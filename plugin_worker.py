"""Isolated plugin worker process and parent handle.

Modified: 2026-09-18
Modified by: Stilgar (Cursor Grok 4.6, Daeron operator)
Justification: PACKET-005. Untrusted plugins import and execute in a child
    process. Host capability calls return to the parent over a pipe. Timeouts
    terminate the worker PID. Host-integrated plugins never enter this module.
Provenance: packets/PACKET-005-execution-boundary.md
Files: plugin_worker.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import multiprocessing
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from host_capabilities import ExecutionDomain, HostCapabilityFacade
from plugin_base import PluginBase, PluginManifest, PluginState, plugin_identity

logger = logging.getLogger(__name__)


def worker_entry(plugin_path: str, plugin_id: str, manifest_data: Dict[str, Any], conn: Any) -> None:
    """Child-process entry. Import plugin.py only here."""
    try:
        from plugin_base import PluginManifest as Manifest

        manifest = Manifest(**manifest_data)
        proxy = _WorkerHostProxy(conn)
        spec = importlib.util.spec_from_file_location(
            f"somnus_isolated_{plugin_id}",
            str(Path(plugin_path) / "plugin.py"),
        )
        if spec is None or spec.loader is None:
            conn.send({"op": "fatal", "error": "module spec failed"})
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        plugin_class = getattr(module, "Plugin", None)
        if plugin_class is None or not issubclass(plugin_class, PluginBase):
            conn.send({"op": "fatal", "error": "Plugin class missing or not canonical"})
            return
        plugin = plugin_class(plugin_id, manifest, proxy)
        conn.send({"op": "ready"})
        _worker_loop(plugin, conn)
    except Exception as exc:
        try:
            conn.send({"op": "fatal", "error": str(exc)})
        except Exception:
            pass


def _worker_loop(plugin: PluginBase, conn: Any) -> None:
    while True:
        msg = conn.recv()
        op = msg.get("op")
        req_id = msg.get("id")
        try:
            if op == "shutdown":
                conn.send({"op": "result", "id": req_id, "ok": True, "value": True})
                return
            if op == "initialize":
                value = asyncio.run(plugin.initialize())
            elif op == "activate":
                value = asyncio.run(plugin.activate())
            elif op == "deactivate":
                value = asyncio.run(plugin.deactivate())
            elif op == "cleanup":
                value = asyncio.run(plugin.cleanup())
            elif op == "checkpoint":
                value = asyncio.run(plugin.checkpoint_state())
            elif op == "restore":
                value = asyncio.run(plugin.restore_checkpoint(msg["checkpoint_id"]))
            elif op == "call":
                exported = plugin.get_exported_action(msg["method"])
                if exported is None:
                    raise PermissionError(f"{msg['method']} is not an exported action")
                method = exported.handler
                if asyncio.iscoroutinefunction(method):
                    value = asyncio.run(method(*msg.get("args", []), **msg.get("kwargs", {})))
                else:
                    value = method(*msg.get("args", []), **msg.get("kwargs", {}))
            elif op == "list_actions":
                value = plugin.exported_action_names()
            elif op == "info":
                value = plugin.get_info()
            else:
                raise ValueError(f"unknown op {op}")
            conn.send({"op": "result", "id": req_id, "ok": True, "value": value})
        except Exception as exc:
            conn.send({"op": "result", "id": req_id, "ok": False, "error": str(exc)})


class _WorkerHostProxy:
    """MemoryManager stand-in that RPCs host capability calls to the parent."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._next = 1

    def _host_call(self, method: str, payload: Dict[str, Any]) -> Any:
        req_id = self._next
        self._next += 1
        self._conn.send({"op": "host_call", "id": req_id, "method": method, "payload": payload})
        while True:
            msg = self._conn.recv()
            if msg.get("op") == "host_result" and msg.get("id") == req_id:
                if not msg.get("ok"):
                    raise RuntimeError(msg.get("error", "host call failed"))
                return msg.get("value")
            # Unexpected parent traffic is a protocol error in this direction.
            raise RuntimeError(f"unexpected worker host message: {msg}")

    async def create_context(self, context_id, scope, metadata=None):
        return self._host_call(
            "create_context",
            {"context_id": context_id, "scope": getattr(scope, "value", scope), "metadata": metadata},
        )

    async def store_memory(self, user_id, content, memory_type, importance,
                           scope=None, tags=None, metadata=None):
        return self._host_call(
            "store_memory",
            {
                "user_id": user_id,
                "content": content,
                "memory_type": getattr(memory_type, "value", memory_type),
                "importance": getattr(importance, "value", importance),
                "scope": getattr(scope, "value", scope) if scope is not None else None,
                "tags": tags,
                "metadata": metadata,
            },
        )

    async def retrieve_memories(self, user_id, query, memory_types=None, limit=10):
        return self._host_call(
            "retrieve_memories",
            {
                "user_id": user_id,
                "query": query,
                "memory_types": [getattr(t, "value", t) for t in (memory_types or [])],
                "limit": limit,
            },
        )

    async def search_memories(self, user_id, query, memory_type=None, limit=10):
        return self._host_call(
            "search_memories",
            {
                "user_id": user_id,
                "query": query,
                "memory_type": getattr(memory_type, "value", memory_type) if memory_type else None,
                "limit": limit,
            },
        )

    async def framework_store_memory(self, user_id, content, memory_type, importance,
                                     scope=None, tags=None, metadata=None):
        return self._host_call(
            "framework_store_memory",
            {
                "user_id": user_id,
                "content": content,
                "memory_type": getattr(memory_type, "value", memory_type),
                "importance": getattr(importance, "value", importance),
                "scope": getattr(scope, "value", scope) if scope is not None else None,
                "tags": tags,
                "metadata": metadata,
            },
        )

    async def framework_search_memories(self, user_id, query, memory_type=None, limit=10):
        return self._host_call(
            "framework_search_memories",
            {
                "user_id": user_id,
                "query": query,
                "memory_type": getattr(memory_type, "value", memory_type) if memory_type else None,
                "limit": limit,
            },
        )


class IsolatedPluginHandle:
    """Parent-side handle for an isolated plugin generation."""

    def __init__(
        self,
        plugin_path: Path,
        plugin_id: str,
        manifest: PluginManifest,
        facade: HostCapabilityFacade,
    ) -> None:
        self.plugin_id = plugin_id
        self.manifest = manifest
        self.memory_manager = facade
        self.execution_domain = ExecutionDomain.ISOLATED.value
        self.state = PluginState.INITIALIZING
        self._path = Path(plugin_path)
        self._facade = facade
        self._ctx = multiprocessing.get_context("spawn")
        self._parent, child = self._ctx.Pipe()
        self._proc = self._ctx.Process(
            target=worker_entry,
            args=(str(self._path), plugin_id, manifest.model_dump(mode="json"), child),
            name=f"plugin-worker-{plugin_id}",
        )
        self._proc.start()
        child.close()
        self._req = 0
        self._actions: Dict[str, str] = {name: name for name in manifest.agent_actions}
        self._ready = False

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc is not None else None

    def is_alive(self) -> bool:
        return bool(self._proc and self._proc.is_alive())

    def get_exported_action(self, name: str) -> Optional[str]:
        return self._actions.get(name)

    def exported_action_names(self) -> list:
        return list(self._actions.keys())

    def wait_ready(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            if self._parent.poll(min(remaining, 0.2)):
                msg = self._parent.recv()
                if msg.get("op") == "ready":
                    self._ready = True
                    return
                if msg.get("op") == "fatal":
                    raise RuntimeError(msg.get("error", "worker fatal before ready"))
            if not self.is_alive():
                raise RuntimeError(f"isolated plugin {self.plugin_id} worker exited before ready")
        raise TimeoutError(f"isolated plugin {self.plugin_id} did not become ready")

    def terminate_worker(self) -> None:
        if self._proc is not None and self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(timeout=2)
            if self._proc.is_alive():
                self._proc.kill()
                self._proc.join(timeout=1)

    async def _rpc(self, payload: Dict[str, Any], timeout: Optional[float] = None) -> Any:
        self._req += 1
        payload = dict(payload)
        payload["id"] = self._req
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._rpc_sync, payload, timeout)

    def _rpc_sync(self, payload: Dict[str, Any], timeout: Optional[float]) -> Any:
        deadline = None if timeout is None else time.monotonic() + timeout
        self._parent.send(payload)
        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if deadline is not None and remaining == 0:
                self.terminate_worker()
                raise TimeoutError(f"isolated plugin {self.plugin_id} timed out")
            if not self._parent.poll(remaining if remaining is not None else 0.1):
                if deadline is not None and time.monotonic() >= deadline:
                    self.terminate_worker()
                    raise TimeoutError(f"isolated plugin {self.plugin_id} timed out")
                if not self.is_alive():
                    raise RuntimeError(f"isolated plugin {self.plugin_id} worker exited")
                continue
            msg = self._parent.recv()
            if msg.get("op") == "fatal":
                raise RuntimeError(msg.get("error", "worker fatal"))
            if msg.get("op") == "ready":
                continue
            if msg.get("op") == "host_call":
                self._service_host_call(msg)
                continue
            if msg.get("op") == "result" and msg.get("id") == payload["id"]:
                if not msg.get("ok"):
                    raise RuntimeError(msg.get("error", "worker call failed"))
                return msg.get("value")

    def _service_host_call(self, msg: Dict[str, Any]) -> None:
        method = msg["method"]
        payload = msg.get("payload", {})
        try:
            result = asyncio.run(self._dispatch_host(method, payload))
            self._parent.send({"op": "host_result", "id": msg["id"], "ok": True, "value": result})
        except Exception as exc:
            self._parent.send({"op": "host_result", "id": msg["id"], "ok": False, "error": str(exc)})

    async def _dispatch_host(self, method: str, payload: Dict[str, Any]) -> Any:
        from host_protocols import MemoryImportance, MemoryScope, MemoryType

        if method == "create_context":
            scope = MemoryScope(payload["scope"]) if payload.get("scope") else MemoryScope.USER
            return await self._facade.create_context(payload["context_id"], scope, payload.get("metadata"))
        if method == "store_memory":
            return await self._facade.store_memory(
                payload["user_id"],
                payload["content"],
                MemoryType(payload["memory_type"]),
                MemoryImportance(payload["importance"]),
                scope=MemoryScope(payload["scope"]) if payload.get("scope") else None,
                tags=payload.get("tags"),
                metadata=payload.get("metadata"),
            )
        if method == "retrieve_memories":
            types = [MemoryType(t) for t in payload.get("memory_types") or []]
            return await self._facade.retrieve_memories(
                payload["user_id"], payload["query"], memory_types=types or None, limit=payload.get("limit", 10)
            )
        if method == "search_memories":
            mt = MemoryType(payload["memory_type"]) if payload.get("memory_type") else None
            return await self._facade.search_memories(
                payload["user_id"], payload["query"], memory_type=mt, limit=payload.get("limit", 10)
            )
        if method == "framework_store_memory":
            return await self._facade.framework_store_memory(
                payload["user_id"],
                payload["content"],
                MemoryType(payload["memory_type"]),
                MemoryImportance(payload["importance"]),
                scope=MemoryScope(payload["scope"]) if payload.get("scope") else None,
                tags=payload.get("tags"),
                metadata=payload.get("metadata"),
            )
        if method == "framework_search_memories":
            mt = MemoryType(payload["memory_type"]) if payload.get("memory_type") else None
            return await self._facade.framework_search_memories(
                payload["user_id"], payload["query"], memory_type=mt, limit=payload.get("limit", 10)
            )
        raise ValueError(f"unknown host method {method}")

    async def initialize(self) -> bool:
        if not self._ready:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.wait_ready)
        ok = bool(await self._rpc({"op": "initialize"}))
        if ok:
            names = await self._rpc({"op": "list_actions"})
            if isinstance(names, list):
                self._actions = {str(name): str(name) for name in names}
        if ok:
            self.state = PluginState.READY
        else:
            self.state = PluginState.ERROR
        return ok

    async def activate(self) -> bool:
        ok = bool(await self._rpc({"op": "activate"}))
        if ok:
            self.state = PluginState.ACTIVE
        else:
            self.state = PluginState.ERROR
        return ok

    async def deactivate(self) -> bool:
        if not self.is_alive():
            self.state = PluginState.TERMINATED
            return True
        try:
            ok = bool(await self._rpc({"op": "deactivate"}, timeout=5.0))
        except Exception:
            ok = False
        if ok:
            self.state = PluginState.TERMINATED
        return ok

    async def cleanup(self) -> bool:
        try:
            if self.is_alive():
                ok = bool(await self._rpc({"op": "cleanup"}, timeout=5.0))
            else:
                ok = True
        except Exception:
            ok = False
        self.terminate_worker()
        try:
            self._parent.close()
        except Exception:
            pass
        self.state = PluginState.TERMINATED
        return ok

    async def checkpoint_state(self) -> str:
        return str(await self._rpc({"op": "checkpoint"}))

    async def restore_checkpoint(self, checkpoint_id: str) -> bool:
        return bool(await self._rpc({"op": "restore", "checkpoint_id": checkpoint_id}))

    async def call_action(self, method: str, *args: Any, timeout: Optional[float] = None, **kwargs: Any) -> Any:
        if method not in self._actions:
            raise PermissionError(f"{method} is not an exported action")
        return await self._rpc(
            {"op": "call", "method": method, "args": list(args), "kwargs": kwargs},
            timeout=timeout,
        )

    def get_info(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.manifest.name,
            "version": self.manifest.version,
            "description": self.manifest.description,
            "author": self.manifest.author,
            "plugin_type": self.manifest.plugin_type.value,
            "status": self.state.value,
            "permissions": [p.value for p in self.manifest.permissions],
            "execution_domain": self.execution_domain,
            "exported_actions": self.exported_action_names(),
            "pid": self.pid,
            "created_at": "",
            "last_accessed": "",
        }


def isolated_identity(name: str, version: str) -> str:
    return plugin_identity(name, version)
