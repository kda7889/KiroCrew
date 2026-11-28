"""MAX owner navigation uses the shared resume transaction like Telegram."""

from types import SimpleNamespace

import pytest
from max_sessions_helpers import Sessions as _Sessions
from max_sessions_helpers import conversation_log as _log

from kiro_crew.config.loader import KiroCrewConfig
from kiro_crew.max.access import OwnerAccess
from kiro_crew.max.dispatch import MaxDispatcher
from kiro_crew.max.transport import MaxTransport
from kiro_crew.messaging.transport import InboundMessage


class _Wire:
    def __init__(self):
        self.sent = []
        self.edits = []
        self.answers = []

    async def send(self, uid, text, **kwargs):
        mid = str(len(self.sent) + 1)
        self.sent.append({"mid": mid, "uid": uid, "text": text, **kwargs})
        return mid

    async def edit(self, mid, text):
        self.edits.append((mid, text))
        return True

    async def answer(self, cid, text):
        self.answers.append((cid, text))


def _router(tmp_path):
    sessions = _Sessions()
    cfg = KiroCrewConfig()
    cfg.max.enabled = True
    cfg.max.allowed_user_ids = [7]
    log = _log(tmp_path, agent="kirocrew")
    router = MaxDispatcher(sessions, None, cfg, log)
    wire = _Wire()
    router.transport = MaxTransport(
        wire, OwnerAccess([7], lambda uid: None), router.handle_message, None
    )
    return router, wire, sessions


async def _say(router, text, uid="7"):
    await router.handle_message(InboundMessage("max", uid, uid, text))


def _choice(wire):
    message = next(row for row in reversed(wire.sent) if row.get("buttons"))
    return message["buttons"][0][0]["payload"], message["mid"]


def _callback(payload, mid, uid=7):
    return {
        "update_type": "message_callback",
        "callback": {
            "callback_id": "synthetic-callback",
            "payload": payload,
            "user": {"user_id": uid},
        },
        "message": {"recipient": {"chat_type": "dialog"}, "body": {"mid": mid}},
    }


@pytest.mark.asyncio
async def test_owner_can_pick_and_continue_a_dashboard_session(tmp_path, monkeypatch):
    from kiro_crew.max import dispatch

    router, wire, sessions = _router(tmp_path)
    turns = []

    async def drive(turn, **kwargs):
        turns.append(turn)

    monkeypatch.setattr(dispatch, "drive_turn", drive)
    try:
        await _say(router, "/sessions")
        assert any(row.get("buttons") for row in wire.sent), "session list needs usable choices"
        payload, mid = _choice(wire)
        assert await router.handle_callback(_callback(payload, mid))
        assert "dashboard:chat-1" in sessions.inbound_keys
        await _say(router, "continue work")
        assert turns[-1].session_key == "dashboard:chat-1"
        assert turns[-1].agent == "kirocrew"
        assert wire.edits
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_session_choice_is_owner_scoped_and_stale_lists_cannot_switch(tmp_path):
    router, wire, sessions = _router(tmp_path)
    try:
        await _say(router, "/sessions")
        assert any(row.get("buttons") for row in wire.sent)
        old_payload, old_mid = _choice(wire)
        assert not await router.handle_callback(_callback(old_payload, old_mid, uid=99))
        assert not sessions.inbound_keys
        await _say(router, "/sessions")
        new_payload, new_mid = _choice(wire)
        assert not await router.handle_callback(_callback(old_payload, old_mid))
        assert not sessions.inbound_keys
        assert await router.handle_callback(_callback(new_payload, new_mid))
        assert sessions.inbound_keys == {"dashboard:chat-1"}
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_new_leaves_resumed_session_before_starting_native_generation(tmp_path):
    router, wire, sessions = _router(tmp_path)
    try:
        await _say(router, "/sessions")
        assert any(row.get("buttons") for row in wire.sent)
        payload, mid = _choice(wire)
        assert await router.handle_callback(_callback(payload, mid))
        await _say(router, "/new")
        assert not sessions.inbound_keys
        assert any(key.startswith("max:") for key in sessions.reserved_generations)
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_unlink_recovers_even_when_a_resumed_route_refuses(tmp_path):
    router, wire, sessions = _router(tmp_path)
    try:
        await _say(router, "/unlink")
        assert len(wire.sent) == 1, "native recovery command must answer without model startup"
        assert sessions.last_key == ""
        assert "/sessions" in wire.sent[-1]["text"]
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_sessions_do_not_disclose_data_to_unpaired_sender(tmp_path):
    router, wire, sessions = _router(tmp_path)
    try:
        await _say(router, "/sessions", "99")
        await _say(router, "/bots", "99")
        assert not wire.sent
        assert not sessions.inbound_keys
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_agents_alias_and_unknown_commands_have_native_feedback(tmp_path, monkeypatch):
    from kiro_crew.max import dispatch

    router, wire, _ = _router(tmp_path)

    async def agents(*args, **kwargs):
        return "Agent list"

    monkeypatch.setattr(dispatch, "handle_channel_agent_command", agents)
    try:
        await _say(router, "/agents")
        assert wire.sent[-1]["text"] == "Agent list"
        await _say(router, "/unknown-command")
        assert "/help" in wire.sent[-1]["text"]
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_max_api_encodes_navigation_keyboard_and_edit(tmp_path, monkeypatch):
    from kiro_crew.max.client import MaxClient

    calls = []

    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"message": {"body": {"mid": "sent-menu"}}, "success": True}

    client = MaxClient("synthetic-token", tmp_path / "cursor", None)
    monkeypatch.setattr(client, "request", request)
    buttons = [[{"type": "callback", "text": "Project", "payload": "s:synthetic:0"}]]
    assert await client.send(7, "Choose a session", buttons=buttons) == "sent-menu"
    assert calls[-1][2]["body"].get("attachments") == [
        {"type": "inline_keyboard", "payload": {"buttons": buttons}}
    ]
    edit = getattr(client, "edit", None)
    assert callable(edit)
    assert await edit("sent-menu", "Selected")
    assert calls[-1] == (
        "PUT",
        "/messages",
        {
            "params": {"message_id": "sent-menu"},
            "body": {"text": "Selected", "attachments": []},
        },
    )


@pytest.mark.asyncio
async def test_bot_picker_reuses_live_bot_thread_and_keeps_ordinary_chats_out(tmp_path):
    import asyncio

    router, wire, sessions = _router(tmp_path)
    bot = SimpleNamespace(
        key="member-project", mode="member", display_title="Project Bot", agent="project"
    )
    ordinary = SimpleNamespace(
        key="chat-other", mode="", display_title="Other chat", agent="kirocrew"
    )
    router.dashboard_state = SimpleNamespace(_slots={"bot": bot, "ordinary": ordinary})
    await asyncio.to_thread(
        router.conv_log.append, "dashboard:member-project", "assistant", "bot history"
    )
    try:
        await _say(router, "/bots")
        assert any(row.get("buttons") for row in wire.sent), "live Crew Bots must be selectable"
        labels = [button["text"] for row in wire.sent[-1]["buttons"] for button in row]
        assert any("Project Bot" in label for label in labels)
        assert not any("Other chat" in label for label in labels)
        payload, mid = _choice(wire)
        assert await router.handle_callback(_callback(payload, mid))
        assert sessions.inbound_keys == {"dashboard:member-project"}
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_resumed_turn_stops_being_admitted_when_its_binding_moves(tmp_path, monkeypatch):
    from kiro_crew.max import dispatch

    router, wire, sessions = _router(tmp_path)
    turns = []

    async def drive(turn, **kwargs):
        turns.append(turn)

    monkeypatch.setattr(dispatch, "drive_turn", drive)
    try:
        await _say(router, "/sessions")
        payload, mid = _choice(wire)
        await router.handle_callback(_callback(payload, mid))
        await _say(router, "continue")
        assert turns[-1].still_admitted()
        sessions.clear_mirror_link("dashboard:chat-1")
        assert not turns[-1].still_admitted(), "an owner rebind must not leave the old route live"
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_agent_change_never_claims_to_change_a_resumed_chat(tmp_path, monkeypatch):
    from kiro_crew.max import dispatch

    router, wire, _ = _router(tmp_path)
    called = []

    async def switch(*args, **kwargs):
        called.append(True)
        return "Changed agent"

    monkeypatch.setattr(dispatch, "handle_channel_agent_command", switch)
    try:
        await _say(router, "/sessions")
        payload, mid = _choice(wire)
        await router.handle_callback(_callback(payload, mid))
        await _say(router, "/agent other")
        assert not called
        assert "/new" in wire.sent[-1]["text"]
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_status_is_native_and_help_explains_navigation(tmp_path):
    router, wire, sessions = _router(tmp_path)
    try:
        await _say(router, "/status")
        assert wire.sent and "Состояние:" in wire.sent[-1]["text"]
        assert sessions.last_key == ""
        await _say(router, "/help")
        assert "/bots" in wire.sent[-1]["text"]
        assert "/unlink" in wire.sent[-1]["text"]
        assert "1" in wire.sent[-1]["text"] and "3" in wire.sent[-1]["text"]
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_outbound_messages_respect_max_two_per_second_limit(tmp_path, monkeypatch):
    from time import monotonic

    from kiro_crew.max.client import MaxClient

    sent_at = []

    async def request(*args, **kwargs):
        sent_at.append(monotonic())
        return {"message": {"body": {"mid": "synthetic"}}}

    client = MaxClient("synthetic-token", tmp_path / "cursor", None)
    monkeypatch.setattr(client, "request", request)
    try:
        for text in ("approval receipt", "model text", "next permission prompt"):
            await client.send(7, text)
        assert (
            sent_at[2] - sent_at[0] >= 1.0
        ), "three messages cannot occupy one API rate-limit window"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_navigation_labels_and_edits_do_not_echo_the_exact_bot_token():
    wire = _Wire()
    wire._token = "synthetic-opaque-max-token"
    transport = MaxTransport(wire, OwnerAccess([7], lambda uid: None), None, None)
    await transport.send_keyboard(
        "7", "Choose", [[{"type": "callback", "text": wire._token, "payload": "s:synthetic:0"}]]
    )
    await transport.edit_message("7", "1", "Selected " + wire._token)
    assert wire._token not in repr(wire.sent)
    assert wire._token not in repr(wire.edits)


@pytest.mark.asyncio
async def test_gateway_factory_connects_bot_navigation_to_real_dashboard_state(
    tmp_path, monkeypatch
):
    import asyncio

    from kiro_crew.max.client import MaxClient
    from kiro_crew.max.gateway import maybe_start_max

    async def polling(client):
        await asyncio.Event().wait()

    monkeypatch.setattr(MaxClient, "poll", polling)
    router, _, sessions = _router(tmp_path)
    from types import MethodType

    from kiro_crew.dashboard.state_parts.session_events import register_channel_transport

    state = SimpleNamespace(_slots={}, channel_transports={})
    state.register_channel_transport = MethodType(register_channel_transport, state)
    orch = SimpleNamespace(
        _max_enabled=True,
        _max_token="synthetic",
        _cfg=router.cfg,
        sessions=sessions,
        ctx_builder=None,
        conv_log=router.conv_log,
        dashboard_state=state,
    )
    client = await maybe_start_max(orch)
    try:
        assert client.dispatcher.dashboard_state is state
        assert state.channel_transports["max"].dispatcher is client.dispatcher
    finally:
        await client.close()
        await router.close()


@pytest.mark.asyncio
async def test_status_names_the_selected_sessions_agent(tmp_path):
    import asyncio

    router, wire, _ = _router(tmp_path)
    await asyncio.to_thread(
        router.conv_log.update_metadata, "dashboard:chat-1", {"agent": "project"}
    )
    try:
        await _say(router, "/sessions")
        payload, mid = _choice(wire)
        await router.handle_callback(_callback(payload, mid))
        await _say(router, "/status")
        assert "project" in wire.sent[-1]["text"]
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_stop_cancels_its_original_turn_even_when_resume_storage_refuses(
    tmp_path, monkeypatch
):
    import asyncio

    from kiro_crew.max import dispatch
    from kiro_crew.messaging.session_resume import RoutingDecision
    from kiro_crew.testing.wait import FALLBACK_TIMEOUT_SECS

    router, wire, sessions = _router(tmp_path)
    cancelled = asyncio.Event()
    routed = []
    stopped = []

    async def drive(turn, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def refuse(uid):
        routed.append(uid)
        return RoutingDecision(refusal="resume storage unavailable")

    async def stop(key):
        stopped.append(key)

    sessions.stop_turn = stop
    sessions.note_stop = lambda key: None
    monkeypatch.setattr(dispatch, "drive_turn", drive)
    try:
        await _say(router, "/sessions")
        payload, mid = _choice(wire)
        await router.handle_callback(_callback(payload, mid))
        await _say(router, "work in the selected chat")
        sessions.clear_mirror_link("dashboard:chat-1")
        monkeypatch.setattr(router.sessions_ui, "route", refuse)
        await _say(router, "/stop")
        assert not routed, "stop must bypass broken resume storage"
        await asyncio.wait_for(cancelled.wait(), FALLBACK_TIMEOUT_SECS)
        assert stopped == ["dashboard:chat-1"]
    finally:
        await router.close()


def test_max_advertises_the_implemented_session_resume_capability():
    assert MaxTransport.capabilities.supports_session_resume
