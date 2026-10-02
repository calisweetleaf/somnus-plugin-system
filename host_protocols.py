"""Host boundary protocol declarations for somnus-plugin-system.

Modified: 2026-09-06
Modified by: Stilgar (Claude Code, Daeron operator)
Justification: Realizes HOST_BOUNDARY.md strategy 1 (Protocol declaration) to define the
    structural subtyping contracts that embedding hosts must satisfy. This is not a stub,
    not a mock, and not a fallback. It is a formal contract definition using Python's
    typing.Protocol system. The host's concrete classes structurally satisfy these protocols
    at integration time without this module importing anything from the host.
Provenance: HOST_BOUNDARY.md section 4, strategy 1
Files: host_protocols.py

The protocols below mirror the 3 donor modules (core.memory_core, schemas.session,
core.security_layer) and their 7 symbols. Live consumers import
`from host_protocols import ...` (plugin_base, plugin_manager, hot_reload,
host_capabilities). Any host implementation that structurally conforms to these
protocols will satisfy the plugin system's requirements.
"""
from __future__ import annotations

import sys
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    Union,
    runtime_checkable,
)
from uuid import UUID


# ---------------------------------------------------------------------------
# schemas.session — SessionID, UserID
#
# Consumed at: plugin_base.PluginContext
# Required behavior: constructible, comparable, usable as type annotations
# on PluginContext.session_id and PluginContext.user_id. No behavioral
# requirement beyond identity.
# ---------------------------------------------------------------------------

SessionID = str
UserID = str


# ---------------------------------------------------------------------------
# core.memory_core — MemoryType, MemoryImportance, MemoryScope
#
# These are enum-like types. The host must supply values that the plugin
# system references. We define Protocol-compatible enums that the host's
# concrete enums structurally satisfy.
# ---------------------------------------------------------------------------

class MemoryType(str, Enum):
    """Memory classification types.

    The host's MemoryType must expose at least USER.
    The SYSTEM_EVENT value is consumed by plugin_manager.py for plugin data storage.
    """
    USER = "user"
    SYSTEM = "system"
    SYSTEM_EVENT = "system_event"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryImportance(str, Enum):
    """Memory importance levels for storage prioritization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryScope(str, Enum):
    """Memory scoping for namespace isolation.

    The host's MemoryScope must expose at least USER.
    PLUGIN was the original scope before the donor API shift (see DEFECT_INDEX D-021).
    """
    USER = "user"
    PLUGIN = "plugin"
    SESSION = "session"
    GLOBAL = "global"


# ---------------------------------------------------------------------------
# core.memory_core — MemoryManager
#
# Consumed at: PluginBase, PluginManager, HostCapabilityFacade, HotReload
# Required behavior: create_context, store_memory, retrieve_memories, search_memories
# ---------------------------------------------------------------------------

@runtime_checkable
class MemoryManager(Protocol):
    """Protocol for the host-supplied memory management system.

    The embedding system must supply a concrete class that structurally
    satisfies this protocol. The plugin system calls these methods during
    lifecycle transitions, state checkpointing, and plugin data persistence.

    This is a contract declaration, not an implementation. Per HOST_BOUNDARY.md,
    the correct response to a donor import is to declare it, not to resolve it.
    """

    async def create_context(
        self,
        context_id: str,
        scope: MemoryScope,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Establish a plugin's memory context during initialize().

        Args:
            context_id: Unique identifier for the memory context (typically plugin_{id}).
            scope: Scoping level for memory isolation.
            metadata: Additional context metadata.

        Returns:
            An opaque context handle the plugin may use for scoped memory operations.
        """
        ...

    async def store_memory(
        self,
        user_id: str,
        content: str,
        memory_type: MemoryType,
        importance: MemoryImportance,
        scope: Optional[MemoryScope] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Persist a memory entry.

        Args:
            user_id: Owner identifier (often "system" or "plugin_{id}").
            content: Serialized content payload.
            memory_type: Classification of the memory.
            importance: Priority level for retention and retrieval.
            scope: Optional scoping override.
            tags: Searchable tags for retrieval.
            metadata: Structured metadata payload.

        Returns:
            UUID of the stored memory entry.
        """
        ...

    async def retrieve_memories(
        self,
        user_id: str,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories matching criteria.

        Args:
            user_id: Owner to scope the search.
            query: Search query string.
            memory_types: Optional filter by memory type.
            limit: Maximum results to return.

        Returns:
            List of memory entry dicts with at minimum 'content' and 'metadata' keys.
        """
        ...

    async def search_memories(
        self,
        user_id: str,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> List[Any]:
        """Search memories with structured result objects.

        Used by PluginBase.restore_checkpoint via the façade.

        Args:
            user_id: Owner to scope the search.
            query: Search query string.
            memory_type: Optional filter.
            limit: Maximum results.

        Returns:
            List of memory objects with .metadata attribute.
        """
        ...


# ---------------------------------------------------------------------------
# core.security_layer — SecurityEnforcer
#
# Consumed at: PluginManager.__init__, HostCapabilityFacade
# Required behavior: host runtime-policy surface. Survived PACKET-002.
# Static analysis authority is security.SecurityManager.
# ---------------------------------------------------------------------------

@runtime_checkable
class SecurityEnforcer(Protocol):
    """Protocol for the host-supplied security enforcement layer.

    Consumed by PluginManager. PACKET-002 ruled that SecurityEnforcer survives
    as the host runtime-policy surface. Static analysis is security.SecurityManager.
    PACKET-005 binds this protocol through the capability façade.
    """

    async def validate_action(
        self,
        action: str,
        context: Dict[str, Any],
    ) -> bool:
        """Validate whether an action is permitted in the given context.

        Args:
            action: The action identifier to validate.
            context: Contextual information for the security decision.

        Returns:
            True if the action is permitted.
        """
        ...

    async def enforce_policy(
        self,
        policy_name: str,
        subject: str,
        resource: str,
    ) -> bool:
        """Enforce a named security policy.

        Args:
            policy_name: The policy to enforce.
            subject: The entity attempting the action.
            resource: The resource being accessed.

        Returns:
            True if the policy permits the action.
        """
        ...
