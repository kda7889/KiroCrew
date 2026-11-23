"""Plain-text MAX output and the shared typed approval ladder."""

from kiro_crew.messaging.approval import (
    abandon_approval,
    build_approval_prompt,
    open_approval,
)
from kiro_crew.messaging.renderer import SilentRenderer, render_options_as_text


class MaxRenderer(SilentRenderer):
    channel_type = "max"

    def __init__(self, transport, uid, session_key):
        super().__init__(transport.capabilities)
        self.transport = transport
        self.uid = uid
        self.session_key = session_key
        self._parts = []

    async def on_text_chunk(self, text):
        self._parts.append(text)

    async def on_prompt_choice(
        self, options, request_id, tool_title="", tool_purpose="", tool_input=""
    ):
        await self._flush()

        async def timeout():
            await self.transport.send_message(self.uid, "Approval expired; tool denied.")

        open_approval(
            self.session_key,
            request_id,
            tool_title=tool_title,
            conversation_id=self.uid,
            on_timeout=timeout,
        )
        try:
            await self.transport.send_message(
                self.uid,
                build_approval_prompt(tool_title, tool_purpose) + "\n" + tool_input,
            )
        except BaseException:
            abandon_approval(self.session_key, request_id)
            raise

    async def _flush(self):
        if self._parts:
            body = render_options_as_text("".join(self._parts), self.capabilities)
            await self.transport.send_message(self.uid, body)
            self._parts.clear()

    async def on_done(self, stop_reason=""):
        if not self._parts and self.empty_turn_notice:
            self._parts.append(self.empty_turn_notice)
        await self._flush()
