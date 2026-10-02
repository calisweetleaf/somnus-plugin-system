"""Canonical reference plugin authored against plugin_base.PluginBase."""
from __future__ import annotations

from typing import Any, Dict

from plugin_base import PluginBase


class Plugin(PluginBase):
    """Reference plugin used to prove the production loader path."""

    async def _plugin_initialize(self) -> bool:
        self._internal_state["initialized"] = True
        self._internal_state["pings"] = 0
        return True

    async def _plugin_activate(self) -> bool:
        self._internal_state["activated"] = True
        return True

    async def _plugin_deactivate(self) -> bool:
        self._internal_state["activated"] = False
        return True

    async def _plugin_cleanup(self) -> bool:
        self._internal_state["cleaned"] = True
        return True

    async def ping(self, note: str = "ok") -> Dict[str, Any]:
        """Invocable reference action used by the production-path harness."""
        self._internal_state["pings"] = int(self._internal_state.get("pings", 0)) + 1
        return {
            "plugin_id": self.plugin_id,
            "note": note,
            "pings": self._internal_state["pings"],
            "state": self.state.value,
        }
