"""Small MAX adapter around shared command, session, turn and approval logic."""

import asyncio

from kiro_crew.agent_switch_command import (
    ChannelAgentPicks,
    handle_channel_agent_command,
)
from kiro_crew.max.renderer import MaxRenderer
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
from kiro_crew.start_priority import person_priority

HELP = "/help /agent [name] /new /stop /sessions /web /mobile\nApprovals: /approve or /deny."


class MaxDispatcher:
    def __init__(self, sessions, ctx_builder, cfg, conv_log=None):
        self.sessions = sessions
        self.ctx_builder = ctx_builder
        self.cfg = cfg
        self.conv_log = conv_log
        self.transport = None
        self.dashboard_owner = lambda: None
        self.picks = ChannelAgentPicks()
        self._conv = ConversationState(seed_fn=self._seed, bucket_fn=self._agent)
        self._turns = {}

    def _agent(self, uid):
        return self.picks.resolve(uid, self.cfg.agent.default)

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
        if command == "/help":
            await transport.send_message(uid, HELP)
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
        if command == "/stop":
            from kiro_crew.messaging.commands import note_user_stop

            note_user_stop(self.sessions, key)
            await self.sessions.stop_turn(key)
            task = self._turns.get(uid)
            if task and not task.done():
                task.cancel()
            await transport.send_message(uid, "Stop requested.")
            return
        if uid in self._turns and not self._turns[uid].done():
            await transport.send_message(uid, "A reply is running. Use /stop first.")
            return
        if command == "/agent":
            reply = await handle_channel_agent_command(
                self.picks,
                uid,
                arg,
                conv=self._conv,
                configured=self.cfg.agent.default,
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
        if command == "/sessions":
            from kiro_crew.messaging.sessions_view import (
                _collect_recent_sessions_off_loop,
            )

            rows = await _collect_recent_sessions_off_loop(
                self.sessions, limit=50, with_messages=False
            )
            own = [row for row in rows if row["key"].startswith("max:")]
            text = "\n".join(f"{row['key']} — {row['title']}" for row in own[:10])
            await transport.send_message(
                uid,
                f"Current session: {key}\n{text}\nUse /agent to switch; /new to start.",
            )
            return
        renderer = MaxRenderer(transport, uid, key)
        turn = ChannelTurn(
            channel_type="max",
            session_key=key,
            conversation_id=f"max:{uid}",
            agent=self._agent(uid),
            user_text=text,
            renderer=renderer,
            approval_mode="interactive",
            decider=TextReplyApprovalDecider(key, self.sessions),
            inbound_route=InboundRoute(conversation_id=uid, user_id=uid, text=text),
            start_priority=person_priority(inbound.person_origin),
            still_admitted=lambda: transport.access.allowed(int(uid)),
            persist=lambda user, reply, new: self._persist(key, user, reply, self._agent(uid)),
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

        self._turns[uid] = asyncio.create_task(run())
        await started.wait()

    def _persist(self, key, user, reply, agent):
        if self.conv_log:
            from kiro_crew.history import mint_row_mid

            self.conv_log.append(key, "user", user, agent=agent, mid=mint_row_mid())
            if reply:
                self.conv_log.append(key, "assistant", reply, agent=agent, mid=mint_row_mid())

    async def close(self):
        for task in self._turns.values():
            task.cancel()
        await asyncio.gather(*self._turns.values(), return_exceptions=True)
