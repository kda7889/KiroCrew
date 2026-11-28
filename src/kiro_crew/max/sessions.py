"""MAX owner navigation over the shared Telegram-style resume transaction."""

import asyncio

from kiro_crew.messaging.link import ChannelLink
from kiro_crew.messaging.session_resume import (
    TITLE_LIMIT,
    ResumeCopy,
    SessionChoice,
    SessionResumeController,
    same_bucket_origin_keys,
    session_title_of,
)
from kiro_crew.security import redact_credentials, redact_exfiltration_urls


def _safe(text, limit=TITLE_LIMIT):
    text, _ = redact_exfiltration_urls(str(text or ""))
    text, _ = redact_credentials(text)
    return " ".join(text.split())[:limit]


class _Surface:
    owner_refusal = "Выбор сессии доступен только привязанному владельцу."
    choice_owner_refusal = owner_refusal
    choice_expired = "Этот список устарел. Откройте /sessions или /bots ещё раз."
    choice_missing = "Сессия больше недоступна. Откройте /sessions ещё раз."
    choice_expectation_failed = "Не удалось сохранить выбор. Сессия не переключена."
    choice_claim_lost = "Привязка уже изменилась. Откройте /sessions ещё раз."
    choice_binding_failed = "Не удалось подключить сессию. Повторите /sessions."

    def __init__(self, transport, uid, *, bots=False):
        self.transport = transport
        self.uid = uid
        self.expectation_id = f"max:{uid}"
        self.bots = bots

    def display_safe(self, text, max_chars):
        return _safe(text, max_chars)

    def no_choices(self, query):
        if self.bots:
            return "Нет активных чатов ботов. Откройте чат бота в панели: /web."
        return "Сессии не найдены. Создайте беседу через /new или измените запрос."

    def picker_heading(self, query, total):
        heading = "Чаты ботов Crew" if self.bots else "Сессии"
        return f"{heading}: показано до 10 из {total}.\nВыберите чат кнопкой. /new — отдельная беседа MAX."

    def choice_success(self, choice):
        return f"Подключено: {choice.title}\nСледующие сообщения продолжат этот чат. /new — отдельная беседа."

    async def post_picker(self, heading, nonce, choices):
        buttons = [
            [
                {
                    "type": "callback",
                    "text": choice.title[:60] or f"Сессия {index + 1}",
                    "payload": f"s:{nonce}:{index}",
                }
            ]
            for index, choice in enumerate(choices)
        ]
        return await self.transport.send_keyboard(self.uid, heading, buttons)

    async def settle_picker(self, message_id, text):
        return await self.transport.edit_message(self.uid, message_id, text)

    async def say(self, text):
        await self.transport.send_message(self.uid, text)


class MaxSessions:
    def __init__(self, sessions, conv_log):
        self.sessions = sessions
        self.conv_log = conv_log
        self.controller = SessionResumeController(
            sessions,
            conv_log,
            channel_type="max",
            copy=ResumeCopy("/sessions", "/unlink", "MAX conversation"),
            title_display=_safe,
        )

    @staticmethod
    def link(uid):
        return ChannelLink("max", channel_id=uid, principal=uid)

    async def _title(self, key):
        return await asyncio.to_thread(session_title_of, self.conv_log, key, "MAX")

    def admitted(self, uid, key, native_key):
        resolution = self.controller.binder.resolve_inbound(self.link(uid))
        return not resolution.ambiguous and (resolution.key or native_key) == key

    async def route(self, uid):
        return await self.controller.binder.route(f"max:{uid}", self.link(uid), self._title)

    async def settle(self, uid, decision):
        await self.controller.binder.settle(f"max:{uid}", self.link(uid), decision)

    async def release(self, uid):
        released = await self.controller.binder.release(f"max:{uid}", self.link(uid), self._title)
        if released is not None:
            self.controller.push_slots()
        return released

    async def show(self, transport, uid, query, native_key, state=None, *, bots=False):
        self.controller.dashboard_state = state
        choices: tuple[SessionChoice, ...] | None = None
        if bots:
            # Same live Bot-thread predicate as Discord. Never fabricate a dormant Bot's session.
            from kiro_crew.dashboard.chat_utils import slot_history_key
            from kiro_crew.dashboard.slot_ownership import is_member_thread

            found: list[SessionChoice] = []
            for slot in list(getattr(state, "_slots", {}).values()):
                if not is_member_thread(slot):
                    continue
                label = _safe(slot.display_title or slot.agent)
                if query.strip().casefold() not in f"{label} {slot.agent}".casefold():
                    continue
                key = slot_history_key(slot)
                if await asyncio.to_thread(self.conv_log.has_log, key):
                    found.append(SessionChoice(key, label))
            choices = tuple(sorted(found, key=lambda choice: choice.title.casefold()))
        return await self.controller.show_picker(
            _Surface(transport, uid, bots=bots),
            caller=uid,
            picker_owner=uid,
            is_owner=transport.access.allowed(int(uid)),
            query=query,
            native_key=native_key,
            choices=choices,
        )

    async def choose(self, transport, uid, payload, mid, native_key):
        parts = payload.split(":")
        if len(parts) != 3 or parts[0] != "s" or not parts[2].isascii() or not parts[2].isdigit():
            return False
        link = self.link(uid)
        choice = await self.controller.choose(
            _Surface(transport, uid),
            caller=uid,
            picker_owner=uid,
            is_owner=transport.access.allowed(int(uid)),
            message_id=mid,
            nonce=parts[1],
            index=int(parts[2]),
            link=link,
            replace_outbound_keys=same_bucket_origin_keys(self.sessions, link, native_key),
        )
        return choice is not None
