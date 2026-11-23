"""A signed-in dashboard owner issues an ephemeral MAX pairing code."""

from aiohttp import web

from kiro_crew.dashboard.handlers._shared import require_owner_dashboard_request
from kiro_crew.dashboard.handlers.source_providers import (
    is_host_owner_dashboard_request,
)
from kiro_crew.dashboard.origin import check_origin
from kiro_crew.sel import sel


async def api_max_pairing(request):
    denied = await require_owner_dashboard_request(request, "max.pairing.issue")
    if denied is not None:
        return denied
    if (
        request.get("app")
        or not check_origin(request, require=True)
        or not is_host_owner_dashboard_request(request)
    ):
        return web.json_response({"error": "owner_origin_required"}, status=403)
    state = request.app.get("state")
    transport = state.channel_transports.get("max") if state else None
    if transport is None:
        return web.json_response({"error": "max_not_started"}, status=409)
    await transport._refresh()
    try:
        code = transport.access.issue()
    except ValueError:
        return web.json_response({"error": "owner_already_configured"}, status=409)
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
