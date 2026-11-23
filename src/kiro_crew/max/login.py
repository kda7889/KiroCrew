"""Existing dashboard token exchange, delivered only to the admitted MAX owner."""

import ipaddress
from urllib.parse import urlsplit


def login_link(origin, uid, dashboard_owner):
    if dashboard_owner is None:
        raise ValueError("Dashboard owner state unavailable")
    parsed = urlsplit(origin)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or host == "localhost"
        or host.endswith((".localhost", ".local"))
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Configure an external HTTPS dashboard.url in Settings")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Configure an external HTTPS dashboard.url in Settings")
    from kiro_crew.dashboard.token_auth import generate_token
    from kiro_crew.dashboard.token_auth_tokens import owner_mint_extra
    from kiro_crew.sel import sel

    token = generate_token(
        dashboard_owner or "local-app", ttl_seconds=300, extra=owner_mint_extra()
    )
    sel().log_api_access(
        caller=str(uid), operation="max.dashboard_token", outcome="ok", source="max"
    )
    return f"{origin.rstrip('/')}/?token={token}"
