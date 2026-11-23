"""Authenticated MAX ingress and a bounded durable inbox. No listener or subscription changes."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import os
import sqlite3
from contextlib import contextmanager
from urllib.parse import urlsplit

from aiohttp import web

from kiro_crew.dashboard.token_auth_paths import MAX_WEBHOOK_PATH

MAX_BODY = 65536


def subscription_url(origin):
    parsed = urlsplit(origin)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.port is not None
        or host == "localhost"
        or host.endswith((".localhost", ".local"))
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Configure an external HTTPS dashboard.url on port 443")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        raise ValueError("Configure an external HTTPS dashboard.url on port 443")
    return origin.rstrip("/") + MAX_WEBHOOK_PATH


class WebhookInbox:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS inbox (key TEXT PRIMARY KEY, body TEXT, state TEXT NOT NULL)"
            )

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=1)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def key(raw):
        kind = raw.get("update_type")
        event_id = (
            (raw.get("callback") or {}).get("callback_id")
            if kind == "message_callback"
            else ((raw.get("message") or {}).get("body") or {}).get("mid")
        )
        identity = [kind, event_id] if event_id else raw
        return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    def enqueue(self, raw):
        key = self.key(raw)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM inbox WHERE key=?", (key,)).fetchone():
                return key
            if (
                db.execute("SELECT count(*) FROM inbox WHERE state!='done'").fetchone()[
                    0
                ]
                >= 256
            ):
                raise OverflowError("MAX inbox full")
            db.execute(
                "INSERT INTO inbox VALUES (?, ?, 'pending')", (key, json.dumps(raw))
            )
        return key

    def next(self):
        with self._db() as db:
            row = db.execute(
                "SELECT key, body, state FROM inbox WHERE state!='done' ORDER BY rowid LIMIT 1"
            ).fetchone()
        return (row[0], json.loads(row[1]), row[2]) if row else None

    def mark(self, key, state):
        with self._db() as db:
            db.execute(
                "UPDATE inbox SET state=?, body=CASE WHEN ?='done' THEN NULL ELSE body END WHERE key=?",
                (state, state, key),
            )
            db.execute(
                "DELETE FROM inbox WHERE state='done' AND rowid NOT IN (SELECT rowid FROM inbox WHERE state='done' ORDER BY rowid DESC LIMIT 4096)"
            )

    def body(self, key):
        with self._db() as db:
            row = db.execute("SELECT body FROM inbox WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def seen(self, key):
        with self._db() as db:
            return (
                db.execute(
                    "SELECT 1 FROM inbox WHERE key=? AND state='done'", (key,)
                ).fetchone()
                is not None
            )

    def complete_control(self, key):
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO inbox VALUES (?, NULL, 'done')", (key,))
        self.mark(key, "done")


class MaxWebhook:
    def __init__(self, transport, dispatcher, secret, path):
        self.transport = transport
        self.dispatcher = dispatcher
        self.secret = secret
        self.inbox = WebhookInbox(path)
        self.wake = asyncio.Event()
        self._control_lock = asyncio.Lock()

    async def accept(self, raw):
        await self.transport._refresh()
        message = raw.get("message") or {}
        text = (message.get("body") or {}).get("text") or ""
        # Pairing codes and callback payloads never enter the durable inbox.
        control = (
            not text
            or raw["update_type"] != "message_created"
            or text.partition(" ")[0]
            in {
                "/start",
                "/help",
                "/agent",
                "/new",
                "/stop",
                "/sessions",
                "/web",
                "/mobile",
                "/approve",
                "/deny",
            }
        )
        if not control:
            from kiro_crew.messaging.approval import parse_approval_reply, pending_for

            uid = (message.get("sender") or {}).get("user_id")
            control = bool(
                self.transport.access.allowed(uid)
                and parse_approval_reply(text)
                and pending_for(self.dispatcher._key(str(uid)), str(uid))
            )
        if control:
            async with self._control_lock:
                key = self.inbox.key(raw)
                if await asyncio.to_thread(self.inbox.seen, key):
                    return
                await self.transport.receive(raw)
                await asyncio.to_thread(self.inbox.complete_control, key)
            return
        user = message.get("sender") or {}
        if (
            not self.transport.access.allowed(user.get("user_id"))
            or user.get("is_bot")
            or (message.get("recipient") or {}).get("chat_type") != "dialog"
        ):
            return
        from kiro_crew.security import redact_credentials

        safe = json.loads(json.dumps(raw))
        text, _ = redact_credentials(text)
        for token in (self.transport.client._token, self.secret):
            if token:
                text = text.replace(token, "[REDACTED: credential]")
        safe["message"]["body"]["text"] = text
        await asyncio.to_thread(self.inbox.enqueue, safe)
        self.wake.set()

    async def run(self):
        while True:
            self.wake.clear()
            entry = await asyncio.to_thread(self.inbox.next)
            if entry is None:
                await self.wake.wait()
                continue
            key, raw, state = entry
            uid = str(raw["message"]["sender"]["user_id"])
            if state == "running":
                # Never replay a turn whose tools may already have run.
                await self.transport._refresh()
                if self.transport.may_send_to(uid):
                    try:
                        await self.transport.send_message(
                            uid,
                            "A previous MAX reply was interrupted. Check the dashboard before resending.",
                        )
                    except (RuntimeError, OSError):
                        await asyncio.sleep(5)
                        continue
                await asyncio.to_thread(self.inbox.mark, key, "done")
                continue
            await asyncio.to_thread(self.inbox.mark, key, "running")
            try:
                await self.transport.receive(raw)
                task = self.dispatcher._turns.get(uid)
                if task:
                    await asyncio.shield(task)
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
            except Exception:  # noqa: BLE001 -- leave an uncertain turn for a restart notice, never auto-replay tools
                await asyncio.sleep(5)
                continue
            await asyncio.to_thread(self.inbox.mark, key, "done")


def _valid(raw):
    if not isinstance(raw, dict) or raw.get("update_type") not in {
        "message_created",
        "message_callback",
        "bot_started",
    }:
        return False
    if raw["update_type"] == "bot_started":
        return isinstance(raw.get("user"), dict) and type(raw.get("chat_id")) is int
    msg = raw.get("message")
    if not isinstance(msg, dict):
        return False
    if not isinstance(msg.get("recipient"), dict) or (
        msg.get("body") is not None and not isinstance(msg.get("body"), dict)
    ):
        return False
    body = msg.get("body") or {}
    if body.get("text") is not None and not isinstance(body.get("text"), str):
        return False
    if raw["update_type"] == "message_callback":
        cb = raw.get("callback")
        return (
            isinstance(cb, dict)
            and isinstance(cb.get("user"), dict)
            and isinstance(cb.get("callback_id"), str)
        )
    return isinstance(msg.get("sender"), dict) and (
        msg.get("body") is None or isinstance(body.get("mid"), str)
    )


async def api_max_webhook(request):
    state = request.app.get("state")
    transport = state.channel_transports.get("max") if state else None
    service = getattr(transport, "webhook", None)
    if service is None or not service.secret:
        return web.Response(status=503)
    worker = getattr(getattr(transport, "client", None), "_task", None)
    if worker is not None and worker.done():
        return web.Response(status=503)
    supplied = request.headers.get("X-Max-Bot-Api-Secret", "")
    if len(supplied) > 256 or not hmac.compare_digest(
        supplied.encode(), service.secret.encode()
    ):
        return web.Response(status=401)
    from kiro_crew.dashboard.handlers._shared import read_bounded_json

    raw, error = await read_bounded_json(request, max_bytes=MAX_BODY)
    if error is not None:
        return error
    if not _valid(raw):
        return web.Response(status=400)
    try:
        await asyncio.wait_for(service.accept(raw), timeout=20)
    except (OSError, sqlite3.Error, OverflowError, TimeoutError, RuntimeError):
        return web.Response(status=503)
    return web.Response(status=200)
