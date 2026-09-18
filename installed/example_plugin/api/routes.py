"""HTTP routes for the reference plugin.

The loader imports api/__init__.py and reads `router` from there.
This module defines the router; __init__ re-exports it.
"""
from fastapi import APIRouter, Request

from .models import HealthResponse, PingResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, plugin_instance=None) -> HealthResponse:
    instance = plugin_instance or getattr(request.state, "plugin_instance", None)
    plugin_id = instance.plugin_id if instance is not None else "unbound"
    return HealthResponse(status="ok", plugin_id=plugin_id)


@router.get("/ping", response_model=PingResponse)
async def ping(plugin_instance=None) -> PingResponse:
    if plugin_instance is None:
        return PingResponse(plugin_id="unbound", note="no-instance", pings=0, state="unknown")
    result = await plugin_instance.ping()
    return PingResponse(**result)
