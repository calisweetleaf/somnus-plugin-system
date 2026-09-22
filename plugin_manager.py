"""
MORPHEUS CHAT - Advanced Plugin Architecture System
Production-grade modular extension framework with hot-reload, sandboxing, and recursive integration.

Architecture Features:
- Dynamic plugin discovery and hot-reload mechanisms
- Secure sandboxing with resource limits and permission systems
- Seamless FastAPI integration with automatic endpoint registration
- Memory-aware plugin state persistence via ChromaDB
- Multi-agent plugin orchestration and workflow management
- Community marketplace integration with cryptographic verification
- Recursive consciousness integration maintaining sentience constraints
"""

import asyncio
import hashlib
import importlib
import importlib.util
import inspect
import json
import logging
import os
import sys
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple, Type, Union, Set
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

import aiofiles
import importlib_metadata
from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from host_protocols import SessionID, UserID, MemoryManager, MemoryType, MemoryImportance, SecurityEnforcer

logger = logging.getLogger(__name__)


from plugin_base import PluginBase, PluginManifest, PluginPermission, PluginState, PluginType
from discovery import PluginDiscovery

class PluginSecurityManager:
    """
    Advanced security manager for plugin validation and sandboxing.
    
    Implements comprehensive security checks, code analysis, and runtime isolation
    to ensure plugins cannot compromise the Morpheus system integrity.
    """
    
    def __init__(self, security_enforcer: SecurityEnforcer):
        self.security_enforcer = security_enforcer
        self.trusted_publishers = set()
        self.publisher_keys: Dict[str, bytes] = {}
        self.blocked_patterns = [
            r'__import__\s*\(',
            r'eval\s*\(',
            r'exec\s*\(',
            r'open\s*\(',
            r'subprocess\.',
            r'os\.system',
            r'os\.popen',
        ]
        
        logger.info("Plugin security manager initialized")
    
    async def validate_plugin(self, plugin_path: Path, manifest: PluginManifest) -> Tuple[bool, List[str]]:
        """
        Comprehensive plugin validation including security analysis.
        
        Returns (is_valid, list_of_issues)
        """
        issues = []

        permitted = await self.security_enforcer.validate_action(
            "plugin.load",
            {
                "plugin": manifest.name,
                "permissions": [permission.value for permission in manifest.permissions],
            },
        )
        if not permitted:
            issues.append("Host security enforcer denied plugin.load")

        # Manifest validation
        if not await self._validate_manifest(manifest):
            issues.append("Invalid manifest structure")
        
        # Code security analysis
        security_issues = await self._analyze_code_security(plugin_path)
        issues.extend(security_issues)

        # `trusted` is a self-assertion and does not skip verification.
        if manifest.signature:
            if not await self._verify_signature(plugin_path, manifest.signature):
                issues.append("Invalid cryptographic signature")
        
        # Dependency analysis
        dep_issues = await self._analyze_dependencies(manifest.dependencies)
        issues.extend(dep_issues)
        
        is_valid = len(issues) == 0
        
        if not is_valid:
            logger.warning(f"Plugin validation failed: {issues}")
        
        return is_valid, issues
    
    async def _validate_manifest(self, manifest: PluginManifest) -> bool:
        """Validate manifest completeness and consistency"""
        required_fields = ['name', 'version', 'description', 'author', 'plugin_type']
        
        for field in required_fields:
            if not getattr(manifest, field, None):
                return False
        
        # Version format validation
        import re
        version_pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+)?$'
        if not re.match(version_pattern, manifest.version):
            return False
        
        return True
    
    async def _analyze_code_security(self, plugin_path: Path) -> List[str]:
        """Analyze plugin code for security vulnerabilities"""
        issues = []
        
        # Scan Python files for dangerous patterns
        for py_file in plugin_path.rglob('*.py'):
            try:
                async with aiofiles.open(py_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                
                # Check for blocked patterns
                import re
                for pattern in self.blocked_patterns:
                    if re.search(pattern, content):
                        issues.append(f"Dangerous pattern found in {py_file}: {pattern}")
                
            except Exception as e:
                issues.append(f"Could not analyze {py_file}: {e}")
        
        return issues
    
    def register_publisher_key(self, publisher_id: str, public_key: bytes) -> None:
        """Register a PEM public key. Placeholder material is refused."""
        if b"..." in public_key:
            raise ValueError(f"Refusing placeholder key for {publisher_id}")
        from cryptography.hazmat.primitives import serialization
        serialization.load_pem_public_key(public_key)
        self.publisher_keys[publisher_id] = public_key
        self.trusted_publishers.add(publisher_id)

    def _canonical_plugin_bytes(self, plugin_path: Path) -> bytes:
        """Deterministic byte image of a plugin tree, used as the signed payload.

        The manifest `signature` field is excluded. A signature cannot cover
        itself.
        """
        chunks: List[bytes] = []
        files = [
            item for item in plugin_path.rglob("*")
            if item.is_file() and "__pycache__" not in item.parts
        ]
        for file_path in sorted(files):
            relative = file_path.relative_to(plugin_path).as_posix().encode()
            if file_path.name == "manifest.json":
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                payload.pop("signature", None)
                body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            else:
                body = file_path.read_bytes()
            chunks.append(relative + b"\0" + body)
        return b"".join(chunks)

    async def _verify_signature(self, plugin_path: Path, signature: str) -> bool:
        """Verify an RSA-PSS signature over the canonical plugin tree.

        The signature string is `rsa_pss_sha256:<hex>`. A missing publisher
        key fails closed. The previous body returned True unconditionally.
        """
        if not self.publisher_keys:
            logger.error("Plugin signature present and no publisher key is registered")
            return False
        from security import CryptographicValidator
        validator = CryptographicValidator()
        payload = self._canonical_plugin_bytes(plugin_path)
        for public_key in self.publisher_keys.values():
            if await validator.verify_signature(payload, signature, public_key):
                return True
        return False
    
    async def _analyze_dependencies(self, dependencies: List[str]) -> List[str]:
        """Analyze plugin dependencies for security risks"""
        issues = []
        
        # Known problematic packages
        dangerous_packages = ['os', 'sys', 'subprocess', 'ctypes', 'importlib']
        
        for dep in dependencies:
            if any(dangerous in dep for dangerous in dangerous_packages):
                issues.append(f"Potentially dangerous dependency: {dep}")
        
        return issues


def _bind_plugin_endpoint(endpoint, plugin_instance: PluginBase):
    """Return an endpoint that receives the loaded plugin as plugin_instance.

    Defined outside the registration loop so each route closes over its own
    endpoint. A nested function declared inside that loop would make every
    route call the last endpoint.

    The exposed signature drops ``plugin_instance`` and any varargs. FastAPI
    treats ``*args`` and ``**kwargs`` as required query fields, and it would
    also publish ``plugin_instance`` as a client-supplied parameter. The
    instance is injected by this closure, not by the request.
    """
    signature = inspect.signature(endpoint)
    exposed = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.name != "plugin_instance"
        and parameter.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    ]

    async def wrapped_endpoint(*args, **kwargs):
        kwargs["plugin_instance"] = plugin_instance
        return await endpoint(*args, **kwargs)

    wrapped_endpoint.__signature__ = signature.replace(parameters=exposed)
    wrapped_endpoint.__name__ = getattr(endpoint, "__name__", "plugin_endpoint")
    wrapped_endpoint.__doc__ = getattr(endpoint, "__doc__", None)
    return wrapped_endpoint


class PluginManager:
    """
    Central orchestrator for the Morpheus Chat plugin ecosystem.
    
    Manages the complete plugin lifecycle including discovery, loading, activation,
    security validation, hot-reloading, and integration with the FastAPI backend.
    """
    
    def __init__(
        self, 
        app: FastAPI,
        memory_manager: MemoryManager,
        security_enforcer: SecurityEnforcer,
        plugin_base_dir: Path = Path("morpheus_plugins")
    ):
        self.app = app
        self.memory_manager = memory_manager
        self.security_enforcer = security_enforcer
        self.plugin_base_dir = plugin_base_dir
        
        # Plugin management
        self.active_plugins: Dict[str, PluginBase] = {}
        self.loaded_modules: Dict[str, Any] = {}
        self.plugin_routers: Dict[str, APIRouter] = {}
        
        # Core components
        self.security_manager = PluginSecurityManager(security_enforcer)
        self.discovery = PluginDiscovery(plugin_base_dir)
        self.discovery.file_watcher.on_plugin_changed = self.reload_plugin
        
        # Background tasks
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plugin-mgr")
        
        # Initialize plugin directories
        self._initialize_directories()
        
        logger.info(f"Plugin manager initialized at {plugin_base_dir}")
    
    def _initialize_directories(self):
        """Initialize plugin directory structure"""
        directories = [
            self.plugin_base_dir / "core",
            self.plugin_base_dir / "installed",
            self.plugin_base_dir / "community",
            self.plugin_base_dir / "templates",
            self.plugin_base_dir / "sandbox",
            self.plugin_base_dir / "cache",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start the plugin management system"""
        logger.info("Starting plugin management system...")
        await self.discovery.start_monitoring()
        await self.discover_and_load_plugins()
        
        logger.info("Plugin management system started")
    
    async def stop(self):
        """Stop the plugin management system"""
        logger.info("Stopping plugin management system...")
        await self.discovery.stop_monitoring()
        
        # Deactivate all plugins
        for plugin_id in list(self.active_plugins.keys()):
            await self.deactivate_plugin(plugin_id)
        
        self.executor.shutdown(wait=True, cancel_futures=True)
        
        logger.info("Plugin management system stopped")
    
    async def discover_and_load_plugins(self):
        """Discover all plugins and load them"""
        discovered = await self.discovery.discover_plugins()
        load_order = self.discovery.get_load_order(set(discovered))
        for plugin_id in load_order:
            if plugin_id not in discovered:
                continue
            try:
                await self.load_plugin(plugin_id)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_id}: {e}")
    
    async def load_plugin(self, plugin_id: str) -> bool:
        """Load a specific plugin"""
        if plugin_id in self.active_plugins:
            logger.warning(f"Plugin {plugin_id} already loaded")
            return True
        
        plugin_path = self.discovery.get_plugin_path(plugin_id)
        if not plugin_path:
            logger.error(f"Plugin path not found for {plugin_id}")
            return False
        
        manifest_path = plugin_path / 'manifest.json'
        if not manifest_path.exists():
            logger.error(f"Manifest not found for plugin {plugin_id}")
            return False
        
        try:
            # Load manifest
            manifest = PluginManifest.from_file(manifest_path)
            
            # Security validation
            is_valid, issues = await self.security_manager.validate_plugin(plugin_path, manifest)
            if not is_valid:
                logger.error(f"Plugin {plugin_id} failed security validation: {issues}")
                return False
            
            # Load plugin module
            plugin_module = await self._load_plugin_module(plugin_path, plugin_id)
            if not plugin_module:
                return False
            
            # Instantiate plugin class
            plugin_class = getattr(plugin_module, 'Plugin', None)
            if not plugin_class or not issubclass(plugin_class, PluginBase):
                logger.error(f"Plugin {plugin_id} does not have valid Plugin class")
                return False
            
            # Create plugin instance
            plugin_instance = plugin_class(plugin_id, manifest, self.memory_manager)
            
            # Initialize plugin
            if not await plugin_instance.initialize():
                logger.error(f"Plugin {plugin_id} initialization failed")
                return False
            
            # Register plugin
            self.active_plugins[plugin_id] = plugin_instance
            self.loaded_modules[plugin_id] = plugin_module
            
            # Register API endpoints
            await self._register_plugin_api(plugin_id, plugin_instance)
            
            # Activate plugin
            await plugin_instance.activate()
            
            logger.info(f"Plugin {plugin_id} loaded and activated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
            return False
    
    async def _load_plugin_module(self, plugin_path: Path, plugin_id: str) -> Optional[Any]:
        """Load plugin Python module"""
        plugin_file = plugin_path / 'plugin.py'
        if not plugin_file.exists():
            logger.error(f"Plugin file not found: {plugin_file}")
            return None
        
        try:
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"morpheus_plugin_{plugin_id}",
                plugin_file
            )
            
            if not spec or not spec.loader:
                logger.error(f"Could not create module spec for {plugin_id}")
                return None
            
            # Load module
            module = importlib.util.module_from_spec(spec)
            
            # Add to sys.modules for proper import resolution
            sys.modules[spec.name] = module
            
            # Execute module
            spec.loader.exec_module(module)
            
            return module
            
        except Exception as e:
            logger.error(f"Failed to load plugin module {plugin_id}: {e}")
            return None


    async def _register_plugin_api(self, plugin_id: str, plugin_instance: PluginBase):
        """Register plugin API endpoints with FastAPI"""
        # Check if plugin has API endpoints
        api_module_path = self.discovery.get_plugin_path(plugin_id) / 'api' / '__init__.py'
        if not api_module_path.exists():
            return
        
        try:
            # Load API module
            spec = importlib.util.spec_from_file_location(
                f"morpheus_plugin_{plugin_id}_api",
                api_module_path
            )
            
            if spec and spec.loader:
                api_module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = api_module
                spec.loader.exec_module(api_module)
                
                # Get router from API module
                if hasattr(api_module, 'router'):
                    router = api_module.router
                    
                    # Bind each route to this instance. A closure inside the
                    # loop would capture the last endpoint for every route.
                    for route in router.routes:
                        if hasattr(route, 'endpoint'):
                            route.endpoint = _bind_plugin_endpoint(
                                route.endpoint, plugin_instance
                            )
                    
                    # Mount router
                    self.app.include_router(
                        router,
                        prefix=f"/api/plugins/{plugin_id}",
                        tags=[f"Plugin: {plugin_instance.manifest.name}"]
                    )
                    
                    self.plugin_routers[plugin_id] = router
                    logger.info(f"Registered API endpoints for plugin {plugin_id}")
        
        except Exception as e:
            logger.error(f"Failed to register API for plugin {plugin_id}: {e}")
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a specific plugin"""
        if plugin_id not in self.active_plugins:
            logger.warning(f"Plugin {plugin_id} not loaded")
            return True
        
        try:
            plugin_instance = self.active_plugins[plugin_id]
            
            # Deactivate plugin
            await plugin_instance.deactivate()
            
            # Remove API router
            if plugin_id in self.plugin_routers:
                # FastAPI doesn't have a direct way to remove routers
                # We'd need to recreate the app or use a custom solution
                del self.plugin_routers[plugin_id]
            
            # Remove from active plugins
            del self.active_plugins[plugin_id]
            
            # Remove module from sys.modules
            module_name = f"morpheus_plugin_{plugin_id}"
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Remove from loaded modules
            if plugin_id in self.loaded_modules:
                del self.loaded_modules[plugin_id]
            
            logger.info(f"Plugin {plugin_id} unloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False
    
    async def reload_plugin(self, plugin_id: str) -> bool:
        """Hot-reload a plugin"""
        logger.info(f"Reloading plugin: {plugin_id}")
        
        was_active = plugin_id in self.active_plugins
        
        if was_active:
            # Unload existing plugin
            if not await self.unload_plugin(plugin_id):
                logger.error(f"Failed to unload plugin {plugin_id} for reload")
                return False
        
        # Refresh discovery cache
        await self.discovery.refresh_cache()
        
        # Load plugin again
        success = await self.load_plugin(plugin_id)
        
        if success:
            logger.info(f"Plugin {plugin_id} reloaded successfully")
        else:
            logger.error(f"Failed to reload plugin {plugin_id}")
        
        return success
    
    async def activate_plugin(self, plugin_id: str) -> bool:
        """Activate a loaded plugin"""
        if plugin_id not in self.active_plugins:
            return await self.load_plugin(plugin_id)
        
        plugin_instance = self.active_plugins[plugin_id]
        return await plugin_instance.activate()
    
    async def deactivate_plugin(self, plugin_id: str) -> bool:
        """Deactivate an active plugin"""
        if plugin_id not in self.active_plugins:
            return True
        
        plugin_instance = self.active_plugins[plugin_id]
        return await plugin_instance.deactivate()
    
    def get_plugin_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific plugin"""
        if plugin_id in self.active_plugins:
            return self.active_plugins[plugin_id].get_info()
        return None
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all active plugins"""
        return [plugin.get_info() for plugin in self.active_plugins.values()]
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginBase]:
        """Get all plugins of a specific type"""
        return [
            plugin for plugin in self.active_plugins.values()
            if plugin.manifest.plugin_type == plugin_type
        ]
    
    async def install_plugin_from_archive(self, archive_path: Path, destination: str = "installed") -> bool:
        """Install a plugin archive into the local tree and load it.

        Extraction refuses path traversal. The canonical manifest is validated
        before the tree is moved into the destination, and the security
        manager runs before load.
        """
        from security import ArchivePathError, safe_extract_zip

        if not archive_path.is_file():
            logger.error("Archive not found: %s", archive_path)
            return False

        destination_root = self.plugin_base_dir / destination
        destination_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="somnus_plugin_install_"))
        try:
            try:
                safe_extract_zip(archive_path, staging)
            except ArchivePathError as exc:
                logger.error("Archive rejected: %s", exc)
                return False

            plugin_dir = staging
            if not (plugin_dir / "manifest.json").is_file():
                nested = [item for item in staging.iterdir() if (item / "manifest.json").is_file()]
                if len(nested) != 1:
                    logger.error("Archive does not contain exactly one plugin manifest")
                    return False
                plugin_dir = nested[0]

            manifest = PluginManifest.from_file(plugin_dir / "manifest.json")
            valid, issues = await self.security_manager.validate_plugin(plugin_dir, manifest)
            if not valid:
                logger.error("Archive %s failed validation: %s", manifest.name, issues)
                return False

            target = destination_root / manifest.name
            if target.exists():
                import shutil
                shutil.rmtree(target)
            import shutil
            shutil.move(str(plugin_dir), str(target))
            await self.discovery.scan_plugin_directory(target)
            return await self.load_plugin(manifest.name)
        except Exception as exc:
            logger.error("Archive install failed: %s", exc)
            return False
        finally:
            import shutil
            shutil.rmtree(staging, ignore_errors=True)

    async def get_plugin_marketplace_info(self) -> Dict[str, Any]:
        """Report the local plugin inventory and the disabled network posture.

        Remote registry browsing is not performed. The network path stays off
        until an operator constructs a PluginMarketplace with network_enabled
        and a registry URL they control.
        """
        discovered: Dict[str, Dict[str, Any]] = {}
        for plugin_id, index in getattr(self.discovery, "plugin_index", {}).items():
            discovered[plugin_id] = {
                "name": index.manifest.name,
                "version": index.manifest.version,
                "author": index.manifest.author,
                "plugin_type": index.manifest.plugin_type.value,
                "path": str(index.path),
                "capabilities": [cap.value for cap in index.manifest.capabilities],
            }
        return {
            "network_enabled": False,
            "installed": self.list_plugins(),
            "discovered": discovered,
            "publisher_keys": sorted(self.security_manager.publisher_keys),
            "active_count": len(self.active_plugins),
        }


# Plugin API Models for frontend integration
class PluginInfoResponse(BaseModel):
    """Plugin information response model"""
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
    """Plugin list response model"""
    plugins: List[PluginInfoResponse]
    total: int
    active: int
    inactive: int


class PluginActionRequest(BaseModel):
    """Plugin action request model"""
    action: str  # 'activate', 'deactivate', 'reload', 'unload'
    plugin_id: str


class PluginActionResponse(BaseModel):
    """Plugin action response model"""
    success: bool
    message: str
    plugin_id: str


# Plugin Manager API Integration
def create_plugin_api_routes(plugin_manager: PluginManager) -> APIRouter:
    """Create FastAPI routes for plugin management"""
    router = APIRouter()
    
    @router.get("/plugins", response_model=PluginListResponse)
    async def list_plugins():
        """List all plugins"""
        plugins_info = plugin_manager.list_plugins()
        active_count = sum(1 for p in plugins_info if p['status'] == 'active')
        
        return PluginListResponse(
            plugins=[PluginInfoResponse(**info) for info in plugins_info],
            total=len(plugins_info),
            active=active_count,
            inactive=len(plugins_info) - active_count
        )
    
    @router.get("/plugins/{plugin_id}", response_model=PluginInfoResponse)
    async def get_plugin_info(plugin_id: str):
        """Get specific plugin information"""
        plugin_info = plugin_manager.get_plugin_info(plugin_id)
        if not plugin_info:
            raise HTTPException(status_code=404, detail="Plugin not found")
        
        return PluginInfoResponse(**plugin_info)
    
    @router.post("/plugins/action", response_model=PluginActionResponse)
    async def plugin_action(request: PluginActionRequest):
        """Perform action on plugin"""
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
        
        return PluginActionResponse(
            success=success,
            message=message,
            plugin_id=request.plugin_id
        )
    
    @router.post("/plugins/discover")
    async def discover_plugins():
        """Trigger plugin discovery"""
        await plugin_manager.discovery.refresh_cache()
        await plugin_manager.discover_and_load_plugins()
        return {"message": "Plugin discovery completed"}
    
    return router


# Usage Example and Integration
async def initialize_plugin_system(
    app: FastAPI,
    memory_manager: MemoryManager,
    security_enforcer: SecurityEnforcer
) -> PluginManager:
    """Initialize the complete plugin system"""
    
    # Create plugin manager
    plugin_manager = PluginManager(app, memory_manager, security_enforcer)
    
    # Create API routes
    plugin_api_router = create_plugin_api_routes(plugin_manager)
    app.include_router(plugin_api_router, prefix="/api", tags=["Plugin Management"])
    
    # Start plugin system
    await plugin_manager.start()
    
    logger.info("Plugin system initialized successfully")
    return plugin_manager


if __name__ == "__main__":
    # Example usage
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="Morpheus Chat Plugin System")
    
    # This would be integrated with your existing Morpheus Chat app
    # plugin_manager = await initialize_plugin_system(app, memory_manager, security_enforcer)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
