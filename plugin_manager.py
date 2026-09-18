"""Somnus Plugin System — Canonical Loader and Host Integration.

Modified: 2026-09-18
Modified by: Stilgar (Cursor Grok 4.6, Daeron operator)
Justification: PACKET-002 remainder. This module no longer defines a rival
    PluginManifest, PluginBase, PluginDiscovery, PluginFileWatcher, PluginStatus,
    PluginPermission, PluginType, or PluginSecurityManager. It is the loader:
    it discovers through discovery.PluginDiscovery, validates through
    security.SecurityManager, and instantiates plugin_base.PluginBase.
Provenance: SPEC.md section 7, packets/PACKET-002-lineage-convergence.md
Files: plugin_manager.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

from discovery import PluginDiscovery, PluginFileWatcher
from host_protocols import MemoryManager, SecurityEnforcer
from plugin_base import (
    PluginBase,
    PluginManifest,
    PluginPermission,
    PluginState,
    PluginType,
    plugin_identity,
)
from security import SecurityLevel, SecurityManager

logger = logging.getLogger(__name__)


class PluginInfoResponse(BaseModel):
    """Plugin information response model."""

    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    plugin_type: str
    status: str
    permissions: List[str]
    created_at: str
    last_accessed: str


class PluginListResponse(BaseModel):
    """Plugin list response model."""

    plugins: List[PluginInfoResponse]
    total: int
    active: int
    inactive: int


class PluginActionRequest(BaseModel):
    """Plugin action request model."""

    action: str
    plugin_id: str


class PluginActionResponse(BaseModel):
    """Plugin action response model."""

    success: bool
    message: str
    plugin_id: str


class PluginManager:
    """Loader and lifecycle authority for the canonical plugin lineage.

    SecurityEnforcer is retained as the host runtime-policy surface for the
    execution-boundary packet. Packet 1 stores it; it does not call the
    deleted PluginSecurityManager. Static analysis goes through SecurityManager.
    """

    def __init__(
        self,
        app: FastAPI,
        memory_manager: MemoryManager,
        security_enforcer: SecurityEnforcer,
        plugin_base_dir: Path = Path("."),
        security_level: int = SecurityLevel.STANDARD,
    ) -> None:
        self.app = app
        self.memory_manager = memory_manager
        self.security_enforcer = security_enforcer
        self.plugin_base_dir = Path(plugin_base_dir)

        self.active_plugins: Dict[str, PluginBase] = {}
        self.loaded_modules: Dict[str, Any] = {}
        self.plugin_routers: Dict[str, APIRouter] = {}

        self.security_manager = SecurityManager(security_level=security_level)
        self.discovery = PluginDiscovery(self.plugin_base_dir)
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plugin-mgr")

        self._initialize_directories()
        logger.info("Plugin manager initialized at %s", self.plugin_base_dir)

    def _initialize_directories(self) -> None:
        for name in ("installed", "community", "templates", "sandbox"):
            (self.plugin_base_dir / name).mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        logger.info("Starting plugin management system")
        await self.discovery.start_monitoring()
        await self.discover_and_load_plugins()
        logger.info("Plugin management system started")

    async def stop(self) -> None:
        logger.info("Stopping plugin management system")
        await self.discovery.stop_monitoring()
        for plugin_id in list(self.active_plugins.keys()):
            await self.unload_plugin(plugin_id)
        self.executor.shutdown(wait=True)
        logger.info("Plugin management system stopped")

    async def discover_and_load_plugins(self) -> None:
        discovered = await self.discovery.discover_plugins()
        for plugin_id in discovered:
            try:
                await self.load_plugin(plugin_id)
            except Exception as exc:
                logger.error("Failed to load plugin %s: %s", plugin_id, exc)

    async def load_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self.active_plugins:
            logger.warning("Plugin %s already loaded", plugin_id)
            return True

        plugin_path = self.discovery.get_plugin_path(plugin_id)
        if not plugin_path:
            logger.error("Plugin path not found for %s", plugin_id)
            return False

        manifest_path = plugin_path / "manifest.json"
        if not manifest_path.exists():
            logger.error("Manifest not found for plugin %s", plugin_id)
            return False

        try:
            manifest = PluginManifest.from_file(manifest_path)
            expected_id = plugin_identity(manifest.name, manifest.version)
            if expected_id != plugin_id:
                logger.error(
                    "Plugin id mismatch: discovery=%s manifest=%s",
                    plugin_id,
                    expected_id,
                )
                return False

            is_valid, issues = await self.security_manager.validate_plugin(plugin_path, manifest)
            if not is_valid:
                logger.error("Plugin %s failed security validation: %s", plugin_id, issues)
                return False

            plugin_module = await self._load_plugin_module(plugin_path, plugin_id)
            if not plugin_module:
                return False

            plugin_class = getattr(plugin_module, "Plugin", None)
            if plugin_class is None or not issubclass(plugin_class, PluginBase):
                logger.error("Plugin %s does not subclass plugin_base.PluginBase", plugin_id)
                return False

            plugin_instance = plugin_class(plugin_id, manifest, self.memory_manager)
            if not await plugin_instance.initialize():
                logger.error("Plugin %s initialization failed", plugin_id)
                return False

            self.active_plugins[plugin_id] = plugin_instance
            self.loaded_modules[plugin_id] = plugin_module
            await self._register_plugin_api(plugin_id, plugin_instance)

            if not await plugin_instance.activate():
                logger.error("Plugin %s activation failed", plugin_id)
                await self.unload_plugin(plugin_id)
                return False

            logger.info("Plugin %s loaded and activated", plugin_id)
            return True

        except Exception as exc:
            logger.error("Failed to load plugin %s: %s", plugin_id, exc)
            return False

    async def _load_plugin_module(self, plugin_path: Path, plugin_id: str) -> Optional[Any]:
        plugin_file = plugin_path / "plugin.py"
        if not plugin_file.exists():
            logger.error("Plugin file not found: %s", plugin_file)
            return None

        try:
            spec = importlib.util.spec_from_file_location(
                f"somnus_plugin_{plugin_id}",
                plugin_file,
            )
            if spec is None or spec.loader is None:
                logger.error("Could not create module spec for %s", plugin_id)
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
        except Exception as exc:
            logger.error("Failed to load plugin module %s: %s", plugin_id, exc)
            return None

    async def _register_plugin_api(self, plugin_id: str, plugin_instance: PluginBase) -> None:
        plugin_path = self.discovery.get_plugin_path(plugin_id)
        if plugin_path is None:
            return
        api_module_path = plugin_path / "api" / "__init__.py"
        if not api_module_path.exists():
            return

        try:
            api_dir = api_module_path.parent
            spec = importlib.util.spec_from_file_location(
                f"somnus_plugin_{plugin_id}_api",
                api_module_path,
                submodule_search_locations=[str(api_dir)],
            )
            if spec is None or spec.loader is None:
                return

            api_module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = api_module
            spec.loader.exec_module(api_module)

            if not hasattr(api_module, "router"):
                return

            router = api_module.router
            for route in router.routes:
                if not hasattr(route, "endpoint"):
                    continue
                original_endpoint = route.endpoint

                async def wrapped_endpoint(
                    *args: Any,
                    _original=original_endpoint,
                    _instance=plugin_instance,
                    **kwargs: Any,
                ):
                    kwargs["plugin_instance"] = _instance
                    return await _original(*args, **kwargs)

                route.endpoint = wrapped_endpoint

            self.app.include_router(
                router,
                prefix=f"/api/plugins/{plugin_id}",
                tags=[f"Plugin: {plugin_instance.manifest.name}"],
            )
            self.plugin_routers[plugin_id] = router
            logger.info("Registered API endpoints for plugin %s", plugin_id)
        except Exception as exc:
            logger.error("Failed to register API for plugin %s: %s", plugin_id, exc)

    async def unload_plugin(self, plugin_id: str) -> bool:
        if plugin_id not in self.active_plugins:
            logger.warning("Plugin %s not loaded", plugin_id)
            return True

        try:
            plugin_instance = self.active_plugins[plugin_id]
            if plugin_instance.state in (
                PluginState.ACTIVE,
                PluginState.PROCESSING,
                PluginState.SUSPENDED,
            ):
                await plugin_instance.deactivate()
            await plugin_instance.cleanup()

            if plugin_id in self.plugin_routers:
                del self.plugin_routers[plugin_id]
            del self.active_plugins[plugin_id]

            module_name = f"somnus_plugin_{plugin_id}"
            sys.modules.pop(module_name, None)
            sys.modules.pop(f"{module_name}_api", None)
            self.loaded_modules.pop(plugin_id, None)

            logger.info("Plugin %s unloaded", plugin_id)
            return True
        except Exception as exc:
            logger.error("Failed to unload plugin %s: %s", plugin_id, exc)
            return False

    async def reload_plugin(self, plugin_id: str) -> bool:
        logger.info("Reloading plugin %s", plugin_id)
        if plugin_id in self.active_plugins:
            if not await self.unload_plugin(plugin_id):
                return False
        await self.discovery.refresh_cache()
        return await self.load_plugin(plugin_id)

    async def activate_plugin(self, plugin_id: str) -> bool:
        if plugin_id not in self.active_plugins:
            return await self.load_plugin(plugin_id)
        return await self.active_plugins[plugin_id].activate()

    async def deactivate_plugin(self, plugin_id: str) -> bool:
        if plugin_id not in self.active_plugins:
            return True
        return await self.active_plugins[plugin_id].deactivate()

    def get_plugin_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        if plugin_id in self.active_plugins:
            return self.active_plugins[plugin_id].get_info()
        return None

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [plugin.get_info() for plugin in self.active_plugins.values()]

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginBase]:
        return [
            plugin
            for plugin in self.active_plugins.values()
            if plugin.manifest.plugin_type == plugin_type
        ]


def create_plugin_api_routes(plugin_manager: PluginManager) -> APIRouter:
    """Create FastAPI routes for plugin management."""
    router = APIRouter()

    @router.get("/plugins", response_model=PluginListResponse)
    async def list_plugins() -> PluginListResponse:
        plugins_info = plugin_manager.list_plugins()
        active_count = sum(1 for item in plugins_info if item["status"] == PluginState.ACTIVE.value)
        return PluginListResponse(
            plugins=[PluginInfoResponse(**_plugin_info_payload(item)) for item in plugins_info],
            total=len(plugins_info),
            active=active_count,
            inactive=len(plugins_info) - active_count,
        )

    @router.get("/plugins/{plugin_id}", response_model=PluginInfoResponse)
    async def get_plugin_info(plugin_id: str) -> PluginInfoResponse:
        plugin_info = plugin_manager.get_plugin_info(plugin_id)
        if plugin_info is None:
            raise HTTPException(status_code=404, detail="Plugin not found")
        return PluginInfoResponse(**_plugin_info_payload(plugin_info))

    @router.post("/plugins/action", response_model=PluginActionResponse)
    async def plugin_action(request: PluginActionRequest) -> PluginActionResponse:
        success = False
        message = ""
        if request.action == "activate":
            success = await plugin_manager.activate_plugin(request.plugin_id)
            message = "Plugin activated" if success else "Failed to activate plugin"
        elif request.action == "deactivate":
            success = await plugin_manager.deactivate_plugin(request.plugin_id)
            message = "Plugin deactivated" if success else "Failed to deactivate plugin"
        elif request.action == "reload":
            success = await plugin_manager.reload_plugin(request.plugin_id)
            message = "Plugin reloaded" if success else "Failed to reload plugin"
        elif request.action == "unload":
            success = await plugin_manager.unload_plugin(request.plugin_id)
            message = "Plugin unloaded" if success else "Failed to unload plugin"
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        return PluginActionResponse(success=success, message=message, plugin_id=request.plugin_id)

    @router.post("/plugins/discover")
    async def discover_plugins() -> Dict[str, str]:
        await plugin_manager.discovery.refresh_cache()
        await plugin_manager.discover_and_load_plugins()
        return {"message": "Plugin discovery completed"}

    return router


def _plugin_info_payload(info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "plugin_id": info["plugin_id"],
        "name": info["name"],
        "version": info["version"],
        "description": info["description"],
        "author": info["author"],
        "plugin_type": info["plugin_type"],
        "status": info["status"],
        "permissions": info.get("permissions", []),
        "created_at": info.get("created_at", ""),
        "last_accessed": info.get("last_accessed", ""),
    }


async def initialize_plugin_system(
    app: FastAPI,
    memory_manager: MemoryManager,
    security_enforcer: SecurityEnforcer,
    plugin_base_dir: Path = Path("."),
) -> PluginManager:
    """Initialize the plugin system against the canonical lineage."""
    plugin_manager = PluginManager(app, memory_manager, security_enforcer, plugin_base_dir)
    plugin_api_router = create_plugin_api_routes(plugin_manager)
    app.include_router(plugin_api_router, prefix="/api", tags=["Plugin Management"])
    await plugin_manager.start()
    logger.info("Plugin system initialized")
    return plugin_manager


__all__ = [
    "PluginManager",
    "PluginInfoResponse",
    "PluginListResponse",
    "PluginActionRequest",
    "PluginActionResponse",
    "create_plugin_api_routes",
    "initialize_plugin_system",
    "PluginBase",
    "PluginManifest",
    "PluginPermission",
    "PluginType",
    "plugin_identity",
    "PluginDiscovery",
    "PluginFileWatcher",
]
