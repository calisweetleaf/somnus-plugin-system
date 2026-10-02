"""Boot-probe failure plugin. initialize always returns False."""
from __future__ import annotations

from typing import Any, Dict

from plugin_base import PluginBase


class Plugin(PluginBase):
    async def _plugin_initialize(self) -> bool:
        return False

    async def _plugin_activate(self) -> bool:
        return True

    async def _plugin_deactivate(self) -> bool:
        return True

    async def _plugin_cleanup(self) -> bool:
        return True

    async def ping(self) -> Dict[str, Any]:
        return {"plugin_id": self.plugin_id}
