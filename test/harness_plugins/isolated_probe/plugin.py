"""Isolated-domain harness plugin. Import of this module must happen in the worker."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

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

    async def hang(self) -> Dict[str, Any]:
        await asyncio.sleep(3600)
        return {"hung": False}
