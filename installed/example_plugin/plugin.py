"""Canonical reference plugin.

Loaded by ``PluginManager.load_plugin``. The class name must be ``Plugin``
and the base class must be ``plugin_base.PluginBase``. The four hooks are
``_plugin_initialize``, ``_plugin_activate``, ``_plugin_deactivate``, and
``_plugin_cleanup``.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from plugin_base import PluginBase


def _load(qualified: str, relative: str):
    path = _PLUGIN_DIR / relative
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {relative} for somnus_reference")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_actions = _load("somnus_reference_actions", "agents/actions.py")
_nodes = _load("somnus_reference_nodes", "workflows/nodes.py")
_kinds = _load("somnus_reference_checkpoint_kinds", "memory/extensions/checkpoint_kinds.py")


class Plugin(PluginBase):
    """Worked example of a plugin as a loaded codebase, not an adapter."""

    async def _plugin_initialize(self) -> bool:
        self._internal_state["ledger"] = ["initialize"]
        self._internal_state["actions"] = _actions.catalog()
        self._internal_state["nodes"] = _nodes.catalog()
        self._internal_state["checkpoint_kind"] = _kinds.USER_CHECKPOINT
        depth = await self.recursive_depth_analysis()
        self._internal_state["depth"] = depth
        return depth["within_limit"] is True

    async def _plugin_activate(self) -> bool:
        synced = await self.consciousness_sync(0.0)
        coherence = await self.quantum_coherence_check()
        ledger: List[str] = self._internal_state.setdefault("ledger", [])
        ledger.append("activate")
        self._internal_state["coherence"] = coherence
        self._internal_state["consciousness_synced"] = synced
        return synced is True and coherence >= 0.0

    async def _plugin_deactivate(self) -> bool:
        ledger: List[str] = self._internal_state.setdefault("ledger", [])
        ledger.append("deactivate")
        return True

    async def _plugin_cleanup(self) -> bool:
        ledger: List[str] = self._internal_state.setdefault("ledger", [])
        ledger.append("cleanup")
        return True

    def contract_view(self) -> Dict[str, Any]:
        manifest = self.manifest
        return {
            "plugin_id": self.plugin_id,
            "name": manifest.name,
            "version": manifest.version,
            "plugin_type": manifest.plugin_type.value,
            "permissions": [item.value for item in manifest.permissions],
            "capabilities": [item.value for item in manifest.capabilities],
            "api_endpoints": list(manifest.api_endpoints),
            "agent_actions": list(manifest.agent_actions),
            "workflow_nodes": list(manifest.workflow_nodes),
            "memory_extensions": list(manifest.memory_extensions),
            "network_access_required": manifest.network_access_required,
            "state": self.state.value,
            "coherence": self._internal_state.get("coherence"),
        }

    def lifecycle_view(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "state": self.state.value,
            "ledger": list(self._internal_state.get("ledger", [])),
            "actions": list(self._internal_state.get("actions", [])),
            "nodes": list(self._internal_state.get("nodes", [])),
            "checkpoint_kind": self._internal_state.get("checkpoint_kind"),
        }

    async def record_observation(self, note: str) -> Dict[str, Any]:
        observation = _actions.record_observation(note)
        observations = self._internal_state.setdefault("observations", [])
        observations.append(observation)
        return observation
