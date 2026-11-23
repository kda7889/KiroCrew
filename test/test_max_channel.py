"""MAX access and delivery contracts; no live bot or external network."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_pairing_never_trusts_first_sender_and_is_single_use():
    from kiro_crew.max.access import OwnerAccess

    saved = []
    access = OwnerAccess([], saved.append, clock=lambda: 10)
    assert not access.allowed(42)
    assert not await access.claim(42, "")
    code = access.issue()
    assert not await access.claim(99, "wrong")
    assert not access.allowed(99)
    assert await access.claim(42, code)
    assert saved == [42]
    assert access.allowed(42)
    assert not access.allowed(99)
    assert not await access.claim(99, code)
    with pytest.raises(ValueError):
        access.issue()


@pytest.mark.asyncio
async def test_pairing_expires_and_caps_attempts():
    from kiro_crew.max.access import PAIR_ATTEMPTS, PAIR_TTL, OwnerAccess

    now = [100]
    saved = []
    access = OwnerAccess([], saved.append, clock=lambda: now[0])
    code = access.issue()
    now[0] += PAIR_TTL
    assert not await access.claim(42, code)
    code = access.issue()
    for _ in range(PAIR_ATTEMPTS):
        assert not await access.claim(99, "wrong")
    assert not await access.claim(42, code)
    assert saved == []


@pytest.mark.parametrize(
    "ids", [None, {}, "", [], [True], ["42"], [0], [-42], [42, 99], [42, "bad"]]
)
def test_numeric_single_owner_allowlist_fails_closed(ids):
    from kiro_crew.max.access import OwnerAccess

    access = OwnerAccess(ids, lambda uid: None)
    assert not access.allowed(42)
    assert not access.allowed(True)
    assert not access.allowed("42")


def message(uid=42, *, kind="dialog", text="hello", mid="mid.1"):
    return {
        "update_type": "message_created",
        "timestamp": 100,
        "message": {
            "sender": {"user_id": uid, "is_bot": False},
            "recipient": {"chat_id": 700, "chat_type": kind, "user_id": 123},
            "body": {"mid": mid, "text": text},
        },
    }


class Wire:
    def __init__(self):
        self.sent = []
        self.answers = []

    async def send(self, uid, text, **kwargs):
        self.sent.append((uid, text, kwargs))
        return "mid.out"

    async def answer(self, cid, text):
        self.answers.append((cid, text))

    async def chat_type(self, cid):
        return "dialog"


@pytest.mark.asyncio
async def test_messages_callbacks_and_starts_gate_owner_and_private_chat():
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport

    seen = []
    callbacks = []

    async def dispatch(msg):
        seen.append(msg)

    async def callback(raw):
        callbacks.append(raw)

    transport = MaxTransport(
        Wire(), OwnerAccess([42], lambda uid: None), dispatch, callback
    )
    await transport.receive(message(99))
    await transport.receive(message(kind="chat"))
    await transport.receive(message(kind="channel"))
    for uid, kind in [(99, "dialog"), (42, "chat")]:
        raw = message(kind=kind)
        raw["update_type"] = "message_callback"
        raw["callback"] = {
            "callback_id": "c1",
            "user": {"user_id": uid},
            "payload": "a:yes",
        }
        await transport.receive(raw)
    await transport.receive(
        {
            "update_type": "bot_started",
            "chat_id": 700,
            "user": {"user_id": 99},
            "payload": "anything",
        }
    )
    assert not seen and not callbacks
    await transport.receive(message())
    assert [(m.channel_type, m.user_id, m.conversation_id, m.text) for m in seen] == [
        ("max", "42", "42", "hello")
    ]


@pytest.mark.asyncio
async def test_retries_do_not_advance_cursor_until_handled_and_survive_restart(
    tmp_path,
):
    from kiro_crew.max.client import MaxClient

    cursor = tmp_path / "cursor.json"
    handled = []
    fail = [True]

    async def receive(update):
        if update["message"]["body"]["mid"] == "mid.2" and fail[0]:
            raise RuntimeError("retry")
        handled.append(update["message"]["body"]["mid"])

    client = MaxClient("synthetic", cursor, receive)
    page = {"updates": [message(), message(mid="mid.2")], "marker": 123}
    with pytest.raises(RuntimeError):
        await client.handle_page(page)
    assert client.marker is None
    assert handled == ["mid.1"]
    fail[0] = False
    restarted = MaxClient("synthetic", cursor, receive)
    await restarted.handle_page(page)
    assert handled == ["mid.1", "mid.2"]
    assert MaxClient("synthetic", cursor, receive).marker == 123
    await restarted.handle_page(page)
    assert handled == ["mid.1", "mid.2"]


@pytest.mark.asyncio
async def test_pairing_save_failure_never_grants_access():
    from kiro_crew.max.access import OwnerAccess

    def fail(uid):
        raise OSError("disk")

    access = OwnerAccess([], fail)
    code = access.issue()
    with pytest.raises(OSError):
        await access.claim(42, code)
    assert not access.allowed(42)
    assert not await access.claim(42, code)


@pytest.mark.asyncio
async def test_pairing_start_does_not_reach_model_or_group():
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport

    access = OwnerAccess([], lambda uid: None)
    code = access.issue()
    seen = []

    async def dispatch(msg):
        seen.append(msg)

    wire = Wire()
    transport = MaxTransport(wire, access, dispatch, dispatch)
    await transport.receive(message(text=f"/start {code}", kind="chat"))
    assert not access.allowed(42)
    await transport.receive(message(text=f"/start {code}"))
    assert access.allowed(42)
    assert seen == []
    assert wire.sent


@pytest.mark.asyncio
async def test_outbound_refuses_non_owner_and_redacts_token(monkeypatch):
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport

    wire = Wire()
    transport = MaxTransport(wire, OwnerAccess([42], lambda uid: None), None, None)
    with pytest.raises(PermissionError):
        await transport.send_message("99", "secret")
    assert not wire.sent


@pytest.mark.asyncio
async def test_dispatch_uses_shared_turn_and_isolates_agent_session(monkeypatch):
    from kiro_crew.max import dispatch
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport
    from kiro_crew.messaging.transport import InboundMessage

    turns = []

    async def drive(turn, **kwargs):
        turns.append(turn)

    monkeypatch.setattr(dispatch, "drive_turn", drive)
    sessions = SimpleNamespace(is_busy=lambda key: False, max_generation=lambda key: 0)
    cfg = SimpleNamespace(agent=SimpleNamespace(default="auto"))
    router = dispatch.MaxDispatcher(sessions, None, cfg)
    router.transport = MaxTransport(
        Wire(), OwnerAccess([42], lambda uid: None), None, None
    )
    inbound = InboundMessage("max", "42", "42", "hello")
    await router.handle_message(inbound)
    assert turns[0].channel_type == "max"
    assert turns[0].session_key.startswith("max:")
    assert turns[0].approval_mode == "interactive"
    assert turns[0].decider is not None
    inbound.text = "/help"
    await router.handle_message(inbound)
    assert len(turns) == 1
    assert "/agent" in router.transport.client.sent[-1][1]
    inbound.user_id = "99"
    await router.handle_message(inbound)
    assert len(turns) == 1


@pytest.mark.asyncio
async def test_login_requires_external_https_and_uses_existing_token(monkeypatch):
    from kiro_crew.dashboard import token_auth
    from kiro_crew.max.login import login_link

    issued = []

    def mint(uid, **kwargs):
        issued.append((uid, kwargs))
        return "synthetic-link"

    monkeypatch.setattr(token_auth, "generate_token", mint)
    for origin in [
        "",
        "http://example.org",
        "https://localhost",
        "https://127.0.0.1",
        "https://10.0.0.1",
    ]:
        with pytest.raises(ValueError):
            login_link(origin, 42, "dashboard-owner")
    assert issued == []
    assert (
        login_link("https://crew.example.org", 42, "dashboard-owner")
        == "https://crew.example.org/?token=synthetic-link"
    )
    assert issued == [
        ("dashboard-owner", {"ttl_seconds": 300, "extra": {"owner_mint": "1"}})
    ]
    with pytest.raises(ValueError):
        login_link("https://crew.example.org", 42, None)


def test_max_config_roundtrip(tmp_path, monkeypatch):
    from kiro_crew.config.loader import KiroCrewConfig

    monkeypatch.setenv("KIROCREW_HOME", str(tmp_path))
    cfg = KiroCrewConfig()
    assert not cfg.max.enabled
    assert cfg.max.allowed_user_ids == []
    assert cfg.to_dict()["max"]["enabled"] is False


@pytest.mark.asyncio
async def test_successful_callback_only_reaches_owner_handler():
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport

    callbacks = []

    async def callback(raw):
        callbacks.append(raw["callback"]["payload"])

    transport = MaxTransport(
        Wire(), OwnerAccess([42], lambda uid: None), None, callback
    )
    raw = message()
    raw["update_type"] = "message_callback"
    raw["callback"] = {"user": {"user_id": 42}, "payload": "old", "callback_id": "id"}
    await transport.receive(raw)
    assert callbacks == ["old"]


@pytest.mark.asyncio
async def test_renderer_delivers_text_and_approval_round_trip():
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.renderer import MaxRenderer
    from kiro_crew.max.transport import MaxTransport
    from kiro_crew.messaging.approval import (
        TextReplyApprovalDecider,
        deliver_verdict,
        pending_for,
    )

    wire = Wire()
    transport = MaxTransport(wire, OwnerAccess([42], lambda uid: None), None, None)
    renderer = MaxRenderer(transport, "42", "max:test")
    await renderer.on_text_chunk("A useful answer")
    await renderer.on_done()
    assert wire.sent[-1][1] == "A useful answer"
    await renderer.on_prompt_choice([], "req1", tool_title="Run test")
    assert pending_for("max:test", "42") is not None
    assert "Run test" in wire.sent[-1][1]
    assert deliver_verdict("max:test", "approve", "99").startswith("That approval")
    assert pending_for("max:test", "42") is not None

    async def answer():
        deliver_verdict("max:test", "approve", "42")

    answer_task = asyncio.create_task(answer())
    assert await TextReplyApprovalDecider("max:test")(
        SimpleNamespace(request_id="req1")
    )
    await answer_task
    # A finished entry is gone: a replay cannot approve a later request.
    assert not await TextReplyApprovalDecider("max:test")(
        SimpleNamespace(request_id="req1")
    )


@pytest.mark.asyncio
async def test_outbound_removes_exact_bot_token():
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport

    wire = Wire()
    wire._token = "synthetic-sensitive-bot-token"
    transport = MaxTransport(wire, OwnerAccess([42], lambda uid: None), None, None)
    transport.webhook = SimpleNamespace(secret="synthetic-sensitive-webhook-secret")
    await transport.send_message("42", "echo " + wire._token + transport.webhook.secret)
    assert wire._token not in wire.sent[-1][1]
    assert transport.webhook.secret not in wire.sent[-1][1]


def test_max_config_loads_owner_without_coercing_strings(tmp_path, monkeypatch):
    import json

    from kiro_crew.config.loader import KiroCrewConfig

    monkeypatch.setenv("KIROCREW_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps({"max": {"enabled": True, "allowed_user_ids": [42]}}),
        encoding="utf-8",
    )
    cfg = KiroCrewConfig.load()
    assert cfg.max.enabled
    assert cfg.max.allowed_user_ids == [42]


@pytest.mark.asyncio
async def test_pairing_endpoint_refuses_app_and_requires_owner(monkeypatch):
    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request

    from kiro_crew.dashboard.handlers import max_pairing

    request = make_mocked_request("POST", "/api/max/pairing")

    async def denied(req, operation):
        return web.json_response({"error": "owner_only"}, status=403)

    monkeypatch.setattr(max_pairing, "require_owner_dashboard_request", denied)
    assert (await max_pairing.api_max_pairing(request)).status == 403

    async def allowed(req, operation):
        return None

    monkeypatch.setattr(max_pairing, "require_owner_dashboard_request", allowed)
    request["app"] = "untrusted-app"
    assert (await max_pairing.api_max_pairing(request)).status == 403


@pytest.mark.asyncio
async def test_factory_pairing_persists_owner_and_live_revocation(
    tmp_path, monkeypatch
):
    import json

    from kiro_crew.config.loader import KiroCrewConfig
    from kiro_crew.config.loader_document import update_config_locked
    from kiro_crew.max.client import MaxClient
    from kiro_crew.max.gateway import maybe_start_max

    monkeypatch.setenv("KIROCREW_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps(
            {"max": {"enabled": True, "allowed_user_ids": []}, "keep": {"value": 1}}
        ),
        encoding="utf-8",
    )

    async def poll(self):
        await asyncio.Future()

    async def send(self, uid, text, **kwargs):
        return "synthetic-mid"

    monkeypatch.setattr(MaxClient, "poll", poll)
    monkeypatch.setattr(MaxClient, "send", send)
    transports = []
    orch = SimpleNamespace(
        _max_enabled=True,
        _max_token="synthetic",
        _cfg=KiroCrewConfig.load(),
        sessions=None,
        ctx_builder=None,
        dashboard_state=SimpleNamespace(register_channel_transport=transports.append),
    )
    client = await maybe_start_max(orch)
    try:
        transport = transports[0]
        code = transport.access.issue()
        await transport.receive(message(text=f"/start {code}"))
        assert KiroCrewConfig.load().max.allowed_user_ids == [42]
        assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))[
            "keep"
        ] == {"value": 1}

        def revoke(data):
            data["max"]["allowed_user_ids"] = [99]
            return data

        update_config_locked(mutate=revoke)
        with pytest.raises(PermissionError):
            await transport.send_message("42", "private")
        assert transport.access.allowed(99)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_disable_invalidates_pairing_and_malformed_config_cannot_pair():
    from kiro_crew.max.access import OwnerAccess

    access = OwnerAccess([], lambda uid: None)
    code = access.issue()
    access.reload([], enabled=False)
    access.reload([], enabled=True)
    assert not await access.claim(42, code)
    access.reload({}, enabled=True)
    with pytest.raises(ValueError):
        access.issue()


@pytest.mark.asyncio
async def test_http_exception_does_not_echo_token_or_follow_redirects(tmp_path):
    from kiro_crew.max.client import API_ORIGIN, MaxClient

    client = MaxClient("synthetic-secret", tmp_path / "cursor.json", None)
    calls = []

    class HTTP:
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            raise RuntimeError(client._token)

    client._http = HTTP()
    with pytest.raises(RuntimeError, match="^MAX request failed$"):
        await client.request("GET", "/updates")
    assert calls[0][1] == API_ORIGIN + "/updates"
    assert calls[0][2]["headers"] == {"Authorization": "synthetic-secret"}
    assert calls[0][2]["allow_redirects"] is False


@pytest.mark.asyncio
async def test_pairing_api_uses_real_host_owner_gate_and_returns_no_store(monkeypatch):
    import json

    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request

    from kiro_crew.dashboard.handlers import max_pairing
    from kiro_crew.max.access import OwnerAccess

    access = OwnerAccess([], lambda uid: None)

    async def refresh():
        pass

    state = SimpleNamespace(
        owner_id="42",
        channel_transports={"max": SimpleNamespace(access=access, _refresh=refresh)},
    )
    app = web.Application()
    app["state"] = state
    request = make_mocked_request("POST", "/api/max/pairing", app=app)
    request["user"] = "42"
    request["app"] = ""
    monkeypatch.setattr(max_pairing, "check_origin", lambda req, require: True)
    response = await max_pairing.api_max_pairing(request)
    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    body = json.loads(response.text)
    assert body["expires_in"] == 300 and body["attempts"] == 5
    assert await access.claim(42, body["code"])
    assert (await max_pairing.api_max_pairing(request)).status == 409
    request["user"] = "99"
    assert (await max_pairing.api_max_pairing(request)).status in (401, 403)


def test_pairing_model_and_svg_are_consistent():
    import runpy
    import xml.etree.ElementTree as ET
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    render = runpy.run_path(str(root / "scripts/render-max-flow.py"))["render"]
    svg = root / "docs/architecture/max-owner.svg"
    assert svg.read_text(encoding="utf-8") == render(svg.with_suffix(".bpmn"))
    parsed = ET.fromstring(svg.read_text(encoding="utf-8"))
    assert len(parsed.findall(".//{http://www.w3.org/2000/svg}polyline")) == 9


@pytest.mark.asyncio
async def test_shared_agent_new_and_stop_commands_keep_session_binding(monkeypatch):
    from kiro_crew.max import dispatch
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport
    from kiro_crew.messaging.transport import InboundMessage

    calls = []

    async def flush():
        calls.append("flushed")

    async def stop(key):
        calls.append(("stop", key))

    sessions = SimpleNamespace(
        max_generation=lambda bucket: 7,
        is_busy=lambda key: False,
        reserve_generation=lambda key: calls.append(("reserve", key)),
        aflush=flush,
        stop_turn=stop,
        note_stop=lambda key: calls.append(("note", key)),
    )
    router = dispatch.MaxDispatcher(
        sessions, None, SimpleNamespace(agent=SimpleNamespace(default="auto"))
    )
    router.transport = MaxTransport(
        Wire(), OwnerAccess([42], lambda uid: None), None, None
    )

    async def agent(picks, route, arg, **kwargs):
        calls.append(("agent", route, arg, kwargs["session_key"]()))
        return "Agent picker"

    monkeypatch.setattr(dispatch, "handle_channel_agent_command", agent)
    inbound = InboundMessage("max", "42", "42", "/agent chosen")
    await router.handle_message(inbound)
    assert calls == [("agent", "42", "chosen", "max:auto:direct:42:gen7")]
    inbound.text = "/new"
    await router.handle_message(inbound)
    assert calls[-2:] == [("reserve", "max:auto:direct:42:gen8"), "flushed"]
    inbound.text = "/stop"
    await router.handle_message(inbound)
    assert calls[-2:] == [
        ("note", "max:auto:direct:42:gen8"),
        ("stop", "max:auto:direct:42:gen8"),
    ]


@pytest.mark.asyncio
async def test_concurrent_pairing_code_has_one_winner():
    from kiro_crew.max.access import OwnerAccess

    saved = []
    access = OwnerAccess([], saved.append)
    code = access.issue()
    result = await asyncio.gather(access.claim(42, code), access.claim(99, code))
    assert result.count(True) == 1
    assert saved == [42]
    assert not access.allowed(99)
