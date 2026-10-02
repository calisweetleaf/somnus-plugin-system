"""Isolated crash probe. A raised error must stay inside the worker."""
from __future__ import annotations

from typing import Any, Dict

from plugin_base import PluginBase


class Plugin(PluginBase):
    async def _plugin_initialize(self) -> bool:
        return True

    async def _plugin_activate(self) -> bool:
        return True

    async def _plugin_deactivate(self) -> bool:
        return True

    async def _plugin_cleanup(self) -> bool:
        return True

    async def crash(self) -> Dict[str, Any]:
        raise RuntimeError("isolated crash")
