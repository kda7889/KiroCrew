"""Factory for the governed channel registry. No listening socket is opened."""

import asyncio
import json
import re

from kiro_crew.config.loader import KiroCrewConfig
from kiro_crew.config.loader_document import update_config_locked
from kiro_crew.config.loader_locations import config_local_path
from kiro_crew.config.paths import data_home
from kiro_crew.max.access import OwnerAccess
from kiro_crew.max.client import MaxClient
from kiro_crew.max.dispatch import MaxDispatcher
from kiro_crew.max.transport import MaxTransport


async def maybe_start_max(orch):
    if not getattr(orch, "_max_enabled", False):
        return None
    mode = orch._cfg.max.delivery_mode
    secret = getattr(orch, "_max_webhook_secret", "")
    if mode not in ("polling", "webhook"):
        return None
    if mode == "webhook" and not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", secret):
        return None

    def save(uid):
        overlay = config_local_path()
        if overlay.exists() and "max" in json.loads(overlay.read_text(encoding="utf-8")):
            raise ValueError("Move MAX settings to the base config before pairing")

        def mutate(data):
            section = data.setdefault("max", {})
            if section.get("allowed_user_ids"):
                raise ValueError("MAX owner already configured")
            if not section.get("enabled"):
                raise ValueError("MAX disabled")
            section["allowed_user_ids"] = [uid]
            return data

        update_config_locked(mutate=mutate, fsync=True)

    access = OwnerAccess(orch._cfg.max.allowed_user_ids, save)
    dispatcher = MaxDispatcher(
        orch.sessions, orch.ctx_builder, orch._cfg, getattr(orch, "conv_log", None)
    )
    dispatcher.dashboard_owner = lambda: (
        orch.dashboard_state.owner_id if orch.dashboard_state is not None else None
    )
    client = MaxClient(orch._max_token, data_home() / "max" / "cursor.json", None)

    async def callback(raw):
        # No uncorrelated/stale button may approve a tool. Typed shared approvals only.
        if str((raw.get("callback") or {}).get("payload") or "").startswith("s:"):
            await dispatcher.handle_callback(raw)
            return
        await client.answer(
            raw["callback"]["callback_id"],
            "Use /approve or /deny for the current tool.",
        )

    transport = MaxTransport(client, access, dispatcher.handle_message, callback)

    async def refresh():
        current = await asyncio.to_thread(KiroCrewConfig.load)
        access.reload(current.max.allowed_user_ids, enabled=current.max.enabled)
        dispatcher.cfg = current

    transport.refresh = refresh
    dispatcher.transport = transport
    client.receive = transport.receive
    client.dispatcher = dispatcher
    if mode == "webhook":
        from kiro_crew.max.webhook import MaxWebhook

        transport.webhook = MaxWebhook(
            transport, dispatcher, secret, data_home() / "max" / "inbox.sqlite"
        )
    if orch.dashboard_state is not None:
        orch.dashboard_state.register_channel_transport(transport)

        def unregister():
            transports = getattr(orch.dashboard_state, "channel_transports", {})
            if transports.get("max") is transport:
                transports.pop("max")

        client.on_close = unregister
    client._task = asyncio.create_task(
        transport.webhook.run() if mode == "webhook" else client.poll()
    )
    return client
