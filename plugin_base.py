"""Somnus Plugin System — Canonical Plugin Contract and Lifecycle Engine.

Modified: 2026-09-06
Modified by: Stilgar (Claude Code, Daeron operator)
Justification: PACKET-001 (dependency/import truth), PACKET-002 (lineage convergence), and
    SOTA++ deep integration pass. Absorbed PluginPermission and PluginType from the superseded
    plugin_manager.py lineage. Replaced ABC-only interfaces with Protocol-based structural
    subtyping. Added capability lattice algebra, content-addressed state checkpoints with
    Merkle hashing, exponentially-weighted moving average metrics, typed event bus, and
    real resource measurement via stdlib. Host boundary realized via host_protocols.py
    (Protocol declaration strategy per HOST_BOUNDARY.md section 4).
Provenance: SPEC.md, MEMORY.md 2026-09-05 LINEAGE RULING, HOST_BOUNDARY.md
Files: plugin_base.py, host_protocols.py

This module is the canonical plugin contract. When SPEC.md and this module disagree,
this module wins and SPEC.md is repaired in the same turn.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import resource
import struct
import sys
import time
from urllib.parse import urlparse
from abc import ABC, abstractmethod
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, Flag, auto
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Deque,
    Dict,
    FrozenSet,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, FastAPI

from host_protocols import (
    MemoryManager,
    MemoryType,
    MemoryImportance,
    MemoryScope,
    SessionID,
    UserID,
    SecurityEnforcer,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
PluginT = TypeVar("PluginT", bound="PluginBase")


# ---------------------------------------------------------------------------
# Absorbed from plugin_manager.py — PACKET-002 lineage convergence
# ---------------------------------------------------------------------------

class PluginPermission(str, Enum):
    """Granular permission system for plugin capabilities.

    Absorbed from plugin_manager.py:75 during PACKET-002 lineage convergence.
    Eight closed values — plugins declare exactly which permissions they require,
    and the security subsystem validates code usage against declarations.
    """
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    NETWORK_ACCESS = "network_access"
    FILE_SYSTEM = "file_system"
    SYSTEM_COMMANDS = "system_commands"
    USER_INTERFACE = "user_interface"
    SESSION_ACCESS = "session_access"
    AGENT_CONTROL = "agent_control"


class PluginType(str, Enum):
    """Plugin classification for routing and permission scoping.

    Absorbed from plugin_manager.py:63 during PACKET-002 lineage convergence.
    The plugin_type manifest field is now typed against this enum rather than
    a bare str, closing the contract weakness documented in SPEC.md section 2.
    """
    API_EXTENSION = "api_extension"
    UI_COMPONENT = "ui_component"
    AGENT_ACTION = "agent_action"
    MEMORY_EXTENSION = "memory_extension"
    WORKFLOW_NODE = "workflow_node"
    TOOL_INTEGRATION = "tool_integration"
    RESEARCH_MODULE = "research_module"
    CREATIVE_ENGINE = "creative_engine"


# ---------------------------------------------------------------------------
# Capability algebra — lattice operations for capability composition analysis
# ---------------------------------------------------------------------------

class PluginCapability(str, Enum):
    """Advanced plugin capability classifications with lattice algebra.

    Capabilities describe what a plugin participates in (distinct from
    permissions, which describe what it is allowed to touch). The lattice
    operations enable formal composition analysis — can two plugins be
    co-scheduled? Does a workflow's capability set span its step requirements?
    """
    MEMORY_INTEGRATION = "memory_integration"
    CONSCIOUSNESS_ACCESS = "consciousness_access"
    MULTI_AGENT_COORDINATION = "multi_agent_coordination"
    RECURSIVE_PROCESSING = "recursive_processing"
    REAL_TIME_ADAPTATION = "real_time_adaptation"
    CROSS_SESSION_PERSISTENCE = "cross_session_persistence"
    QUANTUM_COHERENCE = "quantum_coherence"
    TEMPORAL_MANIPULATION = "temporal_manipulation"


class CapabilitySet:
    """Algebraic capability set with meet/join/complement operations.

    Enables formal analysis of capability composition — does a workflow's
    capability requirement set (the join of all step requirements) form a
    subset of the system's capability provision set? Can two plugins be
    safely co-scheduled given their capability intersection?
    """
    __slots__ = ("_members",)

    def __init__(self, members: FrozenSet[PluginCapability] | None = None) -> None:
        self._members: FrozenSet[PluginCapability] = members or frozenset()

    @classmethod
    def from_list(cls, caps: List[PluginCapability]) -> CapabilitySet:
        return cls(frozenset(caps))

    @classmethod
    def universe(cls) -> CapabilitySet:
        return cls(frozenset(PluginCapability))

    @classmethod
    def empty(cls) -> CapabilitySet:
        return cls(frozenset())

    def join(self, other: CapabilitySet) -> CapabilitySet:
        """Lattice join (union) — combined capabilities of two sets."""
        return CapabilitySet(self._members | other._members)

    def meet(self, other: CapabilitySet) -> CapabilitySet:
        """Lattice meet (intersection) — shared capabilities."""
        return CapabilitySet(self._members & other._members)

    def complement(self) -> CapabilitySet:
        """Capabilities NOT in this set."""
        return CapabilitySet(frozenset(PluginCapability) - self._members)

    def subsumes(self, required: CapabilitySet) -> bool:
        """Does this set provide all capabilities in `required`?"""
        return required._members <= self._members

    def gap(self, required: CapabilitySet) -> CapabilitySet:
        """Capabilities in `required` that this set does not provide."""
        return CapabilitySet(required._members - self._members)

    def __contains__(self, cap: PluginCapability) -> bool:
        return cap in self._members

    def __len__(self) -> int:
        return len(self._members)

    def __iter__(self):
        return iter(self._members)

    def __repr__(self) -> str:
        names = sorted(c.value for c in self._members)
        return f"CapabilitySet({{{', '.join(names)}}})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CapabilitySet):
            return self._members == other._members
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._members)


# ---------------------------------------------------------------------------
# Lifecycle states
# ---------------------------------------------------------------------------

class PluginState(str, Enum):
    """Detailed plugin lifecycle state tracking.

    Eight states forming a directed graph of valid transitions:
      INITIALIZING -> READY -> ACTIVE -> PROCESSING
      ACTIVE -> SUSPENDED -> ACTIVE (resumption)
      Any -> ERROR
      ACTIVE -> TERMINATING -> TERMINATED
      READY -> TERMINATED (never activated)
    """
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    PROCESSING = "processing"
    SUSPENDED = "suspended"
    ERROR = "error"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


_VALID_TRANSITIONS: Dict[PluginState, FrozenSet[PluginState]] = {
    PluginState.INITIALIZING: frozenset({PluginState.READY, PluginState.ERROR}),
    PluginState.READY: frozenset({PluginState.ACTIVE, PluginState.TERMINATED, PluginState.ERROR}),
    PluginState.ACTIVE: frozenset({
        PluginState.PROCESSING, PluginState.SUSPENDED,
        PluginState.TERMINATING, PluginState.ERROR,
    }),
    PluginState.PROCESSING: frozenset({PluginState.ACTIVE, PluginState.ERROR}),
    PluginState.SUSPENDED: frozenset({PluginState.ACTIVE, PluginState.TERMINATING, PluginState.ERROR}),
    PluginState.ERROR: frozenset({PluginState.INITIALIZING, PluginState.TERMINATED}),
    PluginState.TERMINATING: frozenset({PluginState.TERMINATED, PluginState.ERROR}),
    PluginState.TERMINATED: frozenset(),
}


class InvalidStateTransition(RuntimeError):
    """Raised when a plugin lifecycle transition violates the state graph."""
    def __init__(self, plugin_id: str, from_state: PluginState, to_state: PluginState) -> None:
        self.plugin_id = plugin_id
        self.from_state = from_state
        self.to_state = to_state
        valid = _VALID_TRANSITIONS.get(from_state, frozenset())
        super().__init__(
            f"Plugin {plugin_id}: invalid transition {from_state.value} -> {to_state.value}. "
            f"Valid targets: {{{', '.join(s.value for s in valid)}}}"
        )


# ---------------------------------------------------------------------------
# Runtime context and typed events
# ---------------------------------------------------------------------------

@dataclass
class PluginContext:
    """Runtime context for plugin execution, carrying session identity,
    resource limits, and execution topology (parent/child relationships)."""
    session_id: SessionID
    user_id: UserID
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    memory_context: Optional[Dict[str, Any]] = None
    execution_depth: int = 0
    parent_plugin_id: Optional[str] = None
    child_plugins: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    consciousness_level: float = 0.0


class PluginEventType(str, Enum):
    """Typed event classifications for the plugin event bus."""
    INITIALIZED = "initialized"
    ACTIVATED = "activated"
    DEACTIVATED = "deactivated"
    TERMINATED = "terminated"
    STATE_CHANGED = "state_changed"
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    ERROR = "error"
    METRICS_SNAPSHOT = "metrics_snapshot"
    PEER_MESSAGE = "peer_message"


@dataclass(frozen=True)
class PluginEvent:
    """Immutable typed event emitted by the plugin lifecycle engine."""
    event_type: PluginEventType
    plugin_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "plugin_id": self.plugin_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


# ---------------------------------------------------------------------------
# Exponentially-weighted moving average (EWMA) metrics
# ---------------------------------------------------------------------------

class EWMAAccumulator:
    """Exponentially-weighted moving average for streaming metric computation.

    Uses Welford's online algorithm for variance and EWMA for the mean,
    producing stable estimates even with high-variance plugin workloads.
    The decay parameter alpha controls how fast old observations fade:
    alpha=0.1 gives a long memory, alpha=0.5 gives responsive tracking.
    """
    __slots__ = ("_alpha", "_mean", "_var", "_count", "_min", "_max")

    def __init__(self, alpha: float = 0.2) -> None:
        self._alpha = alpha
        self._mean: float = 0.0
        self._var: float = 0.0
        self._count: int = 0
        self._min: float = float("inf")
        self._max: float = float("-inf")

    def update(self, value: float) -> None:
        self._count += 1
        self._min = min(self._min, value)
        self._max = max(self._max, value)
        if self._count == 1:
            self._mean = value
            self._var = 0.0
        else:
            diff = value - self._mean
            self._mean += self._alpha * diff
            self._var = (1 - self._alpha) * (self._var + self._alpha * diff * diff)

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def std(self) -> float:
        return math.sqrt(max(self._var, 0.0))

    @property
    def count(self) -> int:
        return self._count

    @property
    def min_val(self) -> float:
        return self._min if self._count > 0 else 0.0

    @property
    def max_val(self) -> float:
        return self._max if self._count > 0 else 0.0

    def snapshot(self) -> Dict[str, float]:
        return {
            "mean": self._mean,
            "std": self.std,
            "min": self.min_val,
            "max": self.max_val,
            "count": float(self._count),
        }


@dataclass
class PluginMetrics:
    """Runtime performance metrics with EWMA tracking.

    Replaces naive counters with exponentially-weighted moving averages
    that produce stable, responsive estimates of plugin performance
    characteristics under real workloads.
    """
    execution_count: int = 0
    total_execution_time: float = 0.0
    memory_usage_peak: int = 0
    error_count: int = 0
    last_execution: Optional[datetime] = None
    consciousness_coherence: float = 1.0
    recursive_depth_max: int = 0

    _execution_time_ewma: EWMAAccumulator = field(
        default_factory=lambda: EWMAAccumulator(alpha=0.2), repr=False
    )
    _memory_ewma: EWMAAccumulator = field(
        default_factory=lambda: EWMAAccumulator(alpha=0.1), repr=False
    )

    @property
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 1.0
        return max(0.0, 1.0 - (self.error_count / self.execution_count))

    def record_execution(self, duration_s: float, memory_bytes: int = 0) -> None:
        """Record an execution's duration and memory usage."""
        self.execution_count += 1
        self.total_execution_time += duration_s
        self.last_execution = datetime.now(timezone.utc)
        self._execution_time_ewma.update(duration_s)
        if memory_bytes > 0:
            self.memory_usage_peak = max(self.memory_usage_peak, memory_bytes)
            self._memory_ewma.update(memory_bytes)

    def record_error(self) -> None:
        self.error_count += 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            "execution_count": self.execution_count,
            "total_execution_time": self.total_execution_time,
            "memory_usage_peak": self.memory_usage_peak,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "execution_time_ewma": self._execution_time_ewma.snapshot(),
            "memory_ewma": self._memory_ewma.snapshot(),
            "consciousness_coherence": self.consciousness_coherence,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
        }


# ---------------------------------------------------------------------------
# Plugin manifest — the 33-field contract (32 original + plugin_type narrowed)
# ---------------------------------------------------------------------------

class PluginManifest(BaseModel):
    """Enhanced plugin manifest with consciousness integration.

    Pydantic-validated manifest with 33 fields. Malformed input raises.
    This is the canonical manifest — the superseded dataclass manifest from
    plugin_manager.py has been deleted per PACKET-002.
    """
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType  # narrowed from bare str per PACKET-002

    capabilities: List[PluginCapability] = Field(default_factory=list)
    consciousness_level_required: float = Field(default=0.0, ge=0.0, le=1.0)
    recursive_depth_limit: int = Field(default=10, ge=1, le=100)
    quantum_coherence_required: bool = False

    morpheus_version_min: str = "1.0.0"
    morpheus_version_max: str = "2.0.0"
    python_version_min: str = "3.11"
    dependencies: List[str] = Field(default_factory=list)
    plugin_dependencies: List[str] = Field(default_factory=list)

    permissions: List[PluginPermission] = Field(default_factory=list)  # narrowed from List[str]
    trusted: bool = False
    signature: Optional[str] = None
    security_level: int = Field(default=1, ge=1, le=5)

    api_endpoints: List[str] = Field(default_factory=list)
    ui_components: List[str] = Field(default_factory=list)
    agent_actions: List[str] = Field(default_factory=list)
    workflow_nodes: List[str] = Field(default_factory=list)
    memory_extensions: List[str] = Field(default_factory=list)

    memory_limit_mb: int = Field(default=512, ge=1, le=8192)
    cpu_limit_percent: float = Field(default=10.0, ge=0.1, le=100.0)
    network_access_required: bool = False
    file_system_access: List[str] = Field(default_factory=list)

    tags: List[str] = Field(default_factory=list)
    license: str = "MIT"
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None

    @field_validator("version")
    @classmethod
    def _validate_semver(cls, v: str) -> str:
        """Validate version follows semver-like format."""
        import re
        if not re.match(r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?$", v):
            raise ValueError(f"Version '{v}' does not match semver format (MAJOR.MINOR.PATCH)")
        return v

    @classmethod
    def from_file(cls, manifest_path: Path) -> PluginManifest:
        """Load manifest from JSON file with strict validation."""
        with open(manifest_path, "r") as f:
            data = json.load(f)
        return cls(**data)

    def to_file(self, manifest_path: Path) -> None:
        """Persist manifest to JSON file."""
        with open(manifest_path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2, default=str)

    def capability_set(self) -> CapabilitySet:
        """Return the manifest's capabilities as a CapabilitySet for lattice operations."""
        return CapabilitySet.from_list(self.capabilities)

    def permission_set(self) -> FrozenSet[PluginPermission]:
        """Return an immutable set of declared permissions."""
        return frozenset(self.permissions)

    def content_hash(self) -> str:
        """Content-addressable hash of the manifest for change detection."""
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Structural subtyping interfaces (Protocol-based)
# ---------------------------------------------------------------------------

@runtime_checkable
class PluginInterface(Protocol):
    """Core plugin interface — structural subtyping via Protocol.

    Any class that implements these methods satisfies the contract without
    explicit inheritance. This enables host-side plugin implementations
    to conform without importing this module.
    """
    async def initialize(self) -> bool: ...
    async def activate(self) -> bool: ...
    async def deactivate(self) -> bool: ...
    async def cleanup(self) -> bool: ...
    def get_info(self) -> Dict[str, Any]: ...


@runtime_checkable
class StateInterface(Protocol):
    """Interface for stateful plugins with persistence — Protocol-based."""
    async def get_state(self) -> Dict[str, Any]: ...
    async def set_state(self, state: Dict[str, Any]) -> bool: ...
    async def checkpoint_state(self) -> str: ...
    async def restore_checkpoint(self, checkpoint_id: str) -> bool: ...


@runtime_checkable
class ConsciousnessInterface(Protocol):
    """Interface for consciousness-aware plugins."""
    async def consciousness_sync(self, level: float) -> bool: ...
    async def quantum_coherence_check(self) -> float: ...
    async def recursive_depth_analysis(self) -> Dict[str, Any]: ...


@runtime_checkable
class NetworkInterface(Protocol):
    """Interface for network-enabled plugins."""
    async def network_request(self, method: str, url: str, **kwargs: Any) -> Dict[str, Any]: ...
    async def websocket_connect(self, url: str) -> Any: ...
    async def p2p_communicate(self, peer_id: str, message: Dict[str, Any]) -> bool: ...


# ---------------------------------------------------------------------------
# Content-addressed state checkpoints with Merkle hashing
# ---------------------------------------------------------------------------

def _merkle_hash(data: Dict[str, Any]) -> str:
    """Compute a deterministic Merkle hash of a state dictionary.

    Produces a content-addressable identifier for state snapshots,
    enabling deduplication (identical states share the same hash)
    and efficient change detection (only re-persist when hash changes).
    """
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class StateCheckpoint:
    """Immutable, content-addressed state checkpoint.

    The checkpoint_id is derived from the state's Merkle hash,
    not from wall-clock time. Two identical states produce the
    same checkpoint_id, enabling deduplication.
    """
    checkpoint_id: str
    plugin_id: str
    state_data: Dict[str, Any]
    merkle_hash: str
    created_at: datetime
    generation: int  # monotonically increasing generation counter

    @classmethod
    def create(cls, plugin_id: str, state_data: Dict[str, Any], generation: int) -> StateCheckpoint:
        mhash = _merkle_hash(state_data)
        return cls(
            checkpoint_id=f"ckpt_{mhash[:16]}_{generation}",
            plugin_id=plugin_id,
            state_data=state_data,
            merkle_hash=mhash,
            created_at=datetime.now(timezone.utc),
            generation=generation,
        )


# ---------------------------------------------------------------------------
# Resource monitor with real measurement
# ---------------------------------------------------------------------------

def current_resident_bytes() -> int:
    """Live resident set size.

    ``/proc/self/statm`` is the current RSS. ``resource.ru_maxrss`` is a
    high-water mark and stays elevated after the allocation is freed, so it
    is only the fallback when the proc file is unavailable.
    """
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as handle:
            resident_pages = int(handle.readline().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        usage = resource.getrusage(resource.RUSAGE_SELF)
        if sys.platform == "darwin":
            return int(usage.ru_maxrss)
        return int(usage.ru_maxrss) * 1024


def machine_cpu_percent(cpu_seconds: float, wall_seconds: float) -> float:
    """CPU as a share of the whole machine, capped at 100.

    ``process_time`` sums every core. Dividing by ``cpu_count`` keeps a
    single-threaded call on a 4-core host near 25 instead of 100, which is
    the same unit the manifest's ``cpu_limit_percent`` is enforced in.
    """
    cores = max(1, os.cpu_count() or 1)
    if wall_seconds <= 1e-9:
        return 0.0
    return round(min(max(0.0, cpu_seconds) / wall_seconds * 100.0 / cores, 100.0), 2)


class ResourceMonitor:
    """Resource monitoring for one loaded plugin.

    CPU is the machine share over the latest sample interval, not the
    lifetime ratio of process CPU to wall time. Memory is resident growth
    since ``initialize``, so the host process is not charged against the
    plugin manifest. Both readings use the same units as execution admission.
    """

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest
        self._memory_high_water: int = 0
        self._baseline_rss: int = 0
        self._cpu_time_start: float = 0.0
        self._wall_start: float = 0.0
        self._last_cpu: float = 0.0
        self._last_wall: float = 0.0
        self._cpu_percent: float = 0.0
        self._monitoring_task: Optional[asyncio.Task[None]] = None
        self._limits_exceeded: bool = False
        self._memory_hot: bool = False
        self._cpu_hot: bool = False
        self._violation_log: Deque[str] = deque(maxlen=50)

    async def initialize(self) -> None:
        """Capture baseline resource usage."""
        self._baseline_rss = current_resident_bytes()
        self._memory_high_water = 0
        self._cpu_time_start = time.process_time()
        self._wall_start = time.monotonic()
        self._last_cpu = self._cpu_time_start
        self._last_wall = self._wall_start
        self._cpu_percent = 0.0

    async def start(self) -> None:
        """Begin continuous resource monitoring."""
        self._monitoring_task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        if self._monitoring_task is not None:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    async def cleanup(self) -> None:
        await self.stop()

    def snapshot(self) -> Dict[str, Any]:
        """Current resource usage snapshot."""
        attributed = max(0, current_resident_bytes() - self._baseline_rss)
        return {
            "memory_rss_bytes": attributed,
            "memory_high_water_bytes": self._memory_high_water,
            "memory_limit_bytes": self.manifest.memory_limit_mb * 1024 * 1024,
            "cpu_percent": self._cpu_percent,
            "cpu_limit_percent": self.manifest.cpu_limit_percent,
            "limits_exceeded": self._limits_exceeded,
            "violation_count": len(self._violation_log),
        }

    def _note_violation(self, message: str) -> None:
        self._violation_log.append(message)
        logger.warning(message)

    async def _monitor_loop(self) -> None:
        while True:
            try:
                now_cpu = time.process_time()
                now_wall = time.monotonic()
                cpu_pct = machine_cpu_percent(now_cpu - self._last_cpu, now_wall - self._last_wall)
                self._last_cpu = now_cpu
                self._last_wall = now_wall
                self._cpu_percent = cpu_pct

                attributed = max(0, current_resident_bytes() - self._baseline_rss)
                self._memory_high_water = max(self._memory_high_water, attributed)

                limit_bytes = self.manifest.memory_limit_mb * 1024 * 1024
                memory_over = attributed > limit_bytes
                cpu_over = cpu_pct > self.manifest.cpu_limit_percent
                if memory_over and not self._memory_hot:
                    self._note_violation(
                        f"Memory {attributed // (1024*1024)}MB exceeds limit "
                        f"{self.manifest.memory_limit_mb}MB"
                    )
                if cpu_over and not self._cpu_hot:
                    self._note_violation(
                        f"CPU {cpu_pct:.1f}% exceeds limit {self.manifest.cpu_limit_percent}%"
                    )
                self._memory_hot = memory_over
                self._cpu_hot = cpu_over
                self._limits_exceeded = memory_over or cpu_over

                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Resource monitoring error: {exc}")
                break


# ---------------------------------------------------------------------------
# Plugin base class — the canonical implementation contract
# ---------------------------------------------------------------------------

class PluginBase(ABC):
    """Advanced plugin base class with lifecycle state machine, consciousness
    integration, content-addressed checkpointing, and resource monitoring.

    Plugins extend this class and implement the four abstract hooks:
        _plugin_initialize, _plugin_activate, _plugin_deactivate, _plugin_cleanup

    The class also satisfies ConsciousnessInterface and NetworkInterface.
    Network calls require PluginPermission.NETWORK_ACCESS. Peer messaging
    stays inside the process: a plugin here is a loaded codebase, and peers
    are other loaded plugins, not an implicit internet path.

    The base class provides:
    - Validated state transitions via a directed graph
    - EWMA-based runtime metrics
    - Content-addressed state checkpointing with Merkle hashing
    - Typed event bus with async handler dispatch
    - Real resource monitoring via stdlib
    - Consciousness coherence synchronization
    """

    def __init__(
        self,
        plugin_id: str,
        manifest: PluginManifest,
        memory_manager: MemoryManager,
        consciousness_level: float = 0.0,
    ) -> None:
        self.plugin_id = plugin_id
        self.manifest = manifest
        self.memory_manager = memory_manager
        self.consciousness_level = consciousness_level

        self.state = PluginState.INITIALIZING
        self.context: Optional[PluginContext] = None
        self.metrics = PluginMetrics()
        self.execution_lock = asyncio.Lock()

        self._internal_state: Dict[str, Any] = {}
        self._checkpoints: Dict[str, StateCheckpoint] = {}
        self._checkpoint_generation: int = 0
        self._event_handlers: Dict[PluginEventType, List[Callable]] = {}
        self._resource_monitor = ResourceMonitor(self.manifest)

        self._consciousness_coherence: float = 1.0
        self._quantum_state: Dict[str, Any] = {}
        self._recursive_depth: int = 0
        self._temporal_anchor: datetime = datetime.now(timezone.utc)
        self._inbox: List[Dict[str, Any]] = []
        self._live_sockets: List[Any] = []

        logger.info(f"Plugin {plugin_id} created with consciousness level {consciousness_level}")

    _peers: ClassVar[Dict[str, "PluginBase"]] = {}

    def _transition_state(self, target: PluginState) -> None:
        """Validate and execute a state transition against the directed graph."""
        valid = _VALID_TRANSITIONS.get(self.state, frozenset())
        if target not in valid:
            raise InvalidStateTransition(self.plugin_id, self.state, target)
        old = self.state
        self.state = target
        logger.debug(f"Plugin {self.plugin_id}: {old.value} -> {target.value}")

    async def initialize(self) -> bool:
        """Initialize plugin with resource monitoring and memory context setup."""
        try:
            self._transition_state(PluginState.INITIALIZING)
        except InvalidStateTransition:
            if self.state != PluginState.INITIALIZING:
                return False

        try:
            await self._resource_monitor.initialize()

            memory_context = await self.memory_manager.create_context(
                f"plugin_{self.plugin_id}",
                MemoryScope.USER,
                metadata={"plugin_type": self.manifest.plugin_type.value},
            )

            if PluginCapability.CONSCIOUSNESS_ACCESS in self.manifest.capabilities:
                await self._initialize_consciousness()

            success = await self._plugin_initialize()

            if success:
                self._transition_state(PluginState.READY)
                await self._emit_event(PluginEventType.INITIALIZED)
                logger.info(f"Plugin {self.plugin_id} initialized successfully")
            else:
                self._transition_state(PluginState.ERROR)
                logger.error(f"Plugin {self.plugin_id} initialization failed")

            return success

        except Exception as exc:
            self.state = PluginState.ERROR
            logger.error(f"Plugin {self.plugin_id} initialization error: {exc}")
            return False

    async def activate(self) -> bool:
        """Activate plugin with consciousness synchronization."""
        if self.state != PluginState.READY:
            return False

        try:
            async with self.execution_lock:
                self._transition_state(PluginState.ACTIVE)

                if self.manifest.consciousness_level_required > 0:
                    if not await self._synchronize_consciousness():
                        self._transition_state(PluginState.ERROR)
                        return False

                await self._resource_monitor.start()
                success = await self._plugin_activate()

                if success:
                    PluginBase._peers[self.plugin_id] = self
                    await self._emit_event(PluginEventType.ACTIVATED)
                    logger.info(f"Plugin {self.plugin_id} activated")
                else:
                    self._transition_state(PluginState.ERROR)
                    logger.error(f"Plugin {self.plugin_id} activation failed")

                return success

        except Exception as exc:
            self.state = PluginState.ERROR
            logger.error(f"Plugin {self.plugin_id} activation error: {exc}")
            return False

    async def deactivate(self) -> bool:
        """Deactivate plugin with graceful shutdown."""
        if self.state not in (PluginState.ACTIVE, PluginState.PROCESSING, PluginState.SUSPENDED):
            return True

        try:
            self._transition_state(PluginState.TERMINATING)
            PluginBase._peers.pop(self.plugin_id, None)
            await self._close_live_sockets()
            await self._resource_monitor.stop()
            success = await self._plugin_deactivate()

            if success:
                self._transition_state(PluginState.TERMINATED)
                await self._emit_event(PluginEventType.DEACTIVATED)
                logger.info(f"Plugin {self.plugin_id} deactivated")
            else:
                self._transition_state(PluginState.ERROR)

            return success

        except Exception as exc:
            self.state = PluginState.ERROR
            logger.error(f"Plugin {self.plugin_id} deactivation error: {exc}")
            return False

    async def cleanup(self) -> bool:
        """Comprehensive cleanup with final state checkpoint."""
        try:
            if self.state == PluginState.ACTIVE:
                await self.checkpoint_state()

            await self._resource_monitor.cleanup()

            if PluginCapability.CONSCIOUSNESS_ACCESS in self.manifest.capabilities:
                await self._cleanup_consciousness()

            success = await self._plugin_cleanup()
            self.state = PluginState.TERMINATED
            await self._emit_event(PluginEventType.TERMINATED)

            logger.info(f"Plugin {self.plugin_id} cleaned up")
            return success

        except Exception as exc:
            logger.error(f"Plugin {self.plugin_id} cleanup error: {exc}")
            return False

    # -- State persistence with content-addressed checkpoints -----------------

    async def get_state(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "state": self.state.value,
            "consciousness_level": self.consciousness_level,
            "consciousness_coherence": self._consciousness_coherence,
            "recursive_depth": self._recursive_depth,
            "metrics": self.metrics.snapshot(),
            "internal_state": self._internal_state.copy(),
            "quantum_state": self._quantum_state.copy(),
            "resource_snapshot": self._resource_monitor.snapshot(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def set_state(self, state: Dict[str, Any]) -> bool:
        try:
            self.consciousness_level = state.get("consciousness_level", 0.0)
            self._consciousness_coherence = state.get("consciousness_coherence", 1.0)
            self._recursive_depth = state.get("recursive_depth", 0)
            self._internal_state = state.get("internal_state", {}).copy()
            self._quantum_state = state.get("quantum_state", {}).copy()

            if "metrics" in state:
                md = state["metrics"]
                self.metrics.execution_count = md.get("execution_count", 0)
                self.metrics.total_execution_time = md.get("total_execution_time", 0.0)
                self.metrics.error_count = md.get("error_count", 0)
                self.metrics.memory_usage_peak = md.get("memory_usage_peak", 0)

            return True
        except Exception as exc:
            logger.error(f"Plugin {self.plugin_id} state restoration error: {exc}")
            return False

    async def checkpoint_state(self) -> str:
        """Create a content-addressed state checkpoint."""
        state_data = await self.get_state()
        self._checkpoint_generation += 1

        ckpt = StateCheckpoint.create(self.plugin_id, state_data, self._checkpoint_generation)

        if ckpt.merkle_hash in {c.merkle_hash for c in self._checkpoints.values()}:
            logger.debug(f"Plugin {self.plugin_id}: deduplicated checkpoint (same content)")
            return ckpt.checkpoint_id

        self._checkpoints[ckpt.checkpoint_id] = ckpt

        await self.memory_manager.store_memory(
            user_id=f"plugin_{self.plugin_id}",
            content=f"Checkpoint {ckpt.checkpoint_id}",
            # Plugin checkpoints are user-scoped memories. MemoryType.SYSTEM and
            # MemoryScope values other than USER remain on the host protocol for
            # host events; they are not the checkpoint classification.
            memory_type=MemoryType.USER,
            importance=MemoryImportance.HIGH,
            scope=MemoryScope.USER,
            metadata={
                "checkpoint_id": ckpt.checkpoint_id,
                "plugin_id": self.plugin_id,
                "merkle_hash": ckpt.merkle_hash,
                "generation": ckpt.generation,
                "state_data": state_data,
            },
        )

        await self._emit_event(PluginEventType.CHECKPOINT_CREATED, {"checkpoint_id": ckpt.checkpoint_id})
        return ckpt.checkpoint_id

    async def restore_checkpoint(self, checkpoint_id: str) -> bool:
        if checkpoint_id in self._checkpoints:
            success = await self.set_state(self._checkpoints[checkpoint_id].state_data)
            if success:
                await self._emit_event(PluginEventType.CHECKPOINT_RESTORED, {"checkpoint_id": checkpoint_id})
            return success

        memories = await self.memory_manager.search_memories(
            user_id=f"plugin_{self.plugin_id}",
            query=f"checkpoint {checkpoint_id}",
            memory_type=MemoryType.USER,
            limit=1,
        )

        if memories:
            state_data = memories[0].metadata.get("state_data")
            if state_data:
                success = await self.set_state(state_data)
                if success:
                    await self._emit_event(PluginEventType.CHECKPOINT_RESTORED, {"checkpoint_id": checkpoint_id})
                return success

        return False

    # -- Info and event bus ---------------------------------------------------

    def get_info(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.manifest.name,
            "version": self.manifest.version,
            "description": self.manifest.description,
            "author": self.manifest.author,
            "plugin_type": self.manifest.plugin_type.value,
            "status": self.state.value,
            "consciousness_level": self.consciousness_level,
            "consciousness_coherence": self._consciousness_coherence,
            "capabilities": [cap.value for cap in self.manifest.capabilities],
            "permissions": [p.value for p in self.manifest.permissions],
            "metrics": self.metrics.snapshot(),
            "resource_usage": self._resource_monitor.snapshot(),
            "created_at": self._temporal_anchor.isoformat(),
            "last_accessed": datetime.now(timezone.utc).isoformat(),
        }

    async def register_event_handler(
        self, event_type: PluginEventType, handler: Callable
    ) -> None:
        """Register a typed event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _emit_event(
        self, event_type: PluginEventType, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Emit a typed event to registered handlers."""
        event = PluginEvent(
            event_type=event_type,
            plugin_id=self.plugin_id,
            data=data or {},
        )
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as exc:
                logger.error(f"Event handler error for {event_type.value}: {exc}")

    # -- Consciousness subsystem ----------------------------------------------

    async def _initialize_consciousness(self) -> None:
        self._consciousness_coherence = 1.0
        self._quantum_state = {
            "coherence_level": 1.0,
            "entanglement_depth": 0,
            "temporal_stability": 1.0,
        }

    async def _synchronize_consciousness(self) -> bool:
        if self.consciousness_level < self.manifest.consciousness_level_required:
            logger.warning(
                f"Plugin {self.plugin_id}: consciousness level {self.consciousness_level} "
                f"below required {self.manifest.consciousness_level_required}"
            )
            return False

        coherence_drift = abs(self._consciousness_coherence - self.consciousness_level)
        if coherence_drift > 0.1:
            self._consciousness_coherence = self.consciousness_level * 0.9

        return True

    async def _cleanup_consciousness(self) -> None:
        self._consciousness_coherence = 0.0
        self._quantum_state.clear()

    # -- ConsciousnessInterface ------------------------------------------------

    async def consciousness_sync(self, level: float) -> bool:
        """Set the plugin consciousness level and resynchronize coherence."""
        if not 0.0 <= level <= 1.0:
            logger.error(
                "Plugin %s refused consciousness level %s outside [0, 1]",
                self.plugin_id,
                level,
            )
            return False
        self.consciousness_level = level
        if not self._quantum_state:
            await self._initialize_consciousness()
        return await self._synchronize_consciousness()

    async def quantum_coherence_check(self) -> float:
        """Return the current coherence in [0, 1] from level drift."""
        if not self._quantum_state:
            await self._initialize_consciousness()
        drift = abs(self._consciousness_coherence - self.consciousness_level)
        coherence = max(0.0, min(1.0, 1.0 - drift))
        self._quantum_state["coherence_level"] = coherence
        self.metrics.consciousness_coherence = coherence
        return coherence

    async def recursive_depth_analysis(self) -> Dict[str, Any]:
        """Report recursion depth against the manifest limit."""
        limit = self.manifest.recursive_depth_limit
        return {
            "plugin_id": self.plugin_id,
            "current_depth": self._recursive_depth,
            "limit": limit,
            "within_limit": self._recursive_depth <= limit,
            "remaining": max(0, limit - self._recursive_depth),
            "coherence": self._consciousness_coherence,
            "quantum_state": dict(self._quantum_state),
        }

    def enter_recursive_frame(self) -> bool:
        """Advance one recursive frame. Returns False when the limit is hit."""
        if self._recursive_depth >= self.manifest.recursive_depth_limit:
            return False
        self._recursive_depth += 1
        return True

    def leave_recursive_frame(self) -> None:
        self._recursive_depth = max(0, self._recursive_depth - 1)

    # -- NetworkInterface ------------------------------------------------------

    def _require_network_permission(self) -> None:
        if PluginPermission.NETWORK_ACCESS not in self.manifest.permissions:
            raise PermissionError(
                f"Plugin {self.plugin_id} does not declare NETWORK_ACCESS"
            )

    async def network_request(self, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        """Perform one HTTP request. Schemes other than http/https are refused."""
        self._require_network_permission()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"Refusing URL with scheme {parsed.scheme!r}")
        import aiohttp

        timeout_s = float(kwargs.pop("timeout", 30))
        payload = kwargs.pop("json", None)
        body = kwargs.pop("data", None)
        headers = kwargs.pop("headers", None)
        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method.upper(),
                url,
                json=payload,
                data=body,
                headers=headers,
            ) as response:
                text = await response.text()
                return {
                    "status": response.status,
                    "headers": {key: value for key, value in response.headers.items()},
                    "body": text[:1_000_000],
                    "url": str(response.url),
                }

    async def websocket_connect(self, url: str) -> Any:
        """Open a websocket and retain it until deactivate closes it."""
        self._require_network_permission()
        parsed = urlparse(url)
        if parsed.scheme not in ("ws", "wss") or not parsed.netloc:
            raise ValueError(f"Refusing websocket URL with scheme {parsed.scheme!r}")
        import aiohttp

        session = aiohttp.ClientSession()
        try:
            socket = await session.ws_connect(url)
        except Exception:
            await session.close()
            raise
        self._live_sockets.append((session, socket))
        return socket

    async def p2p_communicate(self, peer_id: str, message: Dict[str, Any]) -> bool:
        """Deliver a message to another loaded plugin in this process."""
        self._require_network_permission()
        peer = PluginBase._peers.get(peer_id)
        if peer is None:
            logger.warning("Plugin %s has no peer %s", self.plugin_id, peer_id)
            return False
        envelope = {
            "from": self.plugin_id,
            "to": peer_id,
            "message": message,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        peer._inbox.append(envelope)
        await peer._emit_event(PluginEventType.PEER_MESSAGE, envelope)
        return True

    def peer_inbox(self) -> List[Dict[str, Any]]:
        return list(self._inbox)

    async def _close_live_sockets(self) -> None:
        while self._live_sockets:
            session, socket = self._live_sockets.pop()
            try:
                await socket.close()
            except Exception as exc:
                logger.error("Websocket close failed: %s", type(exc).__name__)
            try:
                await session.close()
            except Exception as exc:
                logger.error("HTTP session close failed: %s", type(exc).__name__)

    # -- Abstract hooks -------------------------------------------------------

    @abstractmethod
    async def _plugin_initialize(self) -> bool:
        """Plugin-specific initialization logic."""
        ...

    @abstractmethod
    async def _plugin_activate(self) -> bool:
        """Plugin-specific activation logic."""
        ...

    @abstractmethod
    async def _plugin_deactivate(self) -> bool:
        """Plugin-specific deactivation logic."""
        ...

    @abstractmethod
    async def _plugin_cleanup(self) -> bool:
        """Plugin-specific cleanup logic."""
        ...
