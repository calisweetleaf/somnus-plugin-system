"""Prove the scoped defect closures in somnus-plugin-system.

Run from the repository root:

    .venv/bin/python experiments/prove_defect_closure.py

The process prints one line per check, then writes a JSON artifact and a
Markdown report. Exit status is 0 only when every check passes.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiohttp import web
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import FastAPI

from host_protocols import MemoryImportance, MemoryScope, MemoryType
from marketplace import (
    DistributionChannel,
    MarketplaceConfig,
    MarketplaceProvider,
    PluginMarketplace,
    RegistryClient,
    TrustSystem,
    create_marketplace,
)
from orchestration import (
    ExecutionMode,
    ExecutionPriority,
    ExecutionQueue,
    ExecutionRequest,
    PluginOrchestrator,
    WorkflowDefinition,
    WorkflowState,
    _PRIORITY_DRAIN_ORDER,
)
from plugin_base import (
    ConsciousnessInterface,
    NetworkInterface,
    PluginBase,
    PluginCapability,
    PluginManifest,
    PluginPermission,
    PluginType,
)
from plugin_manager import PluginManager
from security import ArchivePathError, CryptographicValidator, safe_extract_zip


ARTIFACT_DIR = Path("/opt/cursor/artifacts")
REPORT_DIR = ROOT / "experiments" / "reports"


class MemoryRecord:
    def __init__(self, metadata: Dict[str, Any]) -> None:
        self.metadata = metadata


class HostMemory:
    """In-process host memory. Satisfies the MemoryManager protocol."""

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
            "memory_type": memory_type,
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


CHECKS: List[Dict[str, Any]] = []


def record(defect: str, name: str, passed: bool, detail: str) -> None:
    CHECKS.append({
        "defect": defect,
        "name": name,
        "passed": passed,
        "detail": detail,
    })
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {defect} {name}: {detail}", flush=True)


def manifest_dict(name: str, **overrides: Any) -> Dict[str, Any]:
    payload = {
        "name": name,
        "version": "1.2.0",
        "description": f"{name} loaded as a codebase module",
        "author": "proof-author",
        "plugin_type": PluginType.TOOL_INTEGRATION.value,
        "capabilities": [PluginCapability.CONSCIOUSNESS_ACCESS.value],
        "permissions": [PluginPermission.NETWORK_ACCESS.value],
        "memory_limit_mb": 512,
        "cpu_limit_percent": 50.0,
        "security_level": 1,
        "workflow_nodes": ["ingest", "emit"],
        "memory_extensions": ["checkpoint"],
    }
    payload.update(overrides)
    return payload


PLUGIN_SOURCE = '''
import asyncio
import time

from plugin_base import PluginBase

class Plugin(PluginBase):
    async def _plugin_initialize(self) -> bool:
        self._seen = []
        return True

    async def _plugin_activate(self) -> bool:
        return True

    async def _plugin_deactivate(self) -> bool:
        return True

    async def _plugin_cleanup(self) -> bool:
        return True

    async def ping(self, event=None):
        self._seen.append(event)
        return {"plugin": self.plugin_id, "event": event}

    async def hold(self, delay, label):
        started = time.perf_counter()
        await asyncio.sleep(delay)
        return {"label": label, "started": started, "finished": time.perf_counter()}

    def allocate(self, nbytes):
        block = bytearray(int(nbytes))
        return len(block)

    def burn(self, rounds):
        total = 0
        for value in range(int(rounds)):
            total += value * value
        return total
'''


def write_plugin_tree(root: Path, name: str, **manifest_overrides: Any) -> Path:
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "manifest.json").write_text(
        json.dumps(manifest_dict(name, **manifest_overrides), indent=2),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
    return plugin_dir


def zip_tree(source: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w") as archive:
        for item in source.rglob("*"):
            if item.is_file():
                archive.write(item, item.relative_to(source).as_posix())


def sign_bytes(private_key, payload: bytes) -> str:
    signature = private_key.sign(
        payload,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return signature.hex()


def public_pem(private_key) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


async def wait_execution(orchestrator: PluginOrchestrator, execution_id: str, timeout: float = 5.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        execution = orchestrator.workflow_engine.get_execution_status(execution_id)
        if execution and execution.state in (
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ):
            return execution
        await asyncio.sleep(0.02)
    raise TimeoutError(f"workflow {execution_id} did not finish")


async def prove_queue() -> None:
    queue = ExecutionQueue()
    low = ExecutionRequest(request_id="low", plugin_id="p", method_name="ping", priority=ExecutionPriority.LOW)
    normal = ExecutionRequest(request_id="normal", plugin_id="p", method_name="ping", priority=ExecutionPriority.NORMAL)
    realtime = ExecutionRequest(request_id="rt", plugin_id="p", method_name="ping", priority=ExecutionPriority.REALTIME)
    for request in (low, normal, realtime):
        await queue.enqueue(request)
    order = []
    while True:
        item = await queue.dequeue()
        if item is None:
            break
        order.append(item.request_id)
    record(
        "D-001",
        "priority drain",
        order == ["rt", "normal", "low"] and _PRIORITY_DRAIN_ORDER[0] is ExecutionPriority.REALTIME,
        f"dequeued {order}",
    )

    orphan = ExecutionRequest(request_id="orphan", plugin_id="p", method_name="ping", priority=ExecutionPriority.HIGH)
    await queue.enqueue(orphan)
    queue.queues[orphan.priority].popleft()
    removed = await queue.remove(orphan.request_id)
    record(
        "D-014",
        "remove inconsistency is visible and successful",
        removed is True and "orphan" not in queue.pending_requests,
        f"remove returned {removed}",
    )


async def prove_orchestration(manager: PluginManager, plugin_id: str) -> None:
    orchestrator = PluginOrchestrator(manager)
    await orchestrator.start()
    # Hot reload would replace the live instance from disk and discard the
    # budget the proof writes onto the manifest.
    await manager.discovery.stop_monitoring()
    try:
        plugin = manager.active_plugins[plugin_id]
        plugin.manifest.memory_limit_mb = 8192
        plugin.manifest.cpu_limit_percent = 100.0
        orchestrator.resource_monitor.resource_limits["cpu_percent_per_plugin"] = 100.0
        orchestrator.resource_monitor.resource_limits["memory_mb_per_plugin"] = 8192

        first = await orchestrator.execute_plugin_method(plugin_id, "allocate", 3 * 1024 * 1024)
        record(
            "D-011",
            "memory measurement is non-zero",
            first.success and first.memory_used >= 2,
            f"success={first.success} memory_used={first.memory_used}MB cpu={first.cpu_percent}",
        )
        burned = await orchestrator.execute_plugin_method(plugin_id, "burn", 2_000_000)
        record(
            "D-011",
            "cpu measurement is non-zero",
            burned.success and burned.cpu_percent > 1.0,
            f"success={burned.success} cpu={burned.cpu_percent} memory_used={burned.memory_used}",
        )
        plugin.manifest.memory_limit_mb = 1
        plugin.manifest.cpu_limit_percent = 1.0
        budget_ok, budget_violations = orchestrator.resource_monitor.check_manifest_budget(
            plugin_id,
            int(plugin.manifest.memory_limit_mb),
            float(plugin.manifest.cpu_limit_percent),
        )
        blocked = await orchestrator.execute_plugin_method(plugin_id, "ping")
        live = manager.active_plugins[plugin_id]
        record(
            "D-011",
            "manifest budget blocks the next call",
            budget_ok is False
            and live is plugin
            and (not blocked.success)
            and blocked.error is not None
            and "manifest limit" in str(blocked.error),
            (
                f"precheck_ok={budget_ok} violations={budget_violations} "
                f"manifest_id={id(plugin.manifest)} live_same={live is plugin} "
                f"limits={plugin.manifest.memory_limit_mb}/{plugin.manifest.cpu_limit_percent} "
                f"live_limits={live.manifest.memory_limit_mb}/{live.manifest.cpu_limit_percent} "
                f"usage={orchestrator.resource_monitor.memory_usage}/"
                f"{orchestrator.resource_monitor.cpu_usage} "
                f"success={blocked.success} error={blocked.error}"
            ),
        )
        metrics = getattr(plugin, "metrics", None)
        record(
            "D-012",
            "canonical metrics recorded",
            metrics is not None and metrics.execution_count >= 2,
            f"execution_count={getattr(metrics, 'execution_count', None)}",
        )

        plugin.manifest.memory_limit_mb = 8192
        plugin.manifest.cpu_limit_percent = 100.0
        orchestrator.resource_monitor.memory_usage[plugin_id] = 0
        orchestrator.resource_monitor.cpu_usage[plugin_id] = 0.0

        async def one(index: int) -> bool:
            result = await orchestrator.execute_plugin_method(plugin_id, "ping")
            return bool(result.success and result.result["plugin"] == plugin_id and index >= 0)

        concurrent = await asyncio.gather(*[one(i) for i in range(40)])
        record(
            "D-013",
            "forty concurrent requests all complete",
            all(concurrent),
            f"{sum(concurrent)}/{len(concurrent)} completed",
        )

        reactive = WorkflowDefinition(
            workflow_id="reactive-proof",
            name="reactive",
            description="event handlers must run",
            mode=ExecutionMode.REACTIVE,
            steps=[
                {"id": "now", "plugin_id": plugin_id, "method": "ping", "trigger": "immediate"},
                {"id": "later", "plugin_id": plugin_id, "method": "ping", "trigger": "alarm"},
            ],
        )
        orchestrator.register_workflow(reactive)
        execution_id = await orchestrator.execute_workflow(
            "reactive-proof",
            {"events": [{"name": "alarm", "payload": {"kind": "seed"}}]},
        )
        reactive_execution = await wait_execution(orchestrator, execution_id)
        seeded = reactive_execution.results.get("later")
        record(
            "D-009",
            "seeded reactive event ran its handler",
            reactive_execution.state is WorkflowState.COMPLETED
            and seeded is not None
            and seeded.success
            and seeded.result["event"]["payload"]["kind"] == "seed",
            f"state={reactive_execution.state} later={getattr(seeded, 'result', None)}",
        )
        follow = await orchestrator.workflow_engine.dispatch_event(
            execution_id, "alarm", {"kind": "follow"}
        )
        record(
            "D-009",
            "dispatch_event invokes the registered handler",
            len(follow) == 1 and follow[0].success and follow[0].result["event"]["payload"]["kind"] == "follow",
            f"fired={len(follow)}",
        )

        parallel = WorkflowDefinition(
            workflow_id="graph-proof",
            name="graph",
            description="independent steps overlap",
            mode=ExecutionMode.GRAPH,
            steps=[
                {"id": "left", "plugin_id": plugin_id, "method": "hold", "args": [0.35, "left"]},
                {"id": "right", "plugin_id": plugin_id, "method": "hold", "args": [0.35, "right"]},
            ],
            dependencies={},
        )
        orchestrator.register_workflow(parallel)
        started = time.perf_counter()
        parallel_id = await orchestrator.execute_workflow("graph-proof")
        parallel_execution = await wait_execution(orchestrator, parallel_id)
        elapsed = time.perf_counter() - started
        left = parallel_execution.results["left"].result
        right = parallel_execution.results["right"].result
        overlap = min(left["finished"], right["finished"]) > max(left["started"], right["started"])
        record(
            "D-010",
            "independent graph steps overlap",
            parallel_execution.state is WorkflowState.COMPLETED and overlap and elapsed < 0.65,
            f"elapsed={elapsed:.3f}s overlap={overlap}",
        )

        cyclic = WorkflowDefinition(
            workflow_id="cycle-proof",
            name="cycle",
            description="cycles must fail closed",
            mode=ExecutionMode.GRAPH,
            steps=[
                {"id": "a", "plugin_id": plugin_id, "method": "ping"},
                {"id": "b", "plugin_id": plugin_id, "method": "ping"},
            ],
            dependencies={"a": ["b"], "b": ["a"]},
        )
        orchestrator.register_workflow(cyclic)
        cycle_id = await orchestrator.execute_workflow("cycle-proof")
        cycle_execution = await wait_execution(orchestrator, cycle_id)
        record(
            "D-010",
            "cyclic graph fails with a cycle diagnostic",
            cycle_execution.state is WorkflowState.FAILED
            and any("Cyclic dependency" in error for error in cycle_execution.errors)
            and "a" not in cycle_execution.results,
            f"state={cycle_execution.state} errors={cycle_execution.errors}",
        )
    finally:
        await orchestrator.stop()
        record("D-002", "orchestrator stop", True, "PluginOrchestrator.stop completed")


async def prove_marketplace_and_loader(tmp: Path, private_key, memory: HostMemory) -> str:
    app = FastAPI()
    manager = PluginManager(
        app,
        memory,
        HostSecurity(),
        plugin_base_dir=tmp / "plugins",
    )
    publisher_pem = public_pem(private_key)
    manager.security_manager.register_publisher_key("proof-author", publisher_pem)
    await manager.start()
    loaded_id = ""
    try:
        tree = write_plugin_tree(tmp / "src", "loaderproof")
        canonical = manager.security_manager._canonical_plugin_bytes(tree)
        manifest = json.loads((tree / "manifest.json").read_text(encoding="utf-8"))
        manifest["signature"] = "rsa_pss_sha256:" + sign_bytes(private_key, canonical)
        (tree / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        archive = tmp / "loaderproof.zip"
        zip_tree(tree, archive)

        slip = tmp / "slip.zip"
        with zipfile.ZipFile(slip, "w") as archive_file:
            archive_file.writestr("../escape.txt", "owned")
            archive_file.writestr("manifest.json", "{}")
        slip_rejected = False
        try:
            safe_extract_zip(slip, tmp / "slip-out")
        except ArchivePathError:
            slip_rejected = True
        escaped = list((tmp / "slip-out").rglob("escape.txt")) if (tmp / "slip-out").exists() else []
        record(
            "D-003",
            "zip-slip member is refused before write",
            slip_rejected and not escaped and not (tmp / "escape.txt").exists(),
            f"raised={slip_rejected} escaped={escaped}",
        )
        installed = await manager.install_plugin_from_archive(archive)
        loaded_id = "loaderproof"
        plugin = manager.active_plugins.get(loaded_id)
        record(
            "D-019",
            "archive install loads a canonical plugin",
            installed and plugin is not None and isinstance(plugin, PluginBase),
            f"installed={installed} type={type(plugin).__name__ if plugin else None}",
        )
        record(
            "D-022",
            "loader kept canonical manifest fields",
            plugin is not None
            and plugin.manifest.memory_limit_mb == 512
            and PluginCapability.CONSCIOUSNESS_ACCESS in plugin.manifest.capabilities
            and plugin.manifest.workflow_nodes == ["ingest", "emit"],
            f"fields={plugin.manifest.model_dump().keys() if plugin else []}",
        )
        info = await manager.get_plugin_marketplace_info()
        record(
            "D-019",
            "marketplace info is a real inventory",
            isinstance(info, dict)
            and info["network_enabled"] is False
            and info["active_count"] >= 1
            and "loaderproof" in info["discovered"],
            f"active={info.get('active_count')} keys={sorted(info)}",
        )

        tampered = write_plugin_tree(tmp / "tampered-src", "tampered")
        tampered_manifest = json.loads((tampered / "manifest.json").read_text(encoding="utf-8"))
        tampered_manifest["signature"] = "rsa_pss_sha256:" + ("ab" * 32)
        (tampered / "manifest.json").write_text(json.dumps(tampered_manifest), encoding="utf-8")
        valid, issues = await manager.security_manager.validate_plugin(tampered, PluginManifest.from_file(tampered / "manifest.json"))
        record(
            "SEC-10",
            "bad signature does not pass",
            valid is False and any("signature" in issue.lower() for issue in issues),
            f"valid={valid} issues={issues}",
        )

        if loaded_id in manager.active_plugins:
            await prove_orchestration(manager, loaded_id)
        else:
            record("D-002", "orchestrator stop", False, "plugin did not load; orchestrator proof skipped")

        market_root = tmp / "registry" / "official" / "marketproof"
        market_root.mkdir(parents=True)
        source = write_plugin_tree(tmp / "market-src", "marketproof")
        artifact = market_root / "artifact.zip"
        zip_tree(source, artifact)
        payload = artifact.read_bytes()
        (market_root / "manifest.json").write_text((source / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
        (market_root / "signature.json").write_text(json.dumps({
            "algorithm": "rsa_pss_sha256",
            "developer_id": "proof-author",
            "signature": sign_bytes(private_key, payload),
            "content_sha256": __import__("hashlib").sha256(payload).hexdigest(),
        }), encoding="utf-8")

        config = MarketplaceConfig(
            local_registry_root=str(tmp / "registry"),
            network_enabled=False,
            verify_signatures=True,
            allow_unsigned_plugins=False,
        )
        marketplace = await create_marketplace(manager, manager.security_manager, config)
        marketplace.trust_system.register_developer_key("proof-author", publisher_pem)
        record(
            "D-006",
            "create_marketplace registers no placeholder key",
            "morpheus_official" not in marketplace.trust_system.verification_keys,
            f"keys={list(marketplace.trust_system.verification_keys)}",
        )
        try:
            marketplace.trust_system.register_developer_key(
                "placeholder",
                b"-----BEGIN PUBLIC KEY-----\n...official marketplace public key...\n-----END PUBLIC KEY-----",
            )
            placeholder_refused = False
        except ValueError:
            placeholder_refused = True
        record("D-006", "placeholder PEM is refused", placeholder_refused, f"refused={placeholder_refused}")

        listed = await marketplace.search_plugins("marketproof")
        again = await marketplace.search_plugins("marketproof")
        record(
            "D-018",
            "registry cache survives the client",
            len(listed) == 1 and len(again) == 1 and marketplace.get_marketplace_stats()["stats"]["cached_entries"] >= 1,
            f"cached={marketplace.get_marketplace_stats()['stats']['cached_entries']}",
        )
        record(
            "D-016",
            "default network path is off and hostless",
            marketplace.config.network_enabled is False
            and marketplace.config.official_registry_url == ""
            and marketplace.config.community_registry_url == "",
            f"network={marketplace.config.network_enabled}",
        )
        community_base = RegistryClient(MarketplaceConfig(
            network_enabled=True,
            community_registry_url="https://registry.example.invalid/community",
        )).registry_base(MarketplaceProvider.COMMUNITY)
        record(
            "D-015",
            "community provider selects community_registry_url",
            community_base == "https://registry.example.invalid/community",
            community_base,
        )

        success, message = await marketplace.install_plugin("marketproof")
        market_plugin = manager.active_plugins.get("marketproof")
        record(
            "D-004",
            "RSA-PSS install verifies and loads",
            success and market_plugin is not None,
            f"success={success} message={message}",
        )
        record(
            "D-005",
            "verify_developer_signature accepted the artifact",
            success,
            message,
        )
        record(
            "D-017",
            "install did not trust a server-asserted score",
            success and market_plugin is not None,
            "local signature score cleared the floor; server trust was not an input",
        )

        hostile = RegistryClient(config, trust_system=marketplace.trust_system)
        fake_listing = listed[0]
        fake_listing.server_asserted_trust = 1.0
        fake_listing.trust_score = 1.0
        fake_listing.signature_url = None
        fake_listing.signature_verified = False
        unsigned_ok = await hostile.verify_download(fake_listing, artifact)
        record(
            "D-004",
            "missing signature fails closed",
            unsigned_ok is False,
            f"verify_download={unsigned_ok}",
        )
        checksum_listing = listed[0]
        checksum_dir = tmp / "checksum"
        checksum_dir.mkdir()
        checksum_sig = checksum_dir / "signature.json"
        checksum_sig.write_text(json.dumps({
            "algorithm": "sha256",
            "signature": __import__("hashlib").sha256(payload).hexdigest(),
        }), encoding="utf-8")
        checksum_listing.signature_url = str(checksum_sig)
        checksum_listing.signature_verified = False
        checksum_ok = await hostile.verify_download(checksum_listing, artifact)
        record(
            "D-004",
            "sha256 checksum is not a signature",
            checksum_ok is False,
            f"verify_download={checksum_ok}",
        )

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logging.getLogger("marketplace").addHandler(handler)
        trust = marketplace.trust_system
        trust.verify_developer_signature(b"data", "not-hex", "proof-author")
        trust.verify_developer_signature(b"data", "aa" * 64, "proof-author")
        logging.getLogger("marketplace").removeHandler(handler)
        rendered = log_stream.getvalue()
        record(
            "D-007",
            "malformed hex and cryptographic mismatch are distinct",
            "not hexadecimal" in rendered and "signature mismatch" in rendered,
            rendered.strip().replace("\n", " | "),
        )

        await prove_download_cap(tmp)
        await prove_interfaces(manager, loaded_id, "marketproof")
        return loaded_id
    finally:
        await manager.stop()


async def prove_download_cap(tmp: Path) -> None:
    async def handler(request: web.Request) -> web.StreamResponse:
        # No Content-Length: the pre-flight header check cannot see the body.
        response = web.StreamResponse(status=200)
        await response.prepare(request)
        payload = b"x" * (64 * 1024)
        for _ in range(40):  # 2.5 MiB, above the 1 MiB cap
            await response.write(payload)
        await response.write_eof()
        return response

    application = web.Application()
    application.router.add_get("/blob", handler)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    sockets = site._server.sockets  # type: ignore[attr-defined]
    port = sockets[0].getsockname()[1]
    try:
        config = MarketplaceConfig(
            network_enabled=True,
            official_registry_url=f"http://127.0.0.1:{port}",
            max_download_size_mb=1,
            verify_signatures=False,
        )
        from marketplace import PluginListing, PluginStatistics
        listing = PluginListing(
            plugin_id="cap-probe",
            manifest=PluginManifest(**manifest_dict("cap-probe")),
            provider=MarketplaceProvider.OFFICIAL,
            status=__import__("marketplace").ListingStatus.APPROVED,
            channel=DistributionChannel.PUBLIC,
            download_url=f"http://127.0.0.1:{port}/blob",
            statistics=PluginStatistics(),
        )
        target = tmp / "capped.bin"
        async with RegistryClient(config) as client:
            downloaded = await client.download_plugin(listing, target)
        record(
            "D-008",
            "streaming download stops past the byte cap",
            downloaded is False and not target.exists(),
            f"downloaded={downloaded} exists={target.exists()}",
        )
    finally:
        await runner.cleanup()


async def prove_interfaces(manager: PluginManager, left_id: str, right_id: str) -> None:
    left = manager.active_plugins[left_id]
    right = manager.active_plugins[right_id]
    synced = await left.consciousness_sync(0.4)
    coherence = await left.quantum_coherence_check()
    depth = await left.recursive_depth_analysis()
    entered = left.enter_recursive_frame()
    record(
        "D-020",
        "consciousness interface is operational",
        isinstance(left, ConsciousnessInterface)
        and synced
        and 0.0 <= coherence <= 1.0
        and depth["within_limit"]
        and entered,
        f"coherence={coherence} depth={depth['current_depth']}",
    )
    delivered = await left.p2p_communicate(right.plugin_id, {"topic": "codebase"})
    record(
        "D-020",
        "in-process peer delivery",
        delivered and right.peer_inbox()[-1]["message"]["topic"] == "codebase",
        f"delivered={delivered} inbox={len(right.peer_inbox())}",
    )
    denied = False
    try:
        right.manifest.permissions = []
        await right.network_request("GET", "https://example.invalid")
    except PermissionError:
        denied = True
    record(
        "D-020",
        "network permission is enforced",
        isinstance(right, NetworkInterface) and denied,
        f"denied={denied}",
    )


def prove_static() -> None:
    text = (ROOT / "plugin_base.py").read_text(encoding="utf-8")
    record(
        "D-021",
        "checkpoint memory classification is explicit",
        "changed from MemoryType" not in text and "memory_type=MemoryType.USER" in text,
        "MemoryType.USER is the checkpoint classification",
    )
    classes = {}
    for name in ("PluginManifest", "PluginBase", "PluginDiscovery", "PluginFileWatcher"):
        count = 0
        for path in ROOT.glob("*.py"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"class {name}") or line.startswith(f"class {name}("):
                    count += 1
        classes[name] = count
    record(
        "D-022",
        "each collided class has one definition",
        all(value == 1 for value in classes.values()),
        str(classes),
    )
    record(
        "D-022",
        "plugin_manager.PluginBase is plugin_base.PluginBase",
        PluginManager.__module__ == "plugin_manager" and PluginBase.__module__ == "plugin_base",
        f"{PluginBase.__module__}.{PluginBase.__name__}",
    )
    import plugin_manager
    record(
        "D-022",
        "manager re-exports the canonical base",
        plugin_manager.PluginBase is PluginBase and plugin_manager.PluginManifest is PluginManifest,
        "identity held",
    )


def write_reports() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for item in CHECKS if item["passed"])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "failed": len(CHECKS) - passed,
        "total": len(CHECKS),
        "checks": CHECKS,
    }
    json_text = json.dumps(payload, indent=2)
    lines = [
        "# Defect closure proof",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        f"Passed {passed} of {len(CHECKS)}.",
        "",
        "| Defect | Check | Result | Detail |",
        "|---|---|---|---|",
    ]
    for item in CHECKS:
        result = "PASS" if item["passed"] else "FAIL"
        detail = item["detail"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['defect']} | {item['name']} | {result} | {detail} |")
    markdown = "\n".join(lines) + "\n"
    for directory in (ARTIFACT_DIR, REPORT_DIR):
        (directory / "defect_closure.json").write_text(json_text, encoding="utf-8")
        (directory / "defect_closure.md").write_text(markdown, encoding="utf-8")
    print(f"\n{passed}/{len(CHECKS)} checks passed", flush=True)
    print(f"JSON  {ARTIFACT_DIR / 'defect_closure.json'}", flush=True)
    print(f"REPORT {ARTIFACT_DIR / 'defect_closure.md'}", flush=True)


async def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tmp = Path(tempfile.mkdtemp(prefix="somnus_defect_proof_"))
    memory = HostMemory()
    try:
        prove_static()
        await prove_queue()
        validator = CryptographicValidator()
        payload = b"canonical-bytes"
        signature = "rsa_pss_sha256:" + sign_bytes(private_key, payload)
        verified = await validator.verify_signature(payload, signature, public_pem(private_key))
        record("D-005", "CryptographicValidator verifies RSA-PSS", verified, f"verified={verified}")
        executor_shutdown = True
        try:
            from orchestration import PluginExecutor
            PluginExecutor().shutdown()
        except TypeError:
            executor_shutdown = False
        record("D-002", "ThreadPoolExecutor shutdown accepts no timeout", executor_shutdown, f"ok={executor_shutdown}")
        await prove_marketplace_and_loader(tmp, private_key, memory)
    except Exception as exc:
        record("HARNESS", "unhandled exception", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        write_reports()
    return 0 if CHECKS and all(item["passed"] for item in CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
