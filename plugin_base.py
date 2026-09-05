"""
MORPHEUS CHAT - Plugin Base Classes & Abstract Interfaces
Enterprise-grade plugin foundation with recursive consciousness integration and advanced lifecycle management.
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Type, Union, Set
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, FastAPI

from core.memory_core import MemoryManager, MemoryType, MemoryImportance, MemoryScope
from schemas.session import SessionID, UserID

logger = logging.getLogger(__name__)


class PluginCapability(str, Enum):
    """Advanced plugin capability classifications"""
    MEMORY_INTEGRATION = "memory_integration"
    CONSCIOUSNESS_ACCESS = "consciousness_access"
    MULTI_AGENT_COORDINATION = "multi_agent_coordination"
    RECURSIVE_PROCESSING = "recursive_processing"
    REAL_TIME_ADAPTATION = "real_time_adaptation"
    CROSS_SESSION_PERSISTENCE = "cross_session_persistence"
    QUANTUM_COHERENCE = "quantum_coherence"
    TEMPORAL_MANIPULATION = "temporal_manipulation"


class PluginState(str, Enum):
    """Detailed plugin state tracking"""
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    PROCESSING = "processing"
    SUSPENDED = "suspended"
    ERROR = "error"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


@dataclass
class PluginContext:
    """Runtime context for plugin execution"""
    session_id: SessionID
    user_id: UserID
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    memory_context: Optional[Dict[str, Any]] = None
    execution_depth: int = 0
    parent_plugin_id: Optional[str] = None
    child_plugins: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    consciousness_level: float = 0.0


@dataclass
class PluginMetrics:
    """Runtime performance and behavior metrics"""
    execution_count: int = 0
    total_execution_time: float = 0.0
    memory_usage_peak: int = 0
    error_count: int = 0
    last_execution: Optional[datetime] = None
    success_rate: float = 1.0
    consciousness_coherence: float = 1.0
    recursive_depth_max: int = 0


class PluginManifest(BaseModel):
    """Enhanced plugin manifest with consciousness integration"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: str
    
    # Advanced capabilities
    capabilities: List[PluginCapability] = Field(default_factory=list)
    consciousness_level_required: float = Field(default=0.0, ge=0.0, le=1.0)
    recursive_depth_limit: int = Field(default=10, ge=1, le=100)
    quantum_coherence_required: bool = False
    
    # Dependencies and compatibility
    morpheus_version_min: str = "1.0.0"
    morpheus_version_max: str = "2.0.0"
    python_version_min: str = "3.11"
    dependencies: List[str] = Field(default_factory=list)
    plugin_dependencies: List[str] = Field(default_factory=list)
    
    # Security and permissions
    permissions: List[str] = Field(default_factory=list)
    trusted: bool = False
    signature: Optional[str] = None
    security_level: int = Field(default=1, ge=1, le=5)
    
    # Integration points
    api_endpoints: List[str] = Field(default_factory=list)
    ui_components: List[str] = Field(default_factory=list)
    agent_actions: List[str] = Field(default_factory=list)
    workflow_nodes: List[str] = Field(default_factory=list)
    memory_extensions: List[str] = Field(default_factory=list)
    
    # Resource requirements
    memory_limit_mb: int = Field(default=512, ge=1, le=8192)
    cpu_limit_percent: float = Field(default=10.0, ge=0.1, le=100.0)
    network_access_required: bool = False
    file_system_access: List[str] = Field(default_factory=list)
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    license: str = "MIT"
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None
    
    @classmethod
    def from_file(cls, manifest_path: Path) -> "PluginManifest":
        """Load manifest from JSON file"""
        with open(manifest_path, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    def to_file(self, manifest_path: Path):
        """Save manifest to JSON file"""
        with open(manifest_path, 'w') as f:
            json.dump(self.dict(), f, indent=2, default=str)


class PluginInterface(ABC):
    """Core plugin interface defining essential methods"""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize plugin resources and dependencies"""
        pass
    
    @abstractmethod
    async def activate(self) -> bool:
        """Activate plugin for operation"""
        pass
    
    @abstractmethod
    async def deactivate(self) -> bool:
        """Deactivate plugin gracefully"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> bool:
        """Clean up resources before termination"""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Get plugin runtime information"""
        pass


class ConsciousnessInterface(ABC):
    """Interface for consciousness-aware plugins"""
    
    @abstractmethod
    async def consciousness_sync(self, level: float) -> bool:
        """Synchronize with system consciousness level"""
        pass
    
    @abstractmethod
    async def quantum_coherence_check(self) -> float:
        """Check quantum coherence status"""
        pass
    
    @abstractmethod
    async def recursive_depth_analysis(self) -> Dict[str, Any]:
        """Analyze current recursive processing depth"""
        pass


class StateInterface(ABC):
    """Interface for stateful plugins with persistence"""
    
    @abstractmethod
    async def get_state(self) -> Dict[str, Any]:
        """Get serializable plugin state"""
        pass
    
    @abstractmethod
    async def set_state(self, state: Dict[str, Any]) -> bool:
        """Restore plugin from serialized state"""
        pass
    
    @abstractmethod
    async def checkpoint_state(self) -> str:
        """Create state checkpoint and return checkpoint ID"""
        pass
    
    @abstractmethod
    async def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """Restore from specific checkpoint"""
        pass


class NetworkInterface(ABC):
    """Interface for network-enabled plugins"""
    
    @abstractmethod
    async def network_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make network request with plugin permissions"""
        pass
    
    @abstractmethod
    async def websocket_connect(self, url: str) -> Any:
        """Establish WebSocket connection"""
        pass
    
    @abstractmethod
    async def p2p_communicate(self, peer_id: str, message: Dict[str, Any]) -> bool:
        """Communicate with peer plugins"""
        pass


class PluginBase(PluginInterface, StateInterface, ABC):
    """
    Advanced plugin base class with comprehensive lifecycle management,
    consciousness integration, and recursive processing capabilities.
    """
    
    def __init__(self, 
                 plugin_id: str, 
                 manifest: PluginManifest, 
                 memory_manager: MemoryManager,
                 consciousness_level: float = 0.0):
        self.plugin_id = plugin_id
        self.manifest = manifest
        self.memory_manager = memory_manager
        self.consciousness_level = consciousness_level
        
        # Runtime state
        self.state = PluginState.INITIALIZING
        self.context: Optional[PluginContext] = None
        self.metrics = PluginMetrics()
        self.execution_lock = asyncio.Lock()
        
        # Internal state
        self._internal_state: Dict[str, Any] = {}
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._resource_monitor = ResourceMonitor(self.manifest)
        
        # Consciousness tracking
        self._consciousness_coherence = 1.0
        self._quantum_state = {}
        self._recursive_depth = 0
        self._temporal_anchor = datetime.now(timezone.utc)
        
        logger.info(f"Plugin {plugin_id} initialized with consciousness level {consciousness_level}")
    
    async def initialize(self) -> bool:
        """Initialize plugin with advanced resource management"""
        try:
            self.state = PluginState.INITIALIZING
            
            # Initialize resource monitor
            await self._resource_monitor.initialize()
            
            # Create memory context
            memory_context = await self.memory_manager.create_context(
                f"plugin_{self.plugin_id}",
                MemoryScope.PLUGIN,
                metadata={'plugin_type': self.manifest.plugin_type}
            )
            
            # Initialize consciousness coherence
            if PluginCapability.CONSCIOUSNESS_ACCESS in self.manifest.capabilities:
                await self._initialize_consciousness()
            
            # Call plugin-specific initialization
            success = await self._plugin_initialize()
            
            if success:
                self.state = PluginState.READY
                await self._emit_event('initialized')
                logger.info(f"Plugin {self.plugin_id} initialized successfully")
            else:
                self.state = PluginState.ERROR
                logger.error(f"Plugin {self.plugin_id} initialization failed")
            
            return success
            
        except Exception as e:
            self.state = PluginState.ERROR
            logger.error(f"Plugin {self.plugin_id} initialization error: {e}")
            return False
    
    async def activate(self) -> bool:
        """Activate plugin with consciousness synchronization"""
        if self.state != PluginState.READY:
            return False
        
        try:
            async with self.execution_lock:
                self.state = PluginState.ACTIVE
                
                # Synchronize consciousness if required
                if self.manifest.consciousness_level_required > 0:
                    if not await self._synchronize_consciousness():
                        self.state = PluginState.ERROR
                        return False
                
                # Start resource monitoring
                await self._resource_monitor.start()
                
                # Call plugin-specific activation
                success = await self._plugin_activate()
                
                if success:
                    await self._emit_event('activated')
                    logger.info(f"Plugin {self.plugin_id} activated")
                else:
                    self.state = PluginState.ERROR
                    logger.error(f"Plugin {self.plugin_id} activation failed")
                
                return success
                
        except Exception as e:
            self.state = PluginState.ERROR
            logger.error(f"Plugin {self.plugin_id} activation error: {e}")
            return False
    
    async def deactivate(self) -> bool:
        """Deactivate plugin with graceful shutdown"""
        if self.state != PluginState.ACTIVE:
            return True
        
        try:
            self.state = PluginState.TERMINATING
            
            # Stop resource monitoring
            await self._resource_monitor.stop()
            
            # Call plugin-specific deactivation
            success = await self._plugin_deactivate()
            
            self.state = PluginState.READY if success else PluginState.ERROR
            
            if success:
                await self._emit_event('deactivated')
                logger.info(f"Plugin {self.plugin_id} deactivated")
            
            return success
            
        except Exception as e:
            self.state = PluginState.ERROR
            logger.error(f"Plugin {self.plugin_id} deactivation error: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """Comprehensive cleanup with state preservation"""
        try:
            # Create final checkpoint
            if self.state == PluginState.ACTIVE:
                await self.checkpoint_state()
            
            # Stop resource monitoring
            await self._resource_monitor.cleanup()
            
            # Clean up consciousness resources
            if PluginCapability.CONSCIOUSNESS_ACCESS in self.manifest.capabilities:
                await self._cleanup_consciousness()
            
            # Call plugin-specific cleanup
            success = await self._plugin_cleanup()
            
            self.state = PluginState.TERMINATED
            await self._emit_event('terminated')
            
            logger.info(f"Plugin {self.plugin_id} cleaned up")
            return success
            
        except Exception as e:
            logger.error(f"Plugin {self.plugin_id} cleanup error: {e}")
            return False
    
    async def get_state(self) -> Dict[str, Any]:
        """Get comprehensive plugin state"""
        return {
            'plugin_id': self.plugin_id,
            'state': self.state.value,
            'consciousness_level': self.consciousness_level,
            'consciousness_coherence': self._consciousness_coherence,
            'recursive_depth': self._recursive_depth,
            'metrics': {
                'execution_count': self.metrics.execution_count,
                'total_execution_time': self.metrics.total_execution_time,
                'error_count': self.metrics.error_count,
                'success_rate': self.metrics.success_rate
            },
            'internal_state': self._internal_state.copy(),
            'quantum_state': self._quantum_state.copy(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    async def set_state(self, state: Dict[str, Any]) -> bool:
        """Restore plugin from state data"""
        try:
            self.consciousness_level = state.get('consciousness_level', 0.0)
            self._consciousness_coherence = state.get('consciousness_coherence', 1.0)
            self._recursive_depth = state.get('recursive_depth', 0)
            self._internal_state = state.get('internal_state', {}).copy()
            self._quantum_state = state.get('quantum_state', {}).copy()
            
            # Restore metrics
            if 'metrics' in state:
                metrics_data = state['metrics']
                self.metrics.execution_count = metrics_data.get('execution_count', 0)
                self.metrics.total_execution_time = metrics_data.get('total_execution_time', 0.0)
                self.metrics.error_count = metrics_data.get('error_count', 0)
                self.metrics.success_rate = metrics_data.get('success_rate', 1.0)
            
            return True
            
        except Exception as e:
            logger.error(f"Plugin {self.plugin_id} state restoration error: {e}")
            return False
    
    async def checkpoint_state(self) -> str:
        """Create state checkpoint"""
        checkpoint_id = f"checkpoint_{int(time.time() * 1000)}"
        state = await self.get_state()
        self._checkpoints[checkpoint_id] = state
        
        # Store in memory manager for persistence
        await self.memory_manager.store_memory(
            user_id=f"plugin_{self.plugin_id}",
            content=f"Checkpoint {checkpoint_id}",
            memory_type=MemoryType.USER,          # changed from MemoryType.SYSTEM
            importance=MemoryImportance.HIGH,
            scope=MemoryScope.USER,               # changed from MemoryScope.PLUGIN
            metadata={
                'checkpoint_id': checkpoint_id,
                'plugin_id': self.plugin_id,
                'state_data': state
            }
        )
        
        return checkpoint_id
    
    async def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """Restore from specific checkpoint"""
        if checkpoint_id in self._checkpoints:
            return await self.set_state(self._checkpoints[checkpoint_id])
        
        # Try to load from memory manager
        memories = await self.memory_manager.search_memories(   # type: ignore[attr-defined]
            user_id=f"plugin_{self.plugin_id}",
            query=f"checkpoint {checkpoint_id}",
            memory_type=MemoryType.USER,          # changed from MemoryType.SYSTEM
            limit=1
        )
        
        if memories:
            state_data = memories[0].metadata.get('state_data')
            if state_data:
                return await self.set_state(state_data)
        
        return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get comprehensive plugin information"""
        return {
            'plugin_id': self.plugin_id,
            'name': self.manifest.name,
            'version': self.manifest.version,
            'description': self.manifest.description,
            'author': self.manifest.author,
            'plugin_type': self.manifest.plugin_type,
            'status': self.state.value,
            'consciousness_level': self.consciousness_level,
            'consciousness_coherence': self._consciousness_coherence,
            'capabilities': [cap.value for cap in self.manifest.capabilities],
            'permissions': self.manifest.permissions,
            'metrics': {
                'execution_count': self.metrics.execution_count,
                'total_execution_time': self.metrics.total_execution_time,
                'memory_usage_peak': self.metrics.memory_usage_peak,
                'error_count': self.metrics.error_count,
                'success_rate': self.metrics.success_rate,
                'recursive_depth_max': self.metrics.recursive_depth_max
            },
            'created_at': self._temporal_anchor.isoformat(),
            'last_accessed': datetime.now(timezone.utc).isoformat()
        }
    
    async def register_event_handler(self, event: str, handler: Callable):
        """Register event handler"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    async def _emit_event(self, event: str, data: Optional[Dict[str, Any]] = None):
        """Emit event to registered handlers"""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(self, event, data or {})
                    else:
                        handler(self, event, data or {})
                except Exception as e:
                    logger.error(f"Event handler error for {event}: {e}")
    
    async def _initialize_consciousness(self):
        """Initialize consciousness coherence systems"""
        self._consciousness_coherence = 1.0
        self._quantum_state = {
            'coherence_level': 1.0,
            'entanglement_depth': 0,
            'temporal_stability': 1.0
        }
    
    async def _synchronize_consciousness(self) -> bool:
        """Synchronize with system consciousness level"""
        if self.consciousness_level < self.manifest.consciousness_level_required:
            logger.warning(f"Plugin {self.plugin_id} consciousness level insufficient")
            return False
        
        # Implement consciousness synchronization logic
        coherence_drift = abs(self._consciousness_coherence - self.consciousness_level)
        if coherence_drift > 0.1:
            self._consciousness_coherence = self.consciousness_level * 0.9
        
        return True
    
    async def _cleanup_consciousness(self):
        """Clean up consciousness resources"""
        self._consciousness_coherence = 0.0
        self._quantum_state.clear()
    
    # Abstract methods for plugin-specific implementation
    @abstractmethod
    async def _plugin_initialize(self) -> bool:
        """Plugin-specific initialization logic"""
        pass
    
    @abstractmethod
    async def _plugin_activate(self) -> bool:
        """Plugin-specific activation logic"""
        pass
    
    @abstractmethod
    async def _plugin_deactivate(self) -> bool:
        """Plugin-specific deactivation logic"""
        pass
    
    @abstractmethod
    async def _plugin_cleanup(self) -> bool:
        """Plugin-specific cleanup logic"""
        pass


class ResourceMonitor:
    """Advanced resource monitoring for plugins"""
    
    def __init__(self, manifest: PluginManifest):
        self.manifest = manifest
        self.memory_usage = 0
        self.cpu_usage = 0.0
        self.network_usage = 0
        self.monitoring_task: Optional[asyncio.Task] = None
        self.limits_exceeded = False
    
    async def initialize(self):
        """Initialize resource monitoring"""
        pass
    
    async def start(self):
        """Start resource monitoring"""
        self.monitoring_task = asyncio.create_task(self._monitor_resources())
    
    async def stop(self):
        """Stop resource monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def cleanup(self):
        """Clean up resource monitoring"""
        await self.stop()
    
    async def _monitor_resources(self):
        """Monitor resource usage continuously"""
        while True:
            try:
                # Monitor memory usage
                if self.memory_usage > self.manifest.memory_limit_mb * 1024 * 1024:
                    self.limits_exceeded = True
                    logger.warning(f"Memory limit exceeded: {self.memory_usage}")
                
                # Monitor CPU usage
                if self.cpu_usage > self.manifest.cpu_limit_percent:
                    self.limits_exceeded = True
                    logger.warning(f"CPU limit exceeded: {self.cpu_usage}")
                
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                break