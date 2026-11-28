"""Small MAX adapter around shared command, session, turn and approval logic."""

import asyncio
from dataclasses import dataclass

from kiro_crew.agent_switch_command import (
    ChannelAgentPicks,
    handle_channel_agent_command,
)
from kiro_crew.config.loader import default_template
from kiro_crew.max.renderer import MaxRenderer
from kiro_crew.max.sessions import MaxSessions
from kiro_crew.messaging.approval import (
    TextReplyApprovalDecider,
    deliver_verdict,
    parse_approval_reply,
    pending_for,
)
from kiro_crew.messaging.conversation import ConversationState, reserve_new_generation
from kiro_crew.messaging.dispatch import ChannelTurn, drive_turn
from kiro_crew.messaging.inbound_spool import InboundRoute
from kiro_crew.messaging.link import build_dm_session_key, seed_generation
from kiro_crew.messaging.session_resume import ResumeReleaseError, persisted_session_agent
from kiro_crew.start_priority import person_priority

HELP = """Kiro Crew • MAX

Чаты и боты
/sessions [поиск] — выбрать существующую сессию кнопкой
/bots [имя] — активные чаты ботов Crew
/new — отдельная новая беседа MAX
/unlink — отключить выбранную сессию

Работа
/agents — доступные агенты; /agent имя — выбрать для беседы MAX
/status — текущий контекст и состояние
/stop — остановить ответ
/web или /mobile — открыть панель

Согласования инструментов: 1 — один раз, 2 — отказ, 3 — доверять сессии.
Также работают /approve и /deny. Без ответа за 5 минут — отказ.
Для смены сессии сначала завершите ответ или отправьте /stop.
Чтобы сменить агента подключённого чата: /new, затем /agent имя."""


@dataclass
class _RunningTurn:
    key: str
    task: asyncio.Task


class MaxDispatcher:
    def __init__(self, sessions, ctx_builder, cfg, conv_log=None):
        self.sessions = sessions
        self.ctx_builder = ctx_builder
        self.cfg = cfg
        self.conv_log = conv_log
        self.transport = None
        self.dashboard_owner = lambda: None
        self.picks = ChannelAgentPicks[str]()
        self._conv = ConversationState(seed_fn=self._seed, bucket_fn=self._agent)
        self._turns = {}
        self.dashboard_state = None
        self.sessions_ui = MaxSessions(sessions, conv_log) if conv_log is not None else None

    def _agent(self, uid):
        return self.picks.resolve(uid, default_template(self.cfg))

    def _seed(self, uid):
        return seed_generation(
            self.sessions,
            channel="max",
            agent=self._agent(uid),
            user_id=uid,
            dm_scope="per-channel-peer",
        )

    def _key(self, uid):
        return build_dm_session_key(
            "max",
            self._agent(uid),
            uid,
            gen=self._conv.current_gen(uid),
            dm_scope="per-channel-peer",
        )

    async def handle_message(self, inbound):
        transport = self.transport
        if transport is None:
            return
        if not transport.authorize(inbound):
            return
        from kiro_crew.messaging.identity import channel_inbound_permitted

        if not await channel_inbound_permitted("max"):
            return
        uid = inbound.user_id
        # Help and login do not require a session or provider.
        text = inbound.text.strip()
        command, _, arg = text.partition(" ")
        command = {
            "/agents": "/agent",
            "/session": "/sessions",
            "/bot": "/bots",
            "/cancel": "/stop",
        }.get(command, command)
        if command == "/help":
            await transport.send_message(uid, HELP)
            return
        if command == "/ping":
            await transport.send_message(uid, "pong")
            return
        if command in ("/web", "/mobile"):
            from kiro_crew.max.login import login_link

            try:
                link = login_link(self.cfg.dashboard.url, int(uid), self.dashboard_owner())
            except ValueError as exc:
                await transport.send_message(uid, str(exc))
            else:
                # Deliberate credential delivery, like Telegram's login command.
                await transport.client.send(int(uid), link)
            return
        key = self._key(uid)
        if command == "/status":
            if self.sessions_ui is not None:
                resolution = self.sessions_ui.controller.binder.resolve_inbound(
                    self.sessions_ui.link(uid)
                )
                if resolution.ambiguous:
                    await transport.send_message(
                        uid,
                        "MAX: неоднозначная привязка. /unlink — отключить; /sessions — выбрать заново.",
                    )
                    return
                key = resolution.key or key
                title = await self.sessions_ui._title(key)
            else:
                title = key
            if title in (key, key.removeprefix("dashboard:")):
                title = "Беседа MAX"
            from kiro_crew.max.sessions import _safe

            is_running = uid in self._turns and not self._turns[uid].task.done()
            state = (
                "ожидает согласования"
                if pending_for(key, uid)
                else "отвечает" if is_running else "готов"
            )
            agent = await self._session_agent(uid, key)
            await transport.send_message(
                uid,
                f"Kiro Crew • MAX\nЧат: {_safe(title)}\nАгент: {_safe(agent)}\nСостояние: {state}\n/sessions • /bots • /help",
            )
            return
        if command == "/stop":
            from kiro_crew.messaging.commands import note_user_stop

            running = self._turns.get(uid)
            if running is not None and not running.task.done():
                key = running.key
            elif self.sessions_ui is not None:
                resolution = self.sessions_ui.controller.binder.resolve_inbound(
                    self.sessions_ui.link(uid)
                )
                if resolution.ambiguous:
                    await transport.send_message(
                        uid, "Неоднозначная привязка. /unlink — восстановить выбор."
                    )
                    return
                key = resolution.key or key
            note_user_stop(self.sessions, key)
            if running is not None and not running.task.done():
                running.task.cancel()
            await self.sessions.stop_turn(key)
            await transport.send_message(uid, "Остановка запрошена.")
            return
        if command in ("/sessions", "/bots"):
            if self.sessions_ui is None:
                await transport.send_message(uid, "История недоступна. /new — новая беседа.")
            else:
                await self.sessions_ui.show(
                    transport, uid, arg, key, self.dashboard_state, bots=command == "/bots"
                )
            return
        if command in ("/new", "/unlink") and self.sessions_ui is not None:
            if uid in self._turns and not self._turns[uid].task.done():
                await transport.send_message(uid, "Сначала остановите текущий ответ: /stop.")
                return
            try:
                await self.sessions_ui.release(uid)
            except ResumeReleaseError:
                await transport.send_message(
                    uid, "Не удалось отключить сессию. Сообщение не обработано."
                )
                return
            if command == "/unlink":
                await transport.send_message(
                    uid, "Привязка снята. /sessions — выбрать другой чат; /new — новая беседа."
                )
                return
        elif command == "/unlink":
            await transport.send_message(uid, "Привязки нет. /sessions — список чатов.")
            return
        if self.sessions_ui is not None and command not in ("/agent", "/new"):
            decision = await self.sessions_ui.route(uid)
            if decision.refusal:
                await transport.send_message(uid, decision.refusal)
                await self.sessions_ui.settle(uid, decision)
                return
            key = decision.resumed_key or key
        if command in ("/approve", "/deny"):
            verdict = "approve" if command == "/approve" else "deny"
            receipt = deliver_verdict(key, verdict, uid, sessions=self.sessions)
            await transport.send_message(uid, receipt)
            return
        if pending_for(key, uid):
            verdict = parse_approval_reply(text)
            if verdict:
                receipt = deliver_verdict(key, verdict, uid, sessions=self.sessions)
                await transport.send_message(uid, receipt)
                return
            await transport.send_message(uid, "Use /approve or /deny for the pending tool.")
            if command != "/stop":
                return
        if uid in self._turns and not self._turns[uid].task.done():
            await transport.send_message(uid, "A reply is running. Use /stop first.")
            return
        if command == "/agent":
            if (
                arg
                and self.sessions_ui is not None
                and self.sessions_ui.controller.binder.resumed_session(self.sessions_ui.link(uid))
                is not None
            ):
                await transport.send_message(
                    uid,
                    "Подключён существующий чат. Для другого агента: /new, затем /agent имя. Текущий чат сохранится.",
                )
                return
            reply = await handle_channel_agent_command(
                self.picks,
                uid,
                arg,
                conv=self._conv,
                configured=default_template(self.cfg),
                sessions=self.sessions,
                session_key=lambda: self._key(uid),
            )
            await transport.send_message(uid, reply)
            return
        if command == "/new":
            self._conv.bump_gen(uid)
            saved = await reserve_new_generation(self.sessions, self._key(uid), channel_type="max")
            await transport.send_message(uid, "New session." if saved else "Session save failed.")
            return
        if command.startswith("/"):
            await transport.send_message(uid, "Неизвестная команда. /help — доступные действия.")
            return
        agent = await self._session_agent(uid, key)
        renderer = MaxRenderer(transport, uid, key)
        decider = TextReplyApprovalDecider(key, self.sessions)
        turn = ChannelTurn(
            channel_type="max",
            session_key=key,
            conversation_id=f"max:{uid}",
            agent=agent,
            user_text=text,
            renderer=renderer,
            approval_mode="interactive",
            decider=decider,
            auto_approve_session=decider.trusted,
            inbound_route=InboundRoute(conversation_id=uid, user_id=uid, text=text),
            start_priority=person_priority(inbound.person_origin),
            still_admitted=lambda: transport.access.allowed(int(uid))
            and (self.sessions_ui is None or self.sessions_ui.admitted(uid, key, self._key(uid))),
            persist=lambda user, reply, new: self._persist(key, user, reply, agent),
        )
        started = asyncio.Event()

        async def run():
            started.set()
            try:
                await drive_turn(turn, sessions=self.sessions, ctx_builder=self.ctx_builder)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 -- report a fixed error without provider secrets
                await transport.send_message(uid, "MAX turn failed. Check the dashboard.")
            finally:
                entry = pending_for(key, uid)
                if entry:
                    deliver_verdict(key, "deny", uid)

        self._turns[uid] = _RunningTurn(key, asyncio.create_task(run()))
        await started.wait()

    async def _session_agent(self, uid, key):
        if self.sessions_ui is not None and key != self._key(uid):
            saved = await asyncio.to_thread(persisted_session_agent, self.conv_log, key)
            if saved:
                return saved
        return self._agent(uid)

    async def handle_callback(self, raw):
        callback = raw.get("callback") or {}
        user = callback.get("user") or {}
        uid = user.get("user_id")
        message = raw.get("message") or {}
        if not isinstance(uid, int) or user.get("is_bot") or self.transport is None:
            return False
        await self.transport._refresh()
        if (
            not self.transport.access.allowed(uid)
            or (message.get("recipient") or {}).get("chat_type") != "dialog"
        ):
            return False
        uid = str(uid)
        if self.sessions_ui is None:
            return False
        if uid in self._turns and not self._turns[uid].task.done():
            await self.transport.client.answer(
                callback["callback_id"], "Сначала остановите текущий ответ: /stop."
            )
            return False
        chosen = await self.sessions_ui.choose(
            self.transport,
            uid,
            str(callback.get("payload") or ""),
            str((message.get("body") or {}).get("mid") or ""),
            self._key(uid),
        )
        await self.transport.client.answer(
            callback["callback_id"],
            "Сессия подключена" if chosen else "Выбор не выполнен: откройте /sessions снова",
        )
        return chosen

    def _persist(self, key, user, reply, agent):
        if self.conv_log:
            from kiro_crew.history import mint_row_mid

            self.conv_log.append(key, "user", user, agent=agent, mid=mint_row_mid())
            if reply:
                self.conv_log.append(key, "assistant", reply, agent=agent, mid=mint_row_mid())

    async def close(self):
        tasks = [running.task for running in self._turns.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
