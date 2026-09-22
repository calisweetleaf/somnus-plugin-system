"""Response models for the somnus_reference API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ContractView(BaseModel):
    plugin_id: str
    name: str
    version: str
    plugin_type: str
    permissions: List[str]
    capabilities: List[str]
    api_endpoints: List[str]
    agent_actions: List[str]
    workflow_nodes: List[str]
    memory_extensions: List[str]
    network_access_required: bool
    state: str
    coherence: Optional[float] = None


class LifecycleView(BaseModel):
    plugin_id: str
    state: str
    ledger: List[str]
    actions: List[str]
    nodes: List[Dict[str, Any]]
    checkpoint_kind: Optional[str] = None


class CheckpointView(BaseModel):
    plugin_id: str
    checkpoint_id: str
    merkle_present: bool = Field(default=True)
