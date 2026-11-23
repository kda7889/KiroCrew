"""MAX webhook authentication and durable admission, without external services."""

import asyncio
import json
from types import SimpleNamespace
from typing import ClassVar

import pytest
from aiohttp.test_utils import make_mocked_request


@pytest.mark.asyncio
async def test_receiver_authenticates_before_body_and_never_accepts_missing_secret():
    from kiro_crew.max.webhook import api_max_webhook

    state = SimpleNamespace(channel_transports={})
    request = make_mocked_request("POST", "/api/messaging/max", app={"state": state})
    assert (await api_max_webhook(request)).status == 503
    state.channel_transports["max"] = SimpleNamespace(
        webhook=SimpleNamespace(secret="synthetic-webhook-secret")
    )
    assert (await api_max_webhook(request)).status == 401


@pytest.mark.asyncio
async def test_inbox_ack_survives_restart_and_deduplicates(tmp_path):
    from kiro_crew.max.webhook import WebhookInbox

    path = tmp_path / "inbox.sqlite"
    first = WebhookInbox(path)
    raw = {
        "update_type": "message_created",
        "message": {"body": {"mid": "one", "text": "hello"}},
    }
    key = first.enqueue(raw)
    second = WebhookInbox(path)
    assert second.enqueue(raw) == key
    assert second.next() == (key, raw, "pending")
    second.mark(key, "running")
    assert WebhookInbox(path).next() == (key, raw, "running")
    second.mark(key, "done")
    assert first.next() is None
    first.enqueue(raw)
    assert first.next() is None
    assert first.body(key) is None


@pytest.mark.asyncio
async def test_receiver_rejects_bad_shape_and_accepts_once(monkeypatch):
    from kiro_crew.max.webhook import api_max_webhook

    received = []

    async def accept(raw):
        received.append(raw)

    service = SimpleNamespace(secret="synthetic-webhook-secret", accept=accept)
    state = SimpleNamespace(
        channel_transports={"max": SimpleNamespace(webhook=service)}
    )

    class Request:
        app: ClassVar = {"state": state}
        headers: ClassVar = {
            "X-Max-Bot-Api-Secret": service.secret,
            "Content-Type": "application/json",
        }
        content_length = None
        can_read_body = True
        content_type = "application/json"
        charset = "utf-8"

        @property
        def content(self):
            return self

        async def iter_chunked(self, size):
            yield json.dumps(self.body).encode()

        body: ClassVar = []

    request = Request()
    assert (await api_max_webhook(request)).status == 400
    request.body = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 42},
            "recipient": {"chat_type": "dialog"},
            "body": {"mid": "1", "text": "hello"},
        },
    }
    assert (await api_max_webhook(request)).status == 200
    assert received == [request.body]


def test_webhook_bypass_is_exact_and_post_only():
    from kiro_crew.dashboard.token_auth_paths import (
        _exact_method_bypass,
        is_csrf_exempt,
    )

    assert _exact_method_bypass("/api/messaging/max", "POST")
    assert is_csrf_exempt("/api/messaging/max", "POST")
    for path, method in [
        ("/api/messaging/max", "GET"),
        ("/api/messaging/max/other", "POST"),
        ("/api/max/pairing", "POST"),
    ]:
        assert not _exact_method_bypass(path, method)
        assert not is_csrf_exempt(path, method)


@pytest.mark.asyncio
async def test_control_retries_do_not_reuse_approval_or_store_pair_code(tmp_path):
    from kiro_crew.max.webhook import MaxWebhook

    seen = []

    async def refresh():
        pass

    async def receive(raw):
        seen.append(raw)

    transport = SimpleNamespace(_refresh=refresh, receive=receive)
    service = MaxWebhook(transport, None, "synthetic", tmp_path / "inbox.sqlite")
    raw = {
        "update_type": "bot_started",
        "chat_id": 700,
        "user": {"user_id": 42},
        "payload": "synthetic-pair-code",
    }
    await service.accept(raw)
    await service.accept(raw)
    assert seen == [raw]
    assert b"synthetic-pair-code" not in (tmp_path / "inbox.sqlite").read_bytes()


@pytest.mark.asyncio
async def test_pairing_status_reports_owner_without_secrets(monkeypatch):
    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request

    from kiro_crew.config.loader import KiroCrewConfig
    from kiro_crew.dashboard.handlers import max_pairing

    cfg = KiroCrewConfig()
    cfg.max.allowed_user_ids = [42]
    monkeypatch.setattr(KiroCrewConfig, "load", lambda: cfg)
    app = web.Application()
    app["state"] = SimpleNamespace(owner_id="42", channel_transports={})
    req = make_mocked_request("GET", "/api/max/config", app=app)
    req["user"], req["app"] = "42", ""
    response = await max_pairing.api_max_config(req)
    assert response.status == 200
    body = json.loads(response.text)
    assert body["owner_id"] == "42"
    assert not body["ready"]
    assert not any("secret" in key or "token" in key for key in body)
    req["user"] = "99"
    assert (await max_pairing.api_max_config(req)).status in (401, 403)


@pytest.mark.asyncio
async def test_worker_can_receive_approval_while_model_waits(tmp_path):
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.webhook import MaxWebhook

    entered, approved, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()
    turns = {}

    async def refresh():
        pass

    async def turn():
        entered.set()
        await approved.wait()

    async def receive(raw):
        if raw["message"]["body"]["text"] == "/approve":
            approved.set()
        else:
            turns["42"] = asyncio.create_task(turn())

    transport = SimpleNamespace(
        _refresh=refresh,
        receive=receive,
        access=OwnerAccess([42], lambda uid: None),
        client=SimpleNamespace(_token="synthetic"),
    )
    service = MaxWebhook(
        transport, SimpleNamespace(_turns=turns), "synthetic", tmp_path / "inbox.sqlite"
    )
    mark = service.inbox.mark

    def marked(key, state):
        mark(key, state)
        if state == "done":
            loop.call_soon_threadsafe(completed.set)

    service.inbox.mark = marked
    raw = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 42},
            "recipient": {"chat_type": "dialog"},
            "body": {"mid": "one", "text": "hello"},
        },
    }
    await service.accept(raw)
    worker = asyncio.create_task(service.run())
    try:
        await entered.wait()
        control = json.loads(json.dumps(raw))
        control["message"]["body"] = {"mid": "two", "text": "/approve"}
        await service.accept(control)
        await completed.wait()
        assert approved.is_set()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_running_entry_recovers_with_notice_not_tool_reexecution(tmp_path):
    from kiro_crew.max.webhook import MaxWebhook

    notices = []
    finished = asyncio.Event()
    loop = asyncio.get_running_loop()

    async def refresh():
        pass

    async def send(uid, text):
        notices.append((uid, text))

    async def receive(raw):
        pytest.fail("an uncertain turn must never be replayed")

    transport = SimpleNamespace(
        _refresh=refresh,
        send_message=send,
        receive=receive,
        may_send_to=lambda uid: uid == "42",
    )
    service = MaxWebhook(
        transport, SimpleNamespace(_turns={}), "synthetic", tmp_path / "inbox.sqlite"
    )
    raw = {
        "update_type": "message_created",
        "message": {"sender": {"user_id": 42}, "body": {"mid": "one", "text": "hello"}},
    }
    key = service.inbox.enqueue(raw)
    service.inbox.mark(key, "running")
    mark = service.inbox.mark

    def marked(key, state):
        mark(key, state)
        if state == "done":
            loop.call_soon_threadsafe(finished.set)

    service.inbox.mark = marked
    worker = asyncio.create_task(service.run())
    try:
        await finished.wait()
        assert len(notices) == 1 and notices[0][0] == "42"
        assert service.inbox.next() is None
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "http://crew.example.org",
        "https://crew.example.org:8443",
        "https://localhost",
        "https://127.0.0.1",
        "https://crew.example.org/path",
    ],
)
def test_subscription_url_requires_configured_external_https_443(origin):
    from kiro_crew.max.webhook import subscription_url

    with pytest.raises(ValueError):
        subscription_url(origin)


def test_subscription_url_uses_only_existing_origin():
    from kiro_crew.max.webhook import subscription_url

    assert (
        subscription_url("https://crew.example.org")
        == "https://crew.example.org/api/messaging/max"
    )


@pytest.mark.asyncio
async def test_only_host_owner_explicitly_registers_subscription(monkeypatch):
    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request

    from kiro_crew.config.loader import KiroCrewConfig
    from kiro_crew.dashboard.handlers import max_pairing

    calls = []

    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs["body"]))
        return {"success": True}

    cfg = KiroCrewConfig()
    cfg.max.delivery_mode = "webhook"
    cfg.max.enabled = True
    cfg.dashboard.url = "https://crew.example.org"
    monkeypatch.setattr(KiroCrewConfig, "load", lambda: cfg)
    monkeypatch.setattr(max_pairing, "check_origin", lambda req, require: True)
    transport = SimpleNamespace(
        client=SimpleNamespace(request=request),
        webhook=SimpleNamespace(secret="synthetic-secret"),
    )
    app = web.Application()
    app["state"] = SimpleNamespace(owner_id="42", channel_transports={"max": transport})
    req = make_mocked_request("POST", "/api/max/subscription", app=app)
    req["user"], req["app"] = "99", ""
    assert (await max_pairing.api_max_subscribe(req)).status in (401, 403)
    assert not calls
    req["user"] = "42"
    assert (await max_pairing.api_max_subscribe(req)).status == 200
    assert calls[0][0:2] == ("POST", "/subscriptions")
    assert calls[0][2]["url"] == "https://crew.example.org/api/messaging/max"
    assert calls[0][2]["secret"] == "synthetic-secret"
    cfg.dashboard.url = ""
    assert (await max_pairing.api_max_subscribe(req)).status == 409
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_nullable_media_message_is_acknowledged_without_model_turn():
    from kiro_crew.max.access import OwnerAccess
    from kiro_crew.max.transport import MaxTransport
    from kiro_crew.max.webhook import _valid

    turns, sent = [], []

    async def dispatch(message):
        turns.append(message)

    async def send(uid, text):
        sent.append(text)
        return "synthetic-mid"

    transport = MaxTransport(
        SimpleNamespace(send=send), OwnerAccess([42], lambda uid: None), dispatch, None
    )
    raw = {
        "update_type": "message_created",
        "message": {
            "sender": {"user_id": 42},
            "recipient": {"chat_type": "dialog"},
            "body": {"mid": "media", "text": None, "attachments": [{"type": "image"}]},
        },
    }
    assert _valid(raw)
    await transport.receive(raw)
    assert not turns
    assert sent and "text" in sent[0]
    raw["message"]["body"] = None
    assert _valid(raw)
    from kiro_crew.max.webhook import WebhookInbox

    assert WebhookInbox.key(raw)
    await transport.receive(raw)
    assert not turns


@pytest.mark.asyncio
async def test_webhook_factory_needs_no_external_origin_and_never_starts_polling(
    tmp_path, monkeypatch
):
    from kiro_crew.config.loader import KiroCrewConfig
    from kiro_crew.max.client import MaxClient
    from kiro_crew.max.gateway import maybe_start_max

    monkeypatch.setenv("KIROCREW_HOME", str(tmp_path))
    cfg = KiroCrewConfig()
    cfg.max.enabled, cfg.max.delivery_mode = True, "webhook"
    cfg.dashboard.url = ""

    async def poll(self):
        pytest.fail("webhook mode must never start a poller")

    monkeypatch.setattr(MaxClient, "poll", poll)
    transports = {}
    state = SimpleNamespace(
        owner_id="42",
        channel_transports=transports,
        register_channel_transport=lambda t: transports.update({t.channel_type: t}),
    )
    orch = SimpleNamespace(
        _max_enabled=True,
        _max_token="synthetic-bot",
        _max_webhook_secret="synthetic-webhook-secret-32-chars",
        _cfg=cfg,
        sessions=None,
        ctx_builder=None,
        dashboard_state=state,
    )
    client = await maybe_start_max(orch)
    assert client is not None and transports["max"].webhook is not None
    await client.close()
    assert transports == {}
    orch._max_webhook_secret = ""
    assert await maybe_start_max(orch) is None
