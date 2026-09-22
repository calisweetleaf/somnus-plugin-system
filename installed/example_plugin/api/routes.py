"""HTTP surface mounted by PluginManager at /api/plugins/{plugin_id}.

Every handler accepts ``plugin_instance``. The loader injects the live
plugin into that parameter. The three handlers return different payloads so
a route-binding closure bug cannot hide behind a single endpoint.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

_MODELS = Path(__file__).resolve().parent / "models.py"
_spec = importlib.util.spec_from_file_location("somnus_reference_api_models", _MODELS)
if _spec is None or _spec.loader is None:
    raise ImportError("somnus_reference api/models.py is missing")
_models = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _models
_spec.loader.exec_module(_models)

router = APIRouter()


@router.get("/contract", response_model=_models.ContractView)
async def read_contract(plugin_instance=None):
    if plugin_instance is None:
        raise HTTPException(status_code=500, detail="plugin instance was not injected")
    return plugin_instance.contract_view()


@router.get("/lifecycle", response_model=_models.LifecycleView)
async def read_lifecycle(plugin_instance=None):
    if plugin_instance is None:
        raise HTTPException(status_code=500, detail="plugin instance was not injected")
    return plugin_instance.lifecycle_view()


@router.post("/checkpoint", response_model=_models.CheckpointView)
async def take_checkpoint(plugin_instance=None):
    if plugin_instance is None:
        raise HTTPException(status_code=500, detail="plugin instance was not injected")
    checkpoint_id = await plugin_instance.checkpoint_state()
    return {
        "plugin_id": plugin_instance.plugin_id,
        "checkpoint_id": checkpoint_id,
        "merkle_present": bool(checkpoint_id),
    }
