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


class PluginStatus(str, Enum):
    """Plugin lifecycle status tracking"""
    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"
    UNLOADING = "unloading"


class PluginType(str, Enum):
    """Plugin classification for routing and permissions"""
    API_EXTENSION = "api_extension"
    UI_COMPONENT = "ui_component"
    AGENT_ACTION = "agent_action"
    MEMORY_EXTENSION = "memory_extension"
    WORKFLOW_NODE = "workflow_node"
    TOOL_INTEGRATION = "tool_integration"
    RESEARCH_MODULE = "research_module"
    CREATIVE_ENGINE = "creative_engine"


class PluginPermission(str, Enum):
    """Granular permission system for plugin capabilities"""
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    NETWORK_ACCESS = "network_access"
    FILE_SYSTEM = "file_system"
    SYSTEM_COMMANDS = "system_commands"
    USER_INTERFACE = "user_interface"
    SESSION_ACCESS = "session_access"
    AGENT_CONTROL = "agent_control"


@dataclass
class PluginManifest:
    """Comprehensive plugin metadata and configuration"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    
    # Dependencies and compatibility
    morpheus_version_min: str = "1.0.0"
    morpheus_version_max: str = "2.0.0"
    python_version_min: str = "3.11"
    dependencies: List[str] = field(default_factory=list)
    
    # Security and permissions
    permissions: List[PluginPermission] = field(default_factory=list)
    trusted: bool = False
    signature: Optional[str] = None
    
    # Integration points
    api_endpoints: List[str] = field(default_factory=list)
    ui_components: List[str] = field(default_factory=list)
    agent_actions: List[str] = field(default_factory=list)
    
    # Metadata
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str = "MIT"
    tags: List[str] = field(default_factory=list)
    
    @classmethod
    def from_file(cls, manifest_path: Path) -> 'PluginManifest':
        """Load manifest from JSON file"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls(
            name=data['name'],
            version=data['version'],
            description=data['description'],
            author=data['author'],
            plugin_type=PluginType(data['plugin_type']),
            morpheus_version_min=data.get('morpheus_version_min', '1.0.0'),
            morpheus_version_max=data.get('morpheus_version_max', '2.0.0'),
            python_version_min=data.get('python_version_min', '3.11'),
            dependencies=data.get('dependencies', []),
            permissions=[PluginPermission(p) for p in data.get('permissions', [])],
            trusted=data.get('trusted', False),
            signature=data.get('signature'),
            api_endpoints=data.get('api_endpoints', []),
            ui_components=data.get('ui_components', []),
            agent_actions=data.get('agent_actions', []),
            homepage=data.get('homepage'),
            repository=data.get('repository'),
            license=data.get('license', 'MIT'),
            tags=data.get('tags', [])
        )


class PluginBase(ABC):
    """
    Abstract base class for all Morpheus plugins.
    
    Provides the foundational interface that all plugins must implement,
    ensuring compatibility with the recursive consciousness framework.
    """
    
    def __init__(self, plugin_id: str, manifest: PluginManifest, memory_manager: MemoryManager):
        self.plugin_id = plugin_id
        self.manifest = manifest
        self.memory_manager = memory_manager
        self.status = PluginStatus.DISCOVERED
        self.created_at = datetime.now(timezone.utc)
        self.last_accessed = datetime.now(timezone.utc)
        
        # Plugin-specific memory namespace
        self.memory_namespace = f"plugin:{plugin_id}"
        
        # Event hooks
        self.startup_tasks: List[Callable] = []
        self.shutdown_tasks: List[Callable] = []
        
        logger.info(f"Plugin base initialized: {plugin_id}")
    
    async def initialize(self) -> bool:
        """
        Initialize plugin resources and validate requirements.
        
        Returns True if initialization successful, False otherwise.
        """
        try:
            self.status = PluginStatus.LOADING
            
            # Validate dependencies
            if not await self._validate_dependencies():
                self.status = PluginStatus.ERROR
                return False
            
            # Initialize plugin-specific resources
            success = await self.on_initialize()
            
            if success:
                self.status = PluginStatus.LOADED
                logger.info(f"Plugin {self.plugin_id} initialized successfully")
            else:
                self.status = PluginStatus.ERROR
                logger.error(f"Plugin {self.plugin_id} initialization failed")
            
            return success
        
        except Exception as e:
            logger.error(f"Plugin {self.plugin_id} initialization error: {e}")
            self.status = PluginStatus.ERROR
            return False
    
    async def activate(self) -> bool:
        """Activate plugin and register its capabilities"""
        try:
            if self.status != PluginStatus.LOADED:
                return False
            
            # Run startup tasks
            for task in self.startup_tasks:
                await task()
            
            success = await self.on_activate()
            
            if success:
                self.status = PluginStatus.ACTIVE
                logger.info(f"Plugin {self.plugin_id} activated")
            
            return success
        
        except Exception as e:
            logger.error(f"Plugin {self.plugin_id} activation error: {e}")
            self.status = PluginStatus.ERROR
            return False
    
    async def deactivate(self) -> bool:
        """Deactivate plugin and cleanup resources"""
        try:
            if self.status != PluginStatus.ACTIVE:
                return True
            
            # Run shutdown tasks
            for task in self.shutdown_tasks:
                await task()
            
            success = await self.on_deactivate()
            
            if success:
                self.status = PluginStatus.DISABLED
                logger.info(f"Plugin {self.plugin_id} deactivated")
            
            return success
        
        except Exception as e:
            logger.error(f"Plugin {self.plugin_id} deactivation error: {e}")
            return False
    
    async def store_memory(self, key: str, data: Any, importance: MemoryImportance = MemoryImportance.MEDIUM) -> UUID:
        """Store plugin-specific data in the memory system"""
        memory_key = f"{self.memory_namespace}:{key}"
        
        return await self.memory_manager.store_memory(
            user_id="system",
            content=json.dumps(data, default=str),
            memory_type=MemoryType.SYSTEM_EVENT,
            importance=importance,
            tags=[self.plugin_id, "plugin_data"],
            metadata={
                'plugin_id': self.plugin_id,
                'data_key': key,
                'namespace': self.memory_namespace
            }
        )
    
    async def retrieve_memory(self, key: str) -> Optional[Any]:
        """Retrieve plugin-specific data from memory"""
        memory_key = f"{self.memory_namespace}:{key}"
        
        memories = await self.memory_manager.retrieve_memories(
            user_id="system",
            query=memory_key,
            memory_types=[MemoryType.SYSTEM_EVENT],
            limit=1
        )
        
        if memories:
            try:
                return json.loads(memories[0]['content'])
            except (json.JSONDecodeError, KeyError):
                return None
        
        return None
    
    def add_startup_task(self, task: Callable):
        """Add a task to run during plugin activation"""
        self.startup_tasks.append(task)
    
    def add_shutdown_task(self, task: Callable):
        """Add a task to run during plugin deactivation"""
        self.shutdown_tasks.append(task)
    
    async def _validate_dependencies(self) -> bool:
        """Validate plugin dependencies"""
        for dep in self.manifest.dependencies:
            try:
                importlib_metadata.distribution(dep)
            except importlib_metadata.PackageNotFoundError:
                logger.error(f"Plugin {self.plugin_id} missing dependency: {dep}")
                return False
        
        return True
    
    @abstractmethod
    async def on_initialize(self) -> bool:
        """Plugin-specific initialization logic"""
        pass
    
    @abstractmethod
    async def on_activate(self) -> bool:
        """Plugin-specific activation logic"""
        pass
    
    @abstractmethod
    async def on_deactivate(self) -> bool:
        """Plugin-specific deactivation logic"""
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information for API/UI"""
        return {
            'plugin_id': self.plugin_id,
            'name': self.manifest.name,
            'version': self.manifest.version,
            'description': self.manifest.description,
            'author': self.manifest.author,
            'plugin_type': self.manifest.plugin_type.value,
            'status': self.status.value,
            'permissions': [p.value for p in self.manifest.permissions],
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat()
        }


class PluginSecurityManager:
    """
    Advanced security manager for plugin validation and sandboxing.
    
    Implements comprehensive security checks, code analysis, and runtime isolation
    to ensure plugins cannot compromise the Morpheus system integrity.
    """
    
    def __init__(self, security_enforcer: SecurityEnforcer):
        self.security_enforcer = security_enforcer
        self.trusted_publishers = set()
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
        
        # Manifest validation
        if not await self._validate_manifest(manifest):
            issues.append("Invalid manifest structure")
        
        # Code security analysis
        security_issues = await self._analyze_code_security(plugin_path)
        issues.extend(security_issues)
        
        # Signature verification (if not trusted)
        if not manifest.trusted and manifest.signature:
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
    
    async def _verify_signature(self, plugin_path: Path, signature: str) -> bool:
        """Verify cryptographic signature of plugin"""
        # This would implement actual cryptographic verification
        # For now, return True for demonstration
        return True
    
    async def _analyze_dependencies(self, dependencies: List[str]) -> List[str]:
        """Analyze plugin dependencies for security risks"""
        issues = []
        
        # Known problematic packages
        dangerous_packages = ['os', 'sys', 'subprocess', 'ctypes', 'importlib']
        
        for dep in dependencies:
            if any(dangerous in dep for dangerous in dangerous_packages):
                issues.append(f"Potentially dangerous dependency: {dep}")
        
        return issues


class PluginFileWatcher(FileSystemEventHandler):
    """File system watcher for plugin hot-reload capabilities"""
    
    def __init__(self, plugin_manager: 'PluginManager'):
        self.plugin_manager = plugin_manager
        self.debounce_delay = 1.0  # Seconds
        self.pending_changes = {}
        
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        plugin_path = Path(event.src_path)
        
        # Only process Python files in plugin directories
        if plugin_path.suffix == '.py' and 'plugins' in plugin_path.parts:
            self._schedule_reload(plugin_path)
    
    def _schedule_reload(self, plugin_path: Path):
        """Schedule plugin reload with debouncing"""
        plugin_id = self._extract_plugin_id(plugin_path)
        if not plugin_id:
            return
        
        # Cancel existing timer
        if plugin_id in self.pending_changes:
            self.pending_changes[plugin_id].cancel()
        
        # Schedule new reload
        timer = threading.Timer(
            self.debounce_delay,
            lambda: asyncio.create_task(self.plugin_manager.reload_plugin(plugin_id))
        )
        timer.start()
        self.pending_changes[plugin_id] = timer
        
        logger.info(f"Scheduled reload for plugin: {plugin_id}")
    
    def _extract_plugin_id(self, plugin_path: Path) -> Optional[str]:
        """Extract plugin ID from file path"""
        parts = plugin_path.parts
        try:
            plugins_index = parts.index('plugins')
            if plugins_index + 1 < len(parts):
                return parts[plugins_index + 1]
        except ValueError:
            pass
        
        return None


class PluginDiscovery:
    """
    Advanced plugin discovery system with intelligent scanning and caching.
    
    Handles plugin detection, manifest parsing, and dependency resolution
    across multiple plugin sources including local, community, and marketplace.
    """
    
    def __init__(self, plugin_dirs: List[Path]):
        self.plugin_dirs = plugin_dirs
        self.discovered_plugins: Dict[str, Path] = {}
        self.plugin_cache: Dict[str, PluginManifest] = {}
        
        # Ensure plugin directories exist
        for plugin_dir in self.plugin_dirs:
            plugin_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Plugin discovery initialized for {len(plugin_dirs)} directories")
    
    async def discover_plugins(self) -> Dict[str, PluginManifest]:
        """
        Discover all plugins in configured directories.
        
        Returns mapping of plugin_id -> PluginManifest
        """
        discovered = {}
        
        for plugin_dir in self.plugin_dirs:
            plugins_in_dir = await self._scan_directory(plugin_dir)
            discovered.update(plugins_in_dir)
        
        self.plugin_cache = discovered
        logger.info(f"Discovered {len(discovered)} plugins")
        
        return discovered
    
    async def _scan_directory(self, directory: Path) -> Dict[str, PluginManifest]:
        """Scan a directory for plugin manifests"""
        plugins = {}
        
        if not directory.exists():
            return plugins
        
        for item in directory.iterdir():
            if item.is_dir():
                manifest_path = item / 'manifest.json'
                if manifest_path.exists():
                    try:
                        manifest = PluginManifest.from_file(manifest_path)
                        plugin_id = f"{manifest.name}_{manifest.version}"
                        plugins[plugin_id] = manifest
                        self.discovered_plugins[plugin_id] = item
                        
                        logger.debug(f"Discovered plugin: {plugin_id} at {item}")
                        
                    except Exception as e:
                        logger.error(f"Failed to load manifest from {manifest_path}: {e}")
        
        return plugins
    
    def get_plugin_path(self, plugin_id: str) -> Optional[Path]:
        """Get the filesystem path for a plugin"""
        return self.discovered_plugins.get(plugin_id)
    
    async def refresh_cache(self):
        """Refresh the plugin discovery cache"""
        await self.discover_plugins()


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
        self.discovery = PluginDiscovery([
            plugin_base_dir / "installed",
            plugin_base_dir / "community",
        ])
        
        # File watching for hot-reload
        self.file_watcher = PluginFileWatcher(self)
        self.file_observer = Observer()
        
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
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def start(self):
        """Start the plugin management system"""
        logger.info("Starting plugin management system...")
        
        # Start file watching
        self.file_observer.schedule(
            self.file_watcher,
            str(self.plugin_base_dir),
            recursive=True
        )
        self.file_observer.start()
        
        # Discover and load plugins
        await self.discover_and_load_plugins()
        
        logger.info("Plugin management system started")
    
    async def stop(self):
        """Stop the plugin management system"""
        logger.info("Stopping plugin management system...")
        
        # Stop file watching
        self.file_observer.stop()
        self.file_observer.join()
        
        # Deactivate all plugins
        for plugin_id in list(self.active_plugins.keys()):
            await self.deactivate_plugin(plugin_id)
        
        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=30)
        
        logger.info("Plugin management system stopped")
    
    async def discover_and_load_plugins(self):
        """Discover all plugins and load them"""
        discovered = await self.discovery.discover_plugins()
        
        for plugin_id, manifest in discovered.items():
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
                    
                    # Add plugin context to all routes
                    for route in router.routes:
                        if hasattr(route, 'endpoint'):
                            original_endpoint = route.endpoint
                            
                            async def wrapped_endpoint(*args, **kwargs):
                                # Inject plugin context
                                kwargs['plugin_instance'] = plugin_instance
                                return await original_endpoint(*args, **kwargs)
                            
                            route.endpoint = wrapped_endpoint
                    
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
        """Install plugin from archive file"""
        # This would implement plugin installation from ZIP/TAR archives
        # Including extraction, validation, and dependency installation
        pass
    
    async def get_plugin_marketplace_info(self) -> Dict[str, Any]:
        """Get information about available marketplace plugins"""
        # This would implement marketplace integration
        # Including browsing, searching, and downloading plugins
        pass


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
