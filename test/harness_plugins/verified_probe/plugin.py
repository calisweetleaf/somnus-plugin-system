"""Verified-domain harness plugin. WRITE_MEMORY is absent by design."""
from __future__ import annotations

from typing import Any, Dict

from host_protocols import MemoryImportance, MemoryType
from plugin_base import PluginBase


class Plugin(PluginBase):
    async def _plugin_initialize(self) -> bool:
        self._internal_state["initialized"] = True
        return True

    async def _plugin_activate(self) -> bool:
        return True

    async def _plugin_deactivate(self) -> bool:
        return True

    async def _plugin_cleanup(self) -> bool:
        return True

    async def ping(self) -> Dict[str, Any]:
        return {"plugin_id": self.plugin_id, "domain": self.execution_domain}

    async def try_write(self) -> Dict[str, Any]:
        await self.memory_manager.store_memory(
            user_id="harness",
            content="should-be-denied",
            memory_type=MemoryType.USER,
            importance=MemoryImportance.LOW,
        )
        return {"wrote": True}
