"""
MORPHEUS CHAT - Advanced Plugin Hot-Reload & State Management System
Production-grade hot-reload with state preservation, dependency tracking, and recursive consciousness integration.

Architectural Features:
- Sophisticated state serialization/deserialization across reloads
- Dependency graph analysis with cascade reload management
- Memory-coherent plugin state preservation via ChromaDB
- Zero-downtime reloading with graceful fallback mechanisms
- Recursive consciousness state preservation during transitions
"""

import asyncio
import pickle
import threading
import weakref
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Callable, Union
from uuid import UUID, uuid4
import logging
import json
import hashlib
import importlib
import sys
from enum import Enum

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

from host_protocols import MemoryManager, MemoryType, MemoryImportance

logger = logging.getLogger(__name__)


class ReloadType(str, Enum):
    """Types of reload operations with different impact levels"""
    HOT_RELOAD = "hot_reload"           # In-place reload with state preservation
    WARM_RELOAD = "warm_reload"         # Restart with state restoration
    COLD_RELOAD = "cold_reload"         # Complete restart, lose transient state
    CASCADE_RELOAD = "cascade_reload"   # Reload plugin and all dependents


class StatePreservationLevel(str, Enum):
    """Levels of state preservation during reload"""
    FULL = "full"           # Preserve all state including memory and UI
    PARTIAL = "partial"     # Preserve core state, reset UI
    MINIMAL = "minimal"     # Preserve only essential configuration
    NONE = "none"          # Complete reset


@dataclass
class PluginRuntimeSnapshot:
    """Runtime snapshot preserved across reloads.

    Distinct from plugin_base.PluginState, which is the lifecycle enum.
    Renamed during PACKET-002 lineage convergence.
    """
    plugin_id: str
    version: str
    state_data: Dict[str, Any] = field(default_factory=dict)
    memory_references: List[UUID] = field(default_factory=list)
    active_sessions: Set[str] = field(default_factory=set)
    ui_state: Dict[str, Any] = field(default_factory=dict)
    configuration: Dict[str, Any] = field(default_factory=dict)
    runtime_metrics: Dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    serialization_format: str = "json"  # json, pickle, custom
    
    def serialize(self) -> bytes:
        """Serialize state for persistence. JSON-only — pickle is excluded
        because it enables arbitrary code execution during deserialization."""
        if self.serialization_format == "pickle":
            self.serialization_format = "json"  # force safe serialization
        # JSON serialization with datetime handling
        if True:
            data = {
                'plugin_id': self.plugin_id,
                'version': self.version,
                'state_data': self.state_data,
                'memory_references': [str(ref) for ref in self.memory_references],
                'active_sessions': list(self.active_sessions),
                'ui_state': self.ui_state,
                'configuration': self.configuration,
                'runtime_metrics': self.runtime_metrics,
                'created_at': self.created_at.isoformat(),
                'serialization_format': self.serialization_format
            }
            return json.dumps(data, default=str).encode('utf-8')
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'PluginRuntimeSnapshot':
        """Deserialize state from persistence.

        JSON-only deserialization. pickle.loads is deliberately excluded
        because it executes arbitrary code — a plugin could craft a
        serialized state payload that runs during deserialization.
        """
        try:
            json_data = json.loads(data.decode('utf-8'))
            return cls(
                plugin_id=json_data['plugin_id'],
                version=json_data['version'],
                state_data=json_data.get('state_data', {}),
                memory_references=[UUID(ref) for ref in json_data.get('memory_references', [])],
                active_sessions=set(json_data.get('active_sessions', [])),
                ui_state=json_data.get('ui_state', {}),
                configuration=json_data.get('configuration', {}),
                runtime_metrics=json_data.get('runtime_metrics', {}),
                created_at=datetime.fromisoformat(json_data.get('created_at', datetime.now(timezone.utc).isoformat())),
                serialization_format=json_data.get('serialization_format', 'json')
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise ValueError(f"Failed to deserialize plugin state: {exc}") from exc


class DependencyGraph:
    """
    Sophisticated dependency tracking and cascade management system.
    
    Manages complex plugin interdependencies with cycle detection,
    topological sorting, and cascade impact analysis.
    """
    
    def __init__(self):
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)  # plugin -> dependencies
        self.dependents: Dict[str, Set[str]] = defaultdict(set)    # plugin -> dependents
        self.lock = threading.RLock()
        
    def add_dependency(self, plugin_id: str, dependency_id: str):
        """Add a dependency relationship"""
        with self.lock:
            self.dependencies[plugin_id].add(dependency_id)
            self.dependents[dependency_id].add(plugin_id)
    
    def remove_dependency(self, plugin_id: str, dependency_id: str):
        """Remove a dependency relationship"""
        with self.lock:
            self.dependencies[plugin_id].discard(dependency_id)
            self.dependents[dependency_id].discard(plugin_id)
    
    def get_dependencies(self, plugin_id: str) -> Set[str]:
        """Get direct dependencies of a plugin"""
        return self.dependencies[plugin_id].copy()
    
    def get_dependents(self, plugin_id: str) -> Set[str]:
        """Get direct dependents of a plugin"""
        return self.dependents[plugin_id].copy()
    
    def get_all_dependencies(self, plugin_id: str) -> Set[str]:
        """Get all transitive dependencies (topologically sorted)"""
        visited = set()
        result = []
        
        def dfs(current_id: str):
            if current_id in visited:
                return
            visited.add(current_id)
            
            for dep_id in self.dependencies[current_id]:
                dfs(dep_id)
            
            result.append(current_id)
        
        dfs(plugin_id)
        result.remove(plugin_id)  # Remove self
        return set(result)
    
    def get_all_dependents(self, plugin_id: str) -> Set[str]:
        """Get all transitive dependents"""
        visited = set()
        result = set()
        
        def dfs(current_id: str):
            if current_id in visited:
                return
            visited.add(current_id)
            
            for dep_id in self.dependents[current_id]:
                result.add(dep_id)
                dfs(dep_id)
        
        dfs(plugin_id)
        return result
    
    def detect_cycles(self) -> List[List[str]]:
        """Detect dependency cycles"""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(plugin_id: str, path: List[str]) -> bool:
            if plugin_id in rec_stack:
                # Found cycle
                cycle_start = path.index(plugin_id)
                cycles.append(path[cycle_start:] + [plugin_id])
                return True
            
            if plugin_id in visited:
                return False
            
            visited.add(plugin_id)
            rec_stack.add(plugin_id)
            
            for dep_id in self.dependencies[plugin_id]:
                if dfs(dep_id, path + [plugin_id]):
                    return True
            
            rec_stack.remove(plugin_id)
            return False
        
        for plugin_id in self.dependencies:
            if plugin_id not in visited:
                dfs(plugin_id, [])
        
        return cycles
    
    def get_reload_order(self, plugin_id: str) -> List[str]:
        """Get optimal reload order for plugin and its dependents"""
        affected = self.get_all_dependents(plugin_id)
        affected.add(plugin_id)
        
        # Topological sort of affected plugins
        in_degree = {pid: 0 for pid in affected}
        
        for pid in affected:
            for dep in self.dependencies[pid]:
                if dep in affected:
                    in_degree[pid] += 1
        
        queue = deque([pid for pid in affected if in_degree[pid] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            for dependent in self.dependents[current]:
                if dependent in affected:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        return result


class StateManager:
    """
    Advanced state management system for plugin hot-reload operations.
    
    Implements sophisticated state serialization, memory coherence,
    and recursive consciousness preservation during plugin transitions.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.plugin_states: Dict[str, PluginRuntimeSnapshot] = {}
        self.state_lock = threading.RLock()
        self.preservation_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
    async def capture_plugin_state(
        self, 
        plugin_id: str, 
        plugin_instance: Any,
        preservation_level: StatePreservationLevel = StatePreservationLevel.FULL
    ) -> PluginRuntimeSnapshot:
        """
        Capture comprehensive plugin state for preservation during reload.
        
        Implements deep state introspection with memory coherence preservation.
        """
        try:
            state = PluginRuntimeSnapshot(
                plugin_id=plugin_id,
                version=getattr(plugin_instance, 'version', '1.0.0')
            )
            
            # Capture plugin-specific state
            if hasattr(plugin_instance, 'get_state'):
                state.state_data = await plugin_instance.get_state()
            else:
                # Auto-capture serializable attributes
                state.state_data = self._auto_capture_state(plugin_instance)
            
            # Capture memory references
            if preservation_level in [StatePreservationLevel.FULL, StatePreservationLevel.PARTIAL]:
                state.memory_references = await self._capture_memory_references(plugin_id)
            
            # Capture active sessions
            if hasattr(plugin_instance, 'active_sessions'):
                state.active_sessions = set(plugin_instance.active_sessions)
            
            # Capture UI state
            if preservation_level == StatePreservationLevel.FULL:
                state.ui_state = await self._capture_ui_state(plugin_id)
            
            # Capture configuration
            if hasattr(plugin_instance, 'configuration'):
                state.configuration = plugin_instance.configuration.copy()
            
            # Capture runtime metrics
            if hasattr(plugin_instance, 'get_metrics'):
                state.runtime_metrics = await plugin_instance.get_metrics()
            
            # Run custom preservation callbacks
            for callback in self.preservation_callbacks[plugin_id]:
                try:
                    await callback(state, plugin_instance)
                except Exception as e:
                    logger.warning(f"State preservation callback failed for {plugin_id}: {e}")
            
            # Store state in memory system for persistence
            await self._persist_state(state)
            
            with self.state_lock:
                self.plugin_states[plugin_id] = state
            
            logger.info(f"Captured state for plugin {plugin_id} with {len(state.state_data)} data items")
            return state
            
        except Exception as e:
            logger.error(f"Failed to capture state for plugin {plugin_id}: {e}")
            # Return minimal state
            return PluginRuntimeSnapshot(plugin_id=plugin_id, version='unknown')
    
    def _auto_capture_state(self, plugin_instance: Any) -> Dict[str, Any]:
        """Automatically capture serializable plugin attributes"""
        state_data = {}
        
        for attr_name in dir(plugin_instance):
            if attr_name.startswith('_'):
                continue
            
            try:
                attr_value = getattr(plugin_instance, attr_name)
                
                # Skip methods and functions
                if callable(attr_value):
                    continue
                
                # Try to serialize the attribute
                json.dumps(attr_value, default=str)
                state_data[attr_name] = attr_value
                
            except (TypeError, AttributeError):
                # Skip non-serializable attributes
                continue
        
        return state_data
    
    async def _capture_memory_references(self, plugin_id: str) -> List[UUID]:
        """Capture plugin-related memory references"""
        try:
            memories = await self.memory_manager.retrieve_memories(
                user_id="system",
                query=f"plugin:{plugin_id}",
                limit=1000
            )
            
            return [UUID(memory['memory_id']) for memory in memories]
            
        except Exception as e:
            logger.warning(f"Failed to capture memory references for {plugin_id}: {e}")
            return []
    
    async def _capture_ui_state(self, plugin_id: str) -> Dict[str, Any]:
        """Capture plugin UI state (placeholder for future WebSocket integration)"""
        # This would integrate with the frontend to capture UI component states
        # For now, return empty dict
        return {}
    
    async def _persist_state(self, state: PluginRuntimeSnapshot):
        """Persist plugin state in memory system"""
        try:
            await self.memory_manager.store_memory(
                user_id="system",
                content=state.serialize().decode('utf-8', errors='replace'),
                memory_type=MemoryType.SYSTEM_EVENT,
                importance=MemoryImportance.HIGH,
                tags=[state.plugin_id, "plugin_state", "hot_reload"],
                metadata={
                    'plugin_id': state.plugin_id,
                    'version': state.version,
                    'state_type': 'plugin_preservation',
                    'created_at': state.created_at.isoformat()
                }
            )
        except Exception as e:
            logger.warning(f"Failed to persist state for {state.plugin_id}: {e}")
    
    async def restore_plugin_state(
        self, 
        plugin_id: str, 
        plugin_instance: Any,
        state: Optional[PluginRuntimeSnapshot] = None
    ) -> bool:
        """
        Restore plugin state after reload.
        
        Implements intelligent state restoration with validation and fallback.
        """
        try:
            if state is None:
                with self.state_lock:
                    state = self.plugin_states.get(plugin_id)
            
            if not state:
                logger.info(f"No saved state found for plugin {plugin_id}")
                return False
            
            # Restore plugin-specific state
            if hasattr(plugin_instance, 'set_state') and state.state_data:
                await plugin_instance.set_state(state.state_data)
            else:
                # Auto-restore serializable attributes
                self._auto_restore_state(plugin_instance, state.state_data)
            
            # Restore active sessions
            if hasattr(plugin_instance, 'active_sessions') and state.active_sessions:
                plugin_instance.active_sessions = state.active_sessions
            
            # Restore configuration
            if hasattr(plugin_instance, 'configuration') and state.configuration:
                plugin_instance.configuration.update(state.configuration)
            
            # Restore memory context (memory references remain valid)
            if state.memory_references:
                await self._restore_memory_context(plugin_id, state.memory_references)
            
            logger.info(f"Restored state for plugin {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore state for plugin {plugin_id}: {e}")
            return False
    
    def _auto_restore_state(self, plugin_instance: Any, state_data: Dict[str, Any]):
        """Automatically restore serializable plugin attributes"""
        for attr_name, attr_value in state_data.items():
            try:
                if hasattr(plugin_instance, attr_name):
                    setattr(plugin_instance, attr_name, attr_value)
            except Exception as e:
                logger.warning(f"Failed to restore attribute {attr_name}: {e}")
    
    async def _restore_memory_context(self, plugin_id: str, memory_refs: List[UUID]):
        """Restore plugin memory context"""
        # Memory references remain valid, no action needed
        # Could implement memory validation here if needed
        pass
    
    def register_preservation_callback(self, plugin_id: str, callback: Callable):
        """Register custom state preservation callback"""
        self.preservation_callbacks[plugin_id].append(callback)
    
    def clear_plugin_state(self, plugin_id: str):
        """Clear stored state for a plugin"""
        with self.state_lock:
            self.plugin_states.pop(plugin_id, None)
        
        # Clear callbacks
        self.preservation_callbacks.pop(plugin_id, None)


class HotReloadEngine:
    """
    Core hot-reload engine with sophisticated change detection and reload orchestration.
    
    Implements zero-downtime reloading with cascade management, state preservation,
    and recursive consciousness integration.
    """
    
    def __init__(self, plugin_manager, memory_manager: MemoryManager):
        self.plugin_manager = plugin_manager
        self.memory_manager = memory_manager
        self.state_manager = StateManager(memory_manager)
        self.dependency_graph = DependencyGraph()
        
        # File system monitoring
        self.observer = Observer()
        self.file_handler = PluginFileHandler(self)
        
        # Reload management
        self.reload_queue = asyncio.Queue()
        self.reload_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hot-reload")
        self.active_reloads: Set[str] = set()
        self.reload_lock = asyncio.Lock()
        
        # Performance tracking
        self.reload_metrics: Dict[str, Dict[str, float]] = defaultdict(dict)
        
    async def start_monitoring(self, plugin_dirs: List[Path]):
        """Start file system monitoring for hot-reload"""
        for plugin_dir in plugin_dirs:
            self.observer.schedule(
                self.file_handler,
                str(plugin_dir),
                recursive=True
            )
        
        self.observer.start()
        
        # Start reload processor
        asyncio.create_task(self._process_reload_queue())
        
        logger.info(f"Hot-reload monitoring started for {len(plugin_dirs)} directories")
    
    async def stop_monitoring(self):
        """Stop file system monitoring"""
        self.observer.stop()
        self.observer.join()
        
        self.reload_executor.shutdown(wait=True, timeout=30)
        
        logger.info("Hot-reload monitoring stopped")
    
    async def schedule_reload(
        self, 
        plugin_id: str, 
        reload_type: ReloadType = ReloadType.HOT_RELOAD,
        delay: float = 1.0
    ):
        """Schedule a plugin reload with debouncing"""
        await asyncio.sleep(delay)  # Debounce file system events
        
        reload_info = {
            'plugin_id': plugin_id,
            'reload_type': reload_type,
            'timestamp': datetime.now(timezone.utc),
            'trigger': 'file_change'
        }
        
        await self.reload_queue.put(reload_info)
        logger.debug(f"Scheduled {reload_type.value} reload for {plugin_id}")
    
    async def _process_reload_queue(self):
        """Process queued reload operations"""
        while True:
            try:
                reload_info = await self.reload_queue.get()
                
                plugin_id = reload_info['plugin_id']
                reload_type = ReloadType(reload_info['reload_type'])
                
                # Skip if already reloading
                if plugin_id in self.active_reloads:
                    continue
                
                async with self.reload_lock:
                    self.active_reloads.add(plugin_id)
                
                try:
                    success = await self._execute_reload(plugin_id, reload_type)
                    
                    # Update metrics
                    self.reload_metrics[plugin_id]['last_reload'] = datetime.now(timezone.utc).timestamp()
                    self.reload_metrics[plugin_id]['success_count'] = self.reload_metrics[plugin_id].get('success_count', 0) + (1 if success else 0)
                    self.reload_metrics[plugin_id]['total_count'] = self.reload_metrics[plugin_id].get('total_count', 0) + 1
                    
                finally:
                    self.active_reloads.discard(plugin_id)
                
            except Exception as e:
                logger.error(f"Error processing reload queue: {e}")
    
    async def _execute_reload(self, plugin_id: str, reload_type: ReloadType) -> bool:
        """Execute plugin reload with appropriate strategy"""
        start_time = datetime.now(timezone.utc)
        
        try:
            if reload_type == ReloadType.HOT_RELOAD:
                success = await self._hot_reload(plugin_id)
            elif reload_type == ReloadType.WARM_RELOAD:
                success = await self._warm_reload(plugin_id)
            elif reload_type == ReloadType.COLD_RELOAD:
                success = await self._cold_reload(plugin_id)
            elif reload_type == ReloadType.CASCADE_RELOAD:
                success = await self._cascade_reload(plugin_id)
            else:
                logger.error(f"Unknown reload type: {reload_type}")
                return False
            
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            if success:
                logger.info(f"Successfully reloaded {plugin_id} ({reload_type.value}) in {elapsed:.2f}s")
            else:
                logger.warning(f"Failed to reload {plugin_id} ({reload_type.value}) after {elapsed:.2f}s")
            
            return success
            
        except Exception as e:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Exception during {reload_type.value} reload of {plugin_id} after {elapsed:.2f}s: {e}")
            return False
    
    async def _hot_reload(self, plugin_id: str) -> bool:
        """Hot reload with full state preservation"""
        plugin_instance = self.plugin_manager.active_plugins.get(plugin_id)
        if not plugin_instance:
            logger.warning(f"Plugin {plugin_id} not active for hot reload")
            return False
        
        try:
            # 1. Capture current state
            state = await self.state_manager.capture_plugin_state(
                plugin_id, 
                plugin_instance, 
                StatePreservationLevel.FULL
            )
            
            # 2. Gracefully deactivate (without full unload)
            await plugin_instance.deactivate()
            
            # 3. Reload module
            module_name = f"morpheus_plugin_{plugin_id}"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            
            # 4. Create new instance
            plugin_module = sys.modules[module_name]
            plugin_class = getattr(plugin_module, 'Plugin')
            new_instance = plugin_class(plugin_id, plugin_instance.manifest, self.memory_manager)
            
            # 5. Initialize new instance
            if not await new_instance.initialize():
                logger.error(f"Hot reload initialization failed for {plugin_id}")
                return False
            
            # 6. Restore state
            await self.state_manager.restore_plugin_state(plugin_id, new_instance, state)
            
            # 7. Activate new instance
            if not await new_instance.activate():
                logger.error(f"Hot reload activation failed for {plugin_id}")
                return False
            
            # 8. Replace in plugin manager
            self.plugin_manager.active_plugins[plugin_id] = new_instance
            
            return True
            
        except Exception as e:
            logger.error(f"Hot reload failed for {plugin_id}: {e}")
            # Attempt to restore original instance
            try:
                await plugin_instance.activate()
            except:
                pass
            return False
    
    async def _warm_reload(self, plugin_id: str) -> bool:
        """Warm reload with partial state preservation"""
        # Similar to hot reload but with StatePreservationLevel.PARTIAL
        plugin_instance = self.plugin_manager.active_plugins.get(plugin_id)
        if not plugin_instance:
            return await self.plugin_manager.load_plugin(plugin_id)
        
        state = await self.state_manager.capture_plugin_state(
            plugin_id, 
            plugin_instance, 
            StatePreservationLevel.PARTIAL
        )
        
        # Full unload and reload cycle
        await self.plugin_manager.unload_plugin(plugin_id)
        success = await self.plugin_manager.load_plugin(plugin_id)
        
        if success:
            new_instance = self.plugin_manager.active_plugins[plugin_id]
            await self.state_manager.restore_plugin_state(plugin_id, new_instance, state)
        
        return success
    
    async def _cold_reload(self, plugin_id: str) -> bool:
        """Cold reload with no state preservation"""
        await self.plugin_manager.unload_plugin(plugin_id)
        return await self.plugin_manager.load_plugin(plugin_id)
    
    async def _cascade_reload(self, plugin_id: str) -> bool:
        """Cascade reload affecting dependents"""
        reload_order = self.dependency_graph.get_reload_order(plugin_id)
        
        all_success = True
        for dependent_id in reload_order:
            success = await self._hot_reload(dependent_id)
            if not success:
                all_success = False
                logger.warning(f"Cascade reload failed for dependent {dependent_id}")
        
        return all_success
    
    def update_dependencies(self, plugin_id: str, dependencies: List[str]):
        """Update dependency graph for a plugin"""
        # Clear existing dependencies
        current_deps = self.dependency_graph.get_dependencies(plugin_id)
        for dep in current_deps:
            self.dependency_graph.remove_dependency(plugin_id, dep)
        
        # Add new dependencies
        for dep in dependencies:
            self.dependency_graph.add_dependency(plugin_id, dep)
    
    def get_reload_metrics(self) -> Dict[str, Any]:
        """Get hot-reload performance metrics"""
        return {
            'total_plugins': len(self.reload_metrics),
            'active_reloads': len(self.active_reloads),
            'plugin_metrics': dict(self.reload_metrics),
            'dependency_cycles': self.dependency_graph.detect_cycles()
        }


class PluginFileHandler(FileSystemEventHandler):
    """Enhanced file system event handler with intelligent change detection"""
    
    def __init__(self, reload_engine: HotReloadEngine):
        self.reload_engine = reload_engine
        self.debounce_timers: Dict[str, asyncio.Task] = {}
        self.file_hashes: Dict[str, str] = {}
        
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Only process relevant files
        if file_path.suffix not in ['.py', '.json', '.yaml', '.yml']:
            return
        
        # Extract plugin ID from path
        plugin_id = self._extract_plugin_id(file_path)
        if not plugin_id:
            return
        
        # Check if file actually changed (prevent duplicate events)
        if not self._file_changed(file_path):
            return
        
        # Determine reload type based on file
        reload_type = self._determine_reload_type(file_path)
        
        # Schedule reload with debouncing
        self._schedule_debounced_reload(plugin_id, reload_type)
    
    def _extract_plugin_id(self, file_path: Path) -> Optional[str]:
        """Extract plugin ID from file path"""
        parts = file_path.parts
        try:
            if 'morpheus_plugins' in parts:
                plugins_index = parts.index('morpheus_plugins')
                if plugins_index + 2 < len(parts):
                    return parts[plugins_index + 2]  # Skip 'morpheus_plugins/installed/'
        except (ValueError, IndexError):
            pass
        
        return None
    
    def _file_changed(self, file_path: Path) -> bool:
        """Check if file content actually changed"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            file_hash = hashlib.sha256(content).hexdigest()
            old_hash = self.file_hashes.get(str(file_path))
            
            self.file_hashes[str(file_path)] = file_hash
            
            return old_hash != file_hash
        except:
            return True  # Assume changed if we can't read
    
    def _determine_reload_type(self, file_path: Path) -> ReloadType:
        """Determine appropriate reload type based on file"""
        if file_path.name == 'manifest.json':
            return ReloadType.WARM_RELOAD  # Manifest changes require warm reload
        elif file_path.suffix == '.py':
            return ReloadType.HOT_RELOAD   # Python files can be hot reloaded
        else:
            return ReloadType.WARM_RELOAD  # Other files need warm reload
    
    def _schedule_debounced_reload(self, plugin_id: str, reload_type: ReloadType):
        """Schedule reload with debouncing to prevent reload storms"""
        # Cancel existing timer
        if plugin_id in self.debounce_timers:
            self.debounce_timers[plugin_id].cancel()
        
        # Schedule new reload
        self.debounce_timers[plugin_id] = asyncio.create_task(
            self.reload_engine.schedule_reload(plugin_id, reload_type, delay=1.0)
        )


# Integration with main plugin manager
class HotReloadIntegration:
    """Integration layer between plugin manager and hot-reload system"""
    
    def __init__(self, plugin_manager, memory_manager: MemoryManager):
        self.plugin_manager = plugin_manager
        self.hot_reload_engine = HotReloadEngine(plugin_manager, memory_manager)
        
    async def initialize(self):
        """Initialize hot-reload integration"""
        # Start monitoring plugin directories
        plugin_dirs = [
            self.plugin_manager.plugin_base_dir / "installed",
            self.plugin_manager.plugin_base_dir / "community"
        ]
        
        await self.hot_reload_engine.start_monitoring(plugin_dirs)
        
        # Hook into plugin loading to update dependencies
        original_load = self.plugin_manager.load_plugin
        
        async def enhanced_load(plugin_id: str) -> bool:
            success = await original_load(plugin_id)
            if success:
                # Update dependency graph
                plugin_instance = self.plugin_manager.active_plugins[plugin_id]
                dependencies = getattr(plugin_instance.manifest, 'dependencies', [])
                self.hot_reload_engine.update_dependencies(plugin_id, dependencies)
            return success
        
        self.plugin_manager.load_plugin = enhanced_load
        
    async def shutdown(self):
        """Shutdown hot-reload integration"""
        await self.hot_reload_engine.stop_monitoring()


# Usage example
async def setup_hot_reload(plugin_manager, memory_manager: MemoryManager) -> HotReloadIntegration:
    """Setup hot-reload system with plugin manager"""
    integration = HotReloadIntegration(plugin_manager, memory_manager)
    await integration.initialize()
    return integration
