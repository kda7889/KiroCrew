"""DM-only boundary: authorize every inbound event and every outbound target."""

from typing import TYPE_CHECKING

from kiro_crew.messaging.transport import (
    ConfiguredChannelTarget,
    InboundMessage,
    MessagingTransport,
    TransportCapabilities,
)

if TYPE_CHECKING:
    from kiro_crew.max.webhook import MaxWebhook


class MaxTransport(MessagingTransport):
    webhook: "MaxWebhook"
    channel_type = "max"
    capabilities = TransportCapabilities(
        streaming=False,
        edit=False,
        reactions=False,
        files_inbound=False,
        files_outbound=False,
        rich_blocks=False,
        threads=False,
        max_buttons=0,
        max_message_chars=4000,
        supports_session_resume=True,
    )

    def __init__(self, client, access, dispatch, callback):
        self.client = client
        self.access = access
        self._dispatch = dispatch
        self._callback = callback
        self.refresh = None

    async def _refresh(self):
        if self.refresh:
            await self.refresh()

    def authorize(self, msg):
        return (
            msg.user_id == msg.conversation_id
            and msg.user_id.isdecimal()
            and self.access.allowed(int(msg.user_id))
        )

    def configured_targets(self):
        return (
            [ConfiguredChannelTarget(f"user:{self.access.owner}", "MAX owner")]
            if self.access.owner is not None
            else []
        )

    def may_send_to(self, conversation_id, thread_id=None, *, principal=""):
        return (
            thread_id is None
            and isinstance(conversation_id, str)
            and conversation_id.isdecimal()
            and self.access.allowed(int(conversation_id))
        )

    async def resolve_configured_target(self, target_id):
        uid = target_id.removeprefix("user:")
        await self._refresh()
        return (uid, None) if target_id.startswith("user:") and self.may_send_to(uid) else None

    async def resolve_conversation(self, user_id):
        if not user_id.isdecimal() or not self.access.allowed(int(user_id)):
            raise PermissionError("MAX target denied")
        return user_id

    async def fetch_history(self, conversation_id, thread_id=None):
        return []

    async def send_message(self, conversation_id, content, thread_id=None):
        return await self._send(conversation_id, content, thread_id=thread_id)

    async def send_keyboard(self, conversation_id, content, buttons):
        return await self._send(conversation_id, content, buttons=buttons)

    async def edit_message(self, conversation_id, mid, content):
        await self._refresh()
        await self.resolve_conversation(conversation_id)
        from kiro_crew.max.sessions import _safe

        return await self.client.edit(mid, _safe(self._redact_exact(content), 4000))

    async def _send(self, conversation_id, content, thread_id=None, buttons=None):
        await self._refresh()
        await self.resolve_conversation(conversation_id)
        if thread_id is not None:
            raise PermissionError("MAX groups and threads are disabled")
        from kiro_crew.messaging.renderer import chunk_for_transport

        content = self._redact_exact(content)
        mid = ""
        for chunk in chunk_for_transport(content, self.capabilities):
            await self._refresh()
            await self.resolve_conversation(conversation_id)
            if buttons:
                from kiro_crew.max.sessions import _safe

                rows = [
                    [
                        dict(button, text=_safe(self._redact_exact(button["text"]), 60))
                        for button in row
                    ]
                    for row in buttons
                ]
                mid = await self.client.send(int(conversation_id), chunk, buttons=rows)
            else:
                mid = await self.client.send(int(conversation_id), chunk)
        return mid

    def _redact_exact(self, content):
        for token in (
            getattr(self.client, "_token", ""),
            getattr(getattr(self, "webhook", None), "secret", ""),
        ):
            if token:
                content = content.replace(token, "[REDACTED: credential]")
        return content

    async def receive(self, raw):
        from kiro_crew.messaging.identity import channel_inbound_permitted

        if not await channel_inbound_permitted("max"):
            return
        await self._refresh()
        kind = raw.get("update_type")
        if kind == "bot_started":
            user = raw.get("user") or {}
            uid = user.get("user_id")
            # A start event lacks a recipient: verify the chat through MAX.
            if user.get("is_bot") or await self.client.chat_type(raw.get("chat_id")) != "dialog":
                return
            await self._refresh()
            await self._start(uid, raw.get("payload") or "")
            return
        msg = raw.get("message") or {}
        if (msg.get("recipient") or {}).get("chat_type") != "dialog":
            return
        if kind == "message_callback":
            cb = raw.get("callback") or {}
            user = cb.get("user") or {}
            if (
                self.access.allowed(user.get("user_id"))
                and not user.get("is_bot")
                and self._callback
            ):
                await self._callback(raw)
            return
        if kind != "message_created":
            return
        user = msg.get("sender") or {}
        uid = user.get("user_id")
        if user.get("is_bot"):
            return
        text = (msg.get("body") or {}).get("text") or ""
        if text == "/start" or text.startswith("/start "):
            await self._start(uid, text.partition(" ")[2].strip())
            return
        if self.access.allowed(uid) and self._dispatch:
            if not text:
                await self.send_message(str(uid), "MAX accepts text messages only.")
                return
            await self._dispatch(
                InboundMessage(
                    channel_type="max",
                    user_id=str(uid),
                    conversation_id=str(uid),
                    text=text,
                    person_origin=True,
                )
            )

    async def _start(self, uid, code):
        if await self.access.claim(uid, code):
            await self.send_message(str(uid), "MAX owner paired. Use /help.")
        elif self.access.allowed(uid):
            await self.send_message(str(uid), "Use /help.")
