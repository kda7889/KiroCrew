"""MAX approval replies use the real shared registry and configuration."""

import asyncio
from types import SimpleNamespace

import pytest

from kiro_crew.config.loader import KiroCrewConfig
from kiro_crew.max.access import OwnerAccess
from kiro_crew.max.dispatch import MaxDispatcher
from kiro_crew.max.renderer import MaxRenderer
from kiro_crew.max.transport import MaxTransport
from kiro_crew.messaging.approval import (
    TextReplyApprovalDecider,
    abandon_approval,
    pending_for,
)
from kiro_crew.messaging.transport import InboundMessage


class _Wire:
    def __init__(self):
        self.sent = []

    async def send(self, uid, text):
        self.sent.append((uid, text))
        return "synthetic-message"


@pytest.mark.asyncio
@pytest.mark.parametrize("request_id", [0, 1])
@pytest.mark.parametrize(
    "reply,approved,trusted",
    [
        ("1", True, False),
        ("2", False, False),
        ("3", True, True),
        ("/approve", True, False),
        ("/deny", False, False),
        ("Trust this session", True, True),
    ],
)
async def test_reply_answers_the_visible_request(request_id, reply, approved, trusted):
    from kiro_crew.messaging.session_trust import clear_trusted_sessions

    policy = {}
    sessions = SimpleNamespace(
        is_busy=lambda key: False,
        max_generation=lambda key: 0,
        get_approval_policy=lambda key: policy.get(key, ""),
        set_approval_policy=lambda key, value: policy.__setitem__(key, value),
    )
    router = MaxDispatcher(sessions, None, KiroCrewConfig())
    wire = _Wire()
    router.transport = MaxTransport(wire, OwnerAccess([42], lambda uid: None), None, None)
    key = router._key("42")
    renderer = MaxRenderer(router.transport, "42", key)
    decider = TextReplyApprovalDecider(key, sessions)
    await renderer.on_prompt_choice([], request_id, tool_title="Read status")
    waiting = asyncio.create_task(decider(SimpleNamespace(request_id=request_id)))
    try:
        await asyncio.sleep(0)
        assert not waiting.done(), "a visible request must wait, including request number zero"
        await router.handle_message(InboundMessage("max", "99", "99", reply))
        assert pending_for(key, "42") is not None
        await router.handle_message(InboundMessage("max", "42", "42", reply))
        assert pending_for(key, "42") is None, "the reply must resolve the visible request"
        assert await waiting is approved
        assert (policy.get(key) == "auto") is trusted
        assert not any(uid == 99 for uid, _ in wire.sent)
    finally:
        waiting.cancel()
        await asyncio.gather(waiting, return_exceptions=True)
        abandon_approval(key, request_id)
        clear_trusted_sessions()
        await router.close()


@pytest.mark.asyncio
async def test_prompt_names_the_verified_mcp_tool():
    wire = _Wire()
    transport = MaxTransport(wire, OwnerAccess([42], lambda uid: None), None, None)
    renderer = MaxRenderer(transport, "42", "max:approval-display")
    try:
        renderer.prompt_mcp_identity = ("crew-guide", "lookup")
        await renderer.on_prompt_choice([], "named")
        assert "MCP tool: crew-guide / lookup" in wire.sent[-1][1]
        assert "unknown" not in wire.sent[-1][1]
    finally:
        abandon_approval("max:approval-display", "named")


@pytest.mark.asyncio
async def test_turn_reads_the_same_deciders_session_trust(monkeypatch):
    from kiro_crew.max import dispatch

    turns = []
    policy = {}
    sessions = SimpleNamespace(
        is_busy=lambda key: False,
        max_generation=lambda key: 0,
        get_approval_policy=lambda key: policy.get(key, ""),
    )

    async def drive(turn, **kwargs):
        turns.append(turn)

    monkeypatch.setattr(dispatch, "drive_turn", drive)
    router = MaxDispatcher(sessions, None, KiroCrewConfig())
    router.transport = MaxTransport(_Wire(), OwnerAccess([42], lambda uid: None), None, None)
    try:
        await router.handle_message(InboundMessage("max", "42", "42", "hello"))
        predicate = turns[0].auto_approve_session
        assert callable(predicate), "Trust must be consumed by the shared turn driver"
        assert not predicate()
        policy[turns[0].session_key] = "auto"
        assert predicate()
        policy.clear()
        assert not predicate()
    finally:
        await router.close()
