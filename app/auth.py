"""Multi-channel API authentication supporting Direct API Keys, RapidAPI Hub headers, and Web UI Demo mode."""
from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException, Request

from app.config import settings
from app.database import validate_and_increment_key


async def verify_api_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_rapidapi_proxy_secret: str | None = Header(default=None, alias="X-RapidAPI-Proxy-Secret"),
    x_rapidapi_user: str | None = Header(default=None, alias="X-RapidAPI-User"),
    x_rapidapi_subscription: str | None = Header(default=None, alias="X-RapidAPI-Subscription"),
) -> dict[str, Any]:
    """Authenticate requests coming from RapidAPI Marketplace, Direct SaaS API Keys, or local Dashboard."""
    # 1. Check RapidAPI Gateway Header
    if x_rapidapi_user:
        if settings.rapidapi_proxy_secret and x_rapidapi_proxy_secret != settings.rapidapi_proxy_secret:
            raise HTTPException(status_code=403, detail="Invalid RapidAPI Proxy Secret.")
        return {
            "channel": "rapidapi",
            "customer_email": f"{x_rapidapi_user}@rapidapi.marketplace",
            "plan": (x_rapidapi_subscription or "BASIC").lower(),
        }

    # 2. Check Direct API Key Header or Query Parameter
    key_candidate = x_api_key or request.query_params.get("api_key")
    if key_candidate:
        record = validate_and_increment_key(key_candidate)
        if not record:
            raise HTTPException(
                status_code=401,
                detail="Clé API invalide ou révoquée. Obtenez une clé sur le portail Nexus Pulse.",
            )
        if record.get("error") == "quota_exceeded":
            raise HTTPException(
                status_code=429,
                detail=f"Quota mensuel dépassé ({record['monthly_quota']} appels). Passez au forfait supérieur.",
            )
        return {
            "channel": "direct_api_key",
            "customer_email": record["customer_email"],
            "plan": record["plan"],
            "calls_used": record["calls_used"],
            "monthly_quota": record["monthly_quota"],
        }

    # 3. Allow internal Dashboard UI requests (or local testing)
    return {
        "channel": "dashboard_interactive",
        "customer_email": settings.owner_email,
        "plan": "owner_interactive",
    }
