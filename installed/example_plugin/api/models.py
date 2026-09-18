"""API models for the reference plugin."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    plugin_id: str


class PingResponse(BaseModel):
    plugin_id: str
    note: str
    pings: int
    state: str
