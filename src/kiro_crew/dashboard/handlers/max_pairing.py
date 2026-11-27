"""A signed-in dashboard owner issues an ephemeral MAX pairing code."""

import asyncio

from aiohttp import web

from kiro_crew.dashboard.handlers._shared import require_owner_dashboard_request
from kiro_crew.dashboard.handlers.source_providers import (
    is_host_owner_dashboard_request,
)
from kiro_crew.dashboard.origin import check_origin
from kiro_crew.sel import sel


async def api_max_config(request):
    denied = await require_owner_dashboard_request(request, "max.config.read")
    if denied is not None:
        return denied
    if request.get("app") or not is_host_owner_dashboard_request(request):
        return web.json_response({"error": "owner_only", "code": "owner_only"}, status=403)
    from kiro_crew.config.loader import KiroCrewConfig
    from kiro_crew.max.access import OwnerAccess

    cfg = await asyncio.to_thread(KiroCrewConfig.load)
    state = request.app.get("state")
    transport = state.channel_transports.get("max") if state else None
    owner = OwnerAccess.numeric_owner(cfg.max.allowed_user_ids)
    return web.json_response(
        {
            "connected": False,
            "configured": bool(owner),
            "enabled": cfg.max.enabled,
            "delivery_mode": cfg.max.delivery_mode,
            "owner_id": str(owner) if owner else "",
            "ready": bool(cfg.max.enabled and transport),
        },
        headers={"Cache-Control": "no-store"},
    )


async def api_max_subscribe(request):
    denied = await require_owner_dashboard_request(request, "max.subscription.register")
    if denied is not None:
        return denied
    if (
        request.get("app")
        or not is_host_owner_dashboard_request(request)
        or not check_origin(request, require=True)
    ):
        return web.json_response(
            {"error": "owner_origin_required", "code": "owner_origin_required"}, status=403
        )
    from kiro_crew.config.loader import KiroCrewConfig
    from kiro_crew.max.webhook import subscription_url

    cfg = await asyncio.to_thread(KiroCrewConfig.load)
    state = request.app.get("state")
    transport = state.channel_transports.get("max") if state else None
    service = getattr(transport, "webhook", None)
    if (
        not cfg.max.enabled
        or cfg.max.delivery_mode != "webhook"
        or transport is None
        or service is None
    ):
        return web.json_response(
            {"error": "max_webhook_not_ready", "code": "max_webhook_not_ready"}, status=409
        )
    try:
        url = subscription_url(cfg.dashboard.url)
    except ValueError:
        return web.json_response(
            {"error": "external_https_443_required", "code": "external_https_443_required"},
            status=409,
        )
    try:
        result = await transport.client.request(
            "POST",
            "/subscriptions",
            body={
                "url": url,
                "update_types": ["message_created", "message_callback", "bot_started"],
                "secret": service.secret,
            },
        )
    except RuntimeError:
        return web.json_response(
            {"error": "max_subscription_failed", "code": "max_subscription_failed"}, status=502
        )
    if result.get("success") is not True:
        return web.json_response(
            {"error": "max_subscription_failed", "code": "max_subscription_failed"}, status=502
        )
    sel().log_api_access(
        caller=request.get("user", ""),
        operation="max.subscription.register",
        outcome="ok",
        source="dashboard",
    )
    return web.json_response({"ok": True}, headers={"Cache-Control": "no-store"})


async def api_max_pairing(request):
    denied = await require_owner_dashboard_request(request, "max.pairing.issue")
    if denied is not None:
        return denied
    if (
        request.get("app")
        or not check_origin(request, require=True)
        or not is_host_owner_dashboard_request(request)
    ):
        return web.json_response(
            {"error": "owner_origin_required", "code": "owner_origin_required"}, status=403
        )
    state = request.app.get("state")
    transport = state.channel_transports.get("max") if state else None
    if transport is None:
        return web.json_response(
            {"error": "max_not_started", "code": "max_not_started"}, status=409
        )
    await transport._refresh()
    try:
        code = transport.access.issue()
    except ValueError:
        return web.json_response(
            {"error": "owner_already_configured", "code": "owner_already_configured"}, status=409
        )
    sel().log_api_access(
        caller=request.get("user", ""),
        operation="max.pairing.issue",
        outcome="ok",
        source="dashboard",
    )
    return web.json_response(
        {"code": code, "expires_in": 300, "attempts": 5},
        headers={"Cache-Control": "no-store"},
    )
