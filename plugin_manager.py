"""Somnus Plugin System — Canonical Loader and Host Integration.

Modified: 2026-09-18
Modified by: Stilgar (Cursor Grok 4.6, Daeron operator)
Justification: PACKET-005. The loader assembles a HostCapabilityFacade for
    every plugin. Isolated plugins import inside a worker; the host never
    exec_modules their plugin.py. SecurityEnforcer is bound through the façade.
Provenance: SPEC.md section 7, packets/PACKET-005-execution-boundary.md
Files: plugin_manager.py, host_capabilities.py, plugin_worker.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel

from discovery import PluginDiscovery, PluginFileWatcher
from host_capabilities import ExecutionDomain, HostCapabilityFacade, select_execution_domain
from host_protocols import MemoryManager, SecurityEnforcer
from plugin_base import (
    PluginBase,
    PluginManifest,
    PluginPermission,
    PluginState,
    PluginType,
    plugin_identity,
)
from plugin_lifecycle import (
    EndpointDescriptor,
    GenerationTable,
    PluginGeneration,
)
from plugin_worker import IsolatedPluginHandle
from security import SecurityLevel, SecurityManager

PluginRuntime = Union[PluginBase, IsolatedPluginHandle]

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

        self.active_plugins: Dict[str, PluginRuntime] = {}
        self.loaded_modules: Dict[str, Any] = {}
        self.plugin_routers: Dict[str, APIRouter] = {}
        self.plugin_sandboxes: Dict[str, Any] = {}
        self.plugin_domains: Dict[str, ExecutionDomain] = {}
        self.generations = GenerationTable()
        self._host_routes_mounted = False

        self.security_manager = SecurityManager(security_level=security_level)
        self.discovery = PluginDiscovery(self.plugin_base_dir)
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plugin-mgr")

        self._initialize_directories()
        self._mount_host_plugin_routes()
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

        generation = await self.build_generation(plugin_path, expected_id=plugin_id)
        if generation is None:
            return False
        await self.swing_generation(generation)
        logger.info("Plugin %s loaded and activated in domain %s", plugin_id, generation.instance.execution_domain)
        return True

    async def build_generation(
        self,
        plugin_path: Path,
        expected_id: Optional[str] = None,
    ) -> Optional[PluginGeneration]:
        """Construct generation N+1 without taking the live dispatcher."""
        manifest_path = plugin_path / "manifest.json"
        if not manifest_path.exists():
            logger.error("Manifest not found at %s", plugin_path)
            return None

        try:
            manifest = PluginManifest.from_file(manifest_path)
            plugin_id = plugin_identity(manifest.name, manifest.version)
            if expected_id is not None and expected_id != plugin_id:
                logger.error("Plugin id mismatch: expected=%s manifest=%s", expected_id, plugin_id)
                return None

            report_safe, issues = await self.security_manager.validate_plugin(plugin_path, manifest)
            domain = select_execution_domain(manifest)
            if not report_safe and domain != ExecutionDomain.ISOLATED:
                logger.error("Plugin %s failed security validation: %s", plugin_id, issues)
                return None
            if not report_safe and domain == ExecutionDomain.ISOLATED:
                logger.warning(
                    "Plugin %s failed the host-integrated safety bar and will load isolated: %s",
                    plugin_id,
                    issues,
                )

            facade = HostCapabilityFacade(
                self.memory_manager,
                self.security_enforcer,
                manifest,
                plugin_id,
            )
            generation_number = self.generations.next_number(plugin_id)
            module_name = f"somnus_plugin_{plugin_id}_g{generation_number}"

            if domain == ExecutionDomain.ISOLATED:
                plugin_instance = await self._load_isolated_plugin(plugin_path, plugin_id, manifest, facade)
            else:
                plugin_instance = await self._load_in_process_plugin(
                    plugin_path, plugin_id, manifest, facade, module_name=module_name
                )

            if plugin_instance is None:
                return None

            if not await plugin_instance.initialize():
                logger.error("Plugin %s initialization failed", plugin_id)
                await self._teardown_failed_load(plugin_id, plugin_instance)
                return None

            endpoints = await self._collect_plugin_endpoints(plugin_id, plugin_instance, plugin_path, module_name)

            if not await plugin_instance.activate():
                logger.error("Plugin %s activation failed", plugin_id)
                await self._teardown_failed_load(plugin_id, plugin_instance)
                return None

            self.plugin_domains[plugin_id] = domain
            return PluginGeneration(
                generation=generation_number,
                plugin_id=plugin_id,
                instance=plugin_instance,
                path=Path(plugin_path),
                endpoints=endpoints,
                module_name=module_name,
            )
        except Exception as exc:
            logger.error("Failed to build generation from %s: %s", plugin_path, exc)
            return None

    async def swing_generation(self, generation: PluginGeneration) -> None:
        previous = self.generations.swing(generation)
        self.active_plugins[generation.plugin_id] = generation.instance
        self.plugin_domains[generation.plugin_id] = select_execution_domain(generation.instance.manifest)
        if previous is not None:
            await self.drain_generation(previous)
            dependents = self.discovery.get_plugin_dependents(generation.plugin_id)
            for dependent_id in self.discovery.dependency_resolver.get_load_order(dependents):
                if dependent_id != generation.plugin_id and dependent_id in self.active_plugins:
                    await self.reload_plugin(dependent_id)

    async def drain_generation(self, generation: PluginGeneration) -> None:
        instance = generation.instance
        try:
            if instance.state in (PluginState.ACTIVE, PluginState.PROCESSING, PluginState.SUSPENDED):
                await instance.deactivate()
            await instance.cleanup()
        except Exception as exc:
            logger.error("Drain failed for %s g%s: %s", generation.plugin_id, generation.generation, exc)
            if hasattr(instance, "terminate_worker"):
                instance.terminate_worker()
        sys.modules.pop(generation.module_name, None)
        sys.modules.pop(f"{generation.module_name}_api", None)

    async def _load_in_process_plugin(
        self,
        plugin_path: Path,
        plugin_id: str,
        manifest: PluginManifest,
        facade: HostCapabilityFacade,
        module_name: Optional[str] = None,
    ) -> Optional[PluginBase]:
        plugin_module = await self._load_plugin_module(plugin_path, plugin_id, module_name=module_name)
        if not plugin_module:
            return None
        plugin_class = getattr(plugin_module, "Plugin", None)
        if plugin_class is None or not issubclass(plugin_class, PluginBase):
            logger.error("Plugin %s does not subclass plugin_base.PluginBase", plugin_id)
            return None
        instance = plugin_class(plugin_id, manifest, facade)
        instance.execution_domain = facade.domain.value
        self.loaded_modules[plugin_id] = plugin_module
        return instance

    async def _load_isolated_plugin(
        self,
        plugin_path: Path,
        plugin_id: str,
        manifest: PluginManifest,
        facade: HostCapabilityFacade,
    ) -> Optional[IsolatedPluginHandle]:
        sandbox = await self.security_manager.create_sandbox(plugin_id)
        staged = sandbox.temp_dir / "plugin"
        self._stage_plugin_tree(plugin_path, staged)
        self.plugin_sandboxes[plugin_id] = sandbox
        handle = IsolatedPluginHandle(staged, plugin_id, manifest, facade)
        self.loaded_modules[plugin_id] = {"isolated": True, "pid": handle.pid, "staged": str(staged)}
        return handle

    def _stage_plugin_tree(self, source: Path, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            target = dest / item.name
            if item.is_file():
                shutil.copy2(item, target)
            elif item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)

    async def _teardown_failed_load(self, plugin_id: str, instance: PluginRuntime) -> None:
        try:
            await instance.cleanup()
        except Exception:
            if hasattr(instance, "terminate_worker"):
                instance.terminate_worker()
        sandbox = self.plugin_sandboxes.pop(plugin_id, None)
        if sandbox is not None:
            await self.security_manager.cleanup_sandbox(sandbox)
        self.loaded_modules.pop(plugin_id, None)
        self.plugin_domains.pop(plugin_id, None)

    async def _load_plugin_module(
        self,
        plugin_path: Path,
        plugin_id: str,
        module_name: Optional[str] = None,
    ) -> Optional[Any]:
        plugin_file = plugin_path / "plugin.py"
        if not plugin_file.exists():
            logger.error("Plugin file not found: %s", plugin_file)
            return None

        try:
            spec = importlib.util.spec_from_file_location(
                module_name or f"somnus_plugin_{plugin_id}",
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

    def _mount_host_plugin_routes(self) -> None:
        if self._host_routes_mounted:
            return

        @self.app.api_route(
            "/api/plugins/{plugin_id}/{path:path}",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        )
        async def plugin_host_dispatch(plugin_id: str, path: str, request: Request) -> Any:
            return await self.dispatch_plugin_http(plugin_id, path, request)

        self._host_routes_mounted = True

    async def dispatch_plugin_http(self, plugin_id: str, path: str, request: Request) -> Any:
        generation = self.generations.current.get(plugin_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="plugin not loaded")
        normalized = path.strip("/")
        descriptor = generation.endpoints.get((request.method.upper(), normalized))
        if descriptor is None:
            raise HTTPException(status_code=404, detail=f"no {request.method} /{normalized}")
        import inspect

        parameters = inspect.signature(descriptor.handler).parameters
        kwargs: Dict[str, Any] = {}
        if "plugin_instance" in parameters:
            kwargs["plugin_instance"] = generation.instance
        if "request" in parameters:
            kwargs["request"] = request
        return await descriptor.handler(**kwargs)

    async def _collect_plugin_endpoints(
        self,
        plugin_id: str,
        plugin_instance: PluginRuntime,
        plugin_path: Path,
        module_name: str,
    ) -> Dict[tuple, EndpointDescriptor]:
        endpoints: Dict[tuple, EndpointDescriptor] = {}
        api_module_path = plugin_path / "api" / "__init__.py"
        if not api_module_path.exists():
            return endpoints

        try:
            api_dir = api_module_path.parent
            spec = importlib.util.spec_from_file_location(
                f"{module_name}_api",
                api_module_path,
                submodule_search_locations=[str(api_dir)],
            )
            if spec is None or spec.loader is None:
                return endpoints

            api_module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = api_module
            spec.loader.exec_module(api_module)
            if not hasattr(api_module, "router"):
                return endpoints

            router = api_module.router
            self.plugin_routers[plugin_id] = router
            for route in router.routes:
                if not hasattr(route, "endpoint") or not hasattr(route, "methods"):
                    continue
                original_endpoint = route.endpoint
                route_path = getattr(route, "path", "").strip("/")
                for method in route.methods:
                    if method in {"HEAD", "OPTIONS"}:
                        continue
                    endpoints[(method.upper(), route_path)] = EndpointDescriptor(
                        method=method.upper(),
                        path=route_path,
                        handler=original_endpoint,
                    )
            logger.info("Collected %s host endpoints for %s", len(endpoints), plugin_id)
        except Exception as exc:
            logger.error("Failed to collect API endpoints for %s: %s", plugin_id, exc)
        return endpoints

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
            retired = self.generations.drop(plugin_id)
            if retired is not None:
                sys.modules.pop(retired.module_name, None)
                sys.modules.pop(f"{retired.module_name}_api", None)

            self.loaded_modules.pop(plugin_id, None)
            self.plugin_domains.pop(plugin_id, None)
            sandbox = self.plugin_sandboxes.pop(plugin_id, None)
            if sandbox is not None:
                await self.security_manager.cleanup_sandbox(sandbox)

            logger.info("Plugin %s unloaded", plugin_id)
            return True
        except Exception as exc:
            logger.error("Failed to unload plugin %s: %s", plugin_id, exc)
            return False

    async def reload_plugin(self, plugin_id: str) -> bool:
        """Blue/green reload. N keeps serving until N+1 swings."""
        logger.info("Reloading plugin %s", plugin_id)
        await self.discovery.refresh_cache()
        plugin_path = self.discovery.get_plugin_path(plugin_id)
        if plugin_path is None:
            return False
        current = self.generations.current.get(plugin_id)
        checkpoint_id = None
        if current is not None:
            try:
                checkpoint_id = await current.instance.checkpoint_state()
            except Exception as exc:
                logger.warning("Checkpoint before reload failed for %s: %s", plugin_id, exc)
        incoming = await self.build_generation(plugin_path, expected_id=plugin_id)
        if incoming is None:
            logger.error("N+1 boot probe failed for %s; live generation remains", plugin_id)
            return False
        if checkpoint_id:
            try:
                await incoming.instance.restore_checkpoint(checkpoint_id)
            except Exception as exc:
                logger.warning("State restore onto N+1 failed for %s: %s", plugin_id, exc)
        await self.swing_generation(incoming)
        return True

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

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginRuntime]:
        return [
            plugin
            for plugin in self.active_plugins.values()
            if plugin.manifest.plugin_type == plugin_type
        ]

    def get_execution_domain(self, plugin_id: str) -> Optional[ExecutionDomain]:
        return self.plugin_domains.get(plugin_id)


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
