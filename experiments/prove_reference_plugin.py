"""Load the canonical reference plugin through PluginManager and its API.

Run from the repository root:

    .venv/bin/python experiments/prove_reference_plugin.py

Prints one line per check, then writes a JSON artifact and a Markdown report.
Exit status is 0 only when every check passes.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI

from host_protocols import MemoryImportance, MemoryScope, MemoryType
from plugin_base import PluginBase, PluginManifest
from plugin_manager import PluginManager

SOURCE = ROOT / "installed" / "example_plugin"
ARTIFACT_DIR = Path("/opt/cursor/artifacts")
REPORT_DIR = ROOT / "experiments" / "reports"
CHECKS: List[Dict[str, Any]] = []


class MemoryRecord:
    def __init__(self, metadata: Dict[str, Any]) -> None:
        self.metadata = metadata


class HostMemory:
    def __init__(self) -> None:
        self.contexts: List[str] = []
        self.records: List[Dict[str, Any]] = []

    async def create_context(self, context_id: str, scope: MemoryScope, metadata=None):
        self.contexts.append(context_id)
        return {"context_id": context_id, "scope": scope.value}

    async def store_memory(self, user_id: str, content: str, memory_type: MemoryType,
                            importance: MemoryImportance, scope=None, tags=None, metadata=None):
        self.records.append({
            "user_id": user_id,
            "content": content,
            "memory_type": getattr(memory_type, "value", str(memory_type)),
            "metadata": metadata or {},
        })
        return uuid4()

    async def retrieve_memories(self, user_id: str, query: str, memory_types=None, limit: int = 10):
        return [row for row in self.records if row["user_id"] == user_id][:limit]

    async def search_memories(self, user_id: str, query: str, memory_type=None, limit: int = 10):
        hits = [row for row in self.records if row["user_id"] == user_id][:limit]
        return [MemoryRecord(row["metadata"]) for row in hits]


class HostSecurity:
    async def validate_action(self, action: str, context: Dict[str, Any]) -> bool:
        return action == "plugin.load"

    async def enforce_policy(self, policy_name: str, subject: str, resource: str) -> bool:
        return True


def record(name: str, passed: bool, detail: str) -> None:
    CHECKS.append({"name": name, "passed": passed, "detail": detail})
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name}: {detail}", flush=True)


async def call_asgi(app, method: str, path: str) -> tuple[int, Dict[str, Any]]:
    """Invoke the mounted FastAPI app without an HTTP client package."""
    status = {"code": 0}
    chunks: List[bytes] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"host", b"reference.local")],
        "client": ("127.0.0.1", 9),
        "server": ("reference.local", 80),
    }
    await app(scope, receive, send)
    raw = b"".join(chunks)
    body: Dict[str, Any] = {}
    if raw:
        body = json.loads(raw.decode())
    return status["code"], body


def zero_byte_files(root: Path) -> List[str]:
    found = []
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_size == 0:
            found.append(str(path.relative_to(root)))
    return found


async def main() -> int:
    empty = zero_byte_files(SOURCE)
    record("no zero-byte files", not empty, f"empty={empty}")

    manifest = PluginManifest.from_file(SOURCE / "manifest.json")
    record(
        "manifest validates",
        manifest.name == "somnus_reference"
        and manifest.version == "1.0.0"
        and manifest.plugin_type.value == "api_extension"
        and manifest.signature is None,
        f"name={manifest.name} version={manifest.version} type={manifest.plugin_type.value}",
    )

    import importlib.util
    spec = importlib.util.spec_from_file_location("somnus_reference_plugin", SOURCE / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plugin_cls = getattr(module, "Plugin", None)
    record(
        "Plugin subclasses canonical PluginBase",
        plugin_cls is not None and issubclass(plugin_cls, PluginBase),
        f"class={getattr(plugin_cls, '__name__', None)}",
    )

    api_spec = importlib.util.spec_from_file_location(
        "somnus_reference_api", SOURCE / "api" / "__init__.py"
    )
    api_module = importlib.util.module_from_spec(api_spec)
    api_spec.loader.exec_module(api_module)
    paths = sorted(getattr(route, "path", "") for route in api_module.router.routes)
    record(
        "router exports three distinct paths",
        hasattr(api_module, "router") and paths == ["/checkpoint", "/contract", "/lifecycle"],
        f"paths={paths}",
    )

    base = Path(tempfile.mkdtemp(prefix="somnus-reference-"))
    try:
        install_root = base / "installed" / "example_plugin"
        shutil.copytree(SOURCE, install_root)
        app = FastAPI()
        memory = HostMemory()
        manager = PluginManager(app, memory, HostSecurity(), plugin_base_dir=base)
        await manager.discovery.scan_plugin_directory(install_root)
        loaded = await manager.load_plugin("somnus_reference")
        plugin = manager.active_plugins.get("somnus_reference")
        record(
            "loader activates the reference plugin",
            loaded and plugin is not None and plugin.state.value == "active",
            f"loaded={loaded} state={getattr(plugin, 'state', None)}",
        )

        contract_status, contract_body = await call_asgi(
            app, "GET", "/api/plugins/somnus_reference/contract"
        )
        lifecycle_status, lifecycle_body = await call_asgi(
            app, "GET", "/api/plugins/somnus_reference/lifecycle"
        )
        checkpoint_status, checkpoint_body = await call_asgi(
            app, "POST", "/api/plugins/somnus_reference/checkpoint"
        )
        record(
            "contract route returns the manifest identity",
            contract_status == 200 and contract_body.get("name") == "somnus_reference",
            f"status={contract_status} body={contract_body}",
        )
        record(
            "lifecycle route is not the contract route",
            lifecycle_status == 200
            and lifecycle_body.get("ledger") == ["initialize", "activate"]
            and "name" not in lifecycle_body,
            f"status={lifecycle_status} body={lifecycle_body}",
        )
        stored = memory.records[-1]["metadata"] if memory.records else {}
        record(
            "checkpoint route stores a user-scoped host memory",
            checkpoint_status == 200
            and bool(checkpoint_body.get("checkpoint_id"))
            and bool(stored.get("merkle_hash"))
            and bool(memory.records)
            and memory.records[-1]["memory_type"] == "user",
            f"status={checkpoint_status} checkpoint={checkpoint_body.get('checkpoint_id')} "
            f"memory_type={memory.records[-1]['memory_type'] if memory.records else None}",
        )
        await manager.stop()
    finally:
        shutil.rmtree(base, ignore_errors=True)

    passed = sum(1 for item in CHECKS if item["passed"])
    total = len(CHECKS)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": total,
        "checks": CHECKS,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for directory in (ARTIFACT_DIR, REPORT_DIR):
        (directory / "reference_plugin.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        lines = [
            "# Reference plugin load",
            "",
            f"Passed {passed}/{total}.",
            "",
        ]
        for item in CHECKS:
            mark = "PASS" if item["passed"] else "FAIL"
            lines.append(f"- {mark} {item['name']}: {item['detail']}")
        (directory / "reference_plugin.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{total} checks passed")
    print(f"JSON  {ARTIFACT_DIR / 'reference_plugin.json'}")
    print(f"REPORT {ARTIFACT_DIR / 'reference_plugin.md'}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
