"""Object-capability host façade for somnus-plugin-system.

Modified: 2026-09-18
Modified by: Stilgar (Cursor Grok 4.6, Daeron operator)
Justification: PACKET-005. Permissions become executable policy. A missing
    permission is the absence of a capability object, not a flag a plugin is
    trusted to honor. This module wraps a host MemoryManager / SecurityEnforcer
    Protocol; it does not vendor a host implementation.
Provenance: packets/PACKET-005-execution-boundary.md, SPEC.md section 4
Files: host_capabilities.py
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from host_protocols import MemoryImportance, MemoryManager, MemoryScope, MemoryType, SecurityEnforcer
from plugin_base import PluginManifest, PluginPermission

logger = logging.getLogger(__name__)


class ExecutionDomain(str, Enum):
    """Graduated execution domains. Not every plugin is a subprocess."""

    HOST_INTEGRATED = "host_integrated"
    VERIFIED = "verified"
    ISOLATED = "isolated"


class CapabilityDenied(PermissionError):
    """Raised when a plugin invokes a host operation it was not granted."""

    def __init__(self, plugin_id: str, permission: PluginPermission, action: str) -> None:
        self.plugin_id = plugin_id
        self.permission = permission
        self.action = action
        super().__init__(
            f"Plugin {plugin_id} denied {action}: missing permission {permission.value}"
        )


def select_execution_domain(manifest: PluginManifest) -> ExecutionDomain:
    """Select the execution domain from declared trust and security level."""
    if manifest.trusted or manifest.security_level <= 2:
        return ExecutionDomain.HOST_INTEGRATED
    if manifest.security_level >= 4:
        return ExecutionDomain.ISOLATED
    return ExecutionDomain.VERIFIED


class HostCapabilityFacade:
    """Capability-scoped MemoryManager assembled from a plugin manifest.

    Framework context creation is allowed (the substrate must bind a namespace).
    Plugin-visible store requires WRITE_MEMORY. Retrieve/search require
    READ_MEMORY or WRITE_MEMORY. Network and filesystem objects are omitted
    when those permissions are absent.
    """

    def __init__(
        self,
        host_memory: MemoryManager,
        security_enforcer: Optional[SecurityEnforcer],
        manifest: PluginManifest,
        plugin_id: str,
    ) -> None:
        self._host = host_memory
        self._enforcer = security_enforcer
        self.manifest = manifest
        self.plugin_id = plugin_id
        self.permissions = frozenset(manifest.permissions)
        self.domain = select_execution_domain(manifest)
        self.network = object() if PluginPermission.NETWORK_ACCESS in self.permissions else None
        self.filesystem = object() if PluginPermission.FILE_SYSTEM in self.permissions else None

    def has(self, permission: PluginPermission) -> bool:
        return permission in self.permissions

    async def _enforce(self, action: str, required: Optional[PluginPermission] = None) -> None:
        if required is not None and required not in self.permissions:
            raise CapabilityDenied(self.plugin_id, required, action)
        if self._enforcer is not None:
            allowed = await self._enforcer.validate_action(
                action,
                {"plugin_id": self.plugin_id, "permission": None if required is None else required.value},
            )
            if not allowed:
                perm = required or PluginPermission.SESSION_ACCESS
                raise CapabilityDenied(self.plugin_id, perm, action)

    async def create_context(
        self,
        context_id: str,
        scope: MemoryScope,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        await self._enforce("create_context")
        return await self._host.create_context(context_id, scope, metadata)

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
        await self._enforce("store_memory", PluginPermission.WRITE_MEMORY)
        return await self._host.store_memory(
            user_id, content, memory_type, importance, scope=scope, tags=tags, metadata=metadata
        )

    async def retrieve_memories(
        self,
        user_id: str,
        query: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if not (self.has(PluginPermission.READ_MEMORY) or self.has(PluginPermission.WRITE_MEMORY)):
            raise CapabilityDenied(self.plugin_id, PluginPermission.READ_MEMORY, "retrieve_memories")
        await self._enforce("retrieve_memories")
        return await self._host.retrieve_memories(user_id, query, memory_types=memory_types, limit=limit)

    async def search_memories(
        self,
        user_id: str,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> List[Any]:
        if not (self.has(PluginPermission.READ_MEMORY) or self.has(PluginPermission.WRITE_MEMORY)):
            raise CapabilityDenied(self.plugin_id, PluginPermission.READ_MEMORY, "search_memories")
        await self._enforce("search_memories")
        return await self._host.search_memories(user_id, query, memory_type=memory_type, limit=limit)

    async def framework_store_memory(
        self,
        user_id: str,
        content: str,
        memory_type: MemoryType,
        importance: MemoryImportance,
        scope: Optional[MemoryScope] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Framework checkpoint persistence. Does not require WRITE_MEMORY."""
        await self._enforce("framework_store_memory")
        return await self._host.store_memory(
            user_id, content, memory_type, importance, scope=scope, tags=tags, metadata=metadata
        )

    async def framework_search_memories(
        self,
        user_id: str,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> List[Any]:
        """Framework checkpoint lookup. Does not require READ_MEMORY."""
        await self._enforce("framework_search_memories")
        return await self._host.search_memories(user_id, query, memory_type=memory_type, limit=limit)
