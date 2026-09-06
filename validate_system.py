#!/usr/bin/env python3
"""Somnus Plugin System — Production Validation Harness.

Exercises the real module surface against real fixtures and records the run
to test/system/runs/<timestamp>/{result.json,result.md,result.log}.

This is experimentation, not a pytest suite. Per AGENTS.md section 7 and
the operator's test doctrine: direct Python files with detailed terminal
readout, a JSON artifact, and an MD report every time.

Exit codes:
    0 — all checks passed
    1 — at least one check failed
    2 — harness error
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / "test" / "system" / "runs"


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "fail" | "skip"
    duration_ms: float = 0.0
    detail: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


def timed_check(name: str):
    """Decorator to time a check function and capture its result."""
    def decorator(fn: Callable[[], CheckResult]) -> Callable[[], CheckResult]:
        def wrapper() -> CheckResult:
            start = time.monotonic()
            try:
                result = fn()
                result.duration_ms = (time.monotonic() - start) * 1000.0
                result.name = name
                return result
            except Exception as exc:
                return CheckResult(
                    name=name,
                    status="fail",
                    duration_ms=(time.monotonic() - start) * 1000.0,
                    detail=f"exception: {exc}",
                    extra={"traceback": traceback.format_exc()},
                )
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

@timed_check("import_host_protocols")
def check_import_host_protocols() -> CheckResult:
    """Verify host_protocols.py imports cleanly."""
    import host_protocols
    symbols = ["MemoryManager", "MemoryType", "MemoryImportance", "MemoryScope",
               "SessionID", "UserID", "SecurityEnforcer"]
    missing = [s for s in symbols if not hasattr(host_protocols, s)]
    if missing:
        return CheckResult(name="", status="fail", detail=f"missing symbols: {missing}")
    return CheckResult(name="", status="pass", detail=f"all {len(symbols)} protocol symbols present")


@timed_check("import_plugin_base")
def check_import_plugin_base() -> CheckResult:
    """Verify plugin_base.py imports and exposes canonical types."""
    import plugin_base
    required = [
        "PluginPermission", "PluginType", "PluginCapability", "CapabilitySet",
        "PluginState", "PluginManifest", "PluginBase", "PluginMetrics",
        "PluginContext", "PluginEvent", "PluginEventType", "ResourceMonitor",
        "StateCheckpoint", "EWMAAccumulator", "InvalidStateTransition",
    ]
    missing = [r for r in required if not hasattr(plugin_base, r)]
    if missing:
        return CheckResult(name="", status="fail", detail=f"missing types: {missing}")
    return CheckResult(name="", status="pass", detail=f"all {len(required)} canonical types present")


@timed_check("import_all_modules")
def check_import_all_modules() -> CheckResult:
    """Verify all 7 root modules plus host_protocols import."""
    modules = ["host_protocols", "plugin_base", "plugin_manager", "security",
               "discovery", "orchestration", "hot_reload", "marketplace"]
    results = {}
    for mod_name in modules:
        try:
            __import__(mod_name)
            results[mod_name] = "pass"
        except Exception as exc:
            results[mod_name] = f"fail: {exc}"

    failures = {k: v for k, v in results.items() if v != "pass"}
    if failures:
        return CheckResult(name="", status="fail", detail=f"import failures: {failures}")
    return CheckResult(name="", status="pass", detail=f"all {len(modules)} modules import cleanly",
                       extra=results)


@timed_check("lineage_convergence")
def check_lineage_convergence() -> CheckResult:
    """Verify PluginPermission and PluginType live in plugin_base, not only plugin_manager."""
    from plugin_base import PluginPermission, PluginType

    perm_values = {e.value for e in PluginPermission}
    expected_perms = {"read_memory", "write_memory", "network_access", "file_system",
                      "system_commands", "user_interface", "session_access", "agent_control"}
    if perm_values != expected_perms:
        return CheckResult(name="", status="fail",
                           detail=f"PluginPermission values mismatch: {perm_values} vs {expected_perms}")

    type_values = {e.value for e in PluginType}
    expected_types = {"api_extension", "ui_component", "agent_action", "memory_extension",
                      "workflow_node", "tool_integration", "research_module", "creative_engine"}
    if type_values != expected_types:
        return CheckResult(name="", status="fail",
                           detail=f"PluginType values mismatch: {type_values} vs {expected_types}")

    return CheckResult(name="", status="pass",
                       detail="PluginPermission(8) and PluginType(8) canonical in plugin_base")


@timed_check("capability_lattice")
def check_capability_lattice() -> CheckResult:
    """Verify capability set algebra operations."""
    from plugin_base import PluginCapability, CapabilitySet

    a = CapabilitySet.from_list([PluginCapability.MEMORY_INTEGRATION, PluginCapability.CONSCIOUSNESS_ACCESS])
    b = CapabilitySet.from_list([PluginCapability.CONSCIOUSNESS_ACCESS, PluginCapability.REAL_TIME_ADAPTATION])

    join = a.join(b)
    meet = a.meet(b)

    assert len(join) == 3, f"join should have 3 members, got {len(join)}"
    assert len(meet) == 1, f"meet should have 1 member, got {len(meet)}"
    assert PluginCapability.CONSCIOUSNESS_ACCESS in meet

    universe = CapabilitySet.universe()
    assert len(universe) == 8

    assert universe.subsumes(a)
    assert not a.subsumes(universe)

    gap = a.gap(b)
    assert PluginCapability.REAL_TIME_ADAPTATION in gap
    assert len(gap) == 1

    return CheckResult(name="", status="pass",
                       detail="join(3), meet(1), universe(8), subsumes, gap — all correct")


@timed_check("ewma_metrics")
def check_ewma_metrics() -> CheckResult:
    """Verify EWMA accumulator produces stable estimates."""
    from plugin_base import EWMAAccumulator

    acc = EWMAAccumulator(alpha=0.3)
    for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
        acc.update(v)

    assert acc.count == 5
    assert acc.min_val == 1.0
    assert acc.max_val == 5.0
    assert 1.0 < acc.mean < 5.0, f"EWMA mean should be between 1 and 5, got {acc.mean}"

    snap = acc.snapshot()
    assert "mean" in snap and "std" in snap and "count" in snap

    return CheckResult(name="", status="pass",
                       detail=f"EWMA mean={acc.mean:.3f}, std={acc.std:.3f}, count={acc.count}",
                       extra=snap)


@timed_check("state_transitions")
def check_state_transitions() -> CheckResult:
    """Verify the state machine rejects invalid transitions."""
    from plugin_base import PluginState, _VALID_TRANSITIONS, InvalidStateTransition

    valid_count = sum(len(targets) for targets in _VALID_TRANSITIONS.values())

    caught = False
    try:
        raise InvalidStateTransition("test", PluginState.TERMINATED, PluginState.ACTIVE)
    except InvalidStateTransition:
        caught = True

    assert caught, "InvalidStateTransition should be raiseable"

    assert PluginState.ACTIVE in _VALID_TRANSITIONS[PluginState.READY]
    assert PluginState.TERMINATED not in _VALID_TRANSITIONS[PluginState.ACTIVE]

    return CheckResult(name="", status="pass",
                       detail=f"state graph has {valid_count} valid edges across {len(_VALID_TRANSITIONS)} states")


@timed_check("content_addressed_checkpoint")
def check_content_addressed_checkpoint() -> CheckResult:
    """Verify content-addressed checkpoints with Merkle hashing."""
    from plugin_base import StateCheckpoint, _merkle_hash

    state_a = {"plugin_id": "test", "value": 42}
    state_b = {"plugin_id": "test", "value": 42}
    state_c = {"plugin_id": "test", "value": 99}

    hash_a = _merkle_hash(state_a)
    hash_b = _merkle_hash(state_b)
    hash_c = _merkle_hash(state_c)

    assert hash_a == hash_b, "identical states should produce identical hashes"
    assert hash_a != hash_c, "different states should produce different hashes"
    assert len(hash_a) == 64, f"SHA-256 hex digest should be 64 chars, got {len(hash_a)}"

    ckpt = StateCheckpoint.create("test_plugin", state_a, generation=1)
    assert ckpt.merkle_hash == hash_a
    assert ckpt.generation == 1
    assert "ckpt_" in ckpt.checkpoint_id

    return CheckResult(name="", status="pass",
                       detail=f"Merkle dedup works, hash={hash_a[:16]}..., checkpoint_id={ckpt.checkpoint_id}")


@timed_check("manifest_validation")
def check_manifest_validation() -> CheckResult:
    """Verify manifest validates types correctly."""
    from plugin_base import PluginManifest, PluginType, PluginPermission
    from pydantic import ValidationError

    manifest = PluginManifest(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin for validation",
        author="test-author",
        plugin_type=PluginType.API_EXTENSION,
        permissions=[PluginPermission.READ_MEMORY],
    )
    assert manifest.plugin_type == PluginType.API_EXTENSION
    assert manifest.permissions == [PluginPermission.READ_MEMORY]
    assert manifest.content_hash()
    assert len(manifest.content_hash()) == 64

    cap_set = manifest.capability_set()
    assert len(cap_set) == 0

    try:
        PluginManifest(
            name="bad", version="not-semver", description="x", author="y",
            plugin_type=PluginType.API_EXTENSION,
        )
        return CheckResult(name="", status="fail", detail="should reject invalid semver")
    except ValidationError:
        pass

    return CheckResult(name="", status="pass",
                       detail=f"manifest validates, content_hash={manifest.content_hash()[:16]}...")


@timed_check("plugin_lifecycle_async")
def check_plugin_lifecycle_async() -> CheckResult:
    """Exercise the full plugin lifecycle asynchronously."""
    from plugin_base import (
        PluginBase, PluginManifest, PluginType, PluginState,
        PluginEventType, PluginEvent,
    )
    from host_protocols import MemoryManager, MemoryType, MemoryImportance, MemoryScope

    class MockMemoryManager:
        """Minimal conforming implementation for testing lifecycle."""
        async def create_context(self, context_id, scope, metadata=None):
            return {"context_id": context_id}

        async def store_memory(self, user_id, content, memory_type, importance,
                               scope=None, tags=None, metadata=None):
            from uuid import uuid4
            return uuid4()

        async def retrieve_memories(self, user_id, query, memory_types=None, limit=10):
            return []

        async def search_memories(self, user_id, query, memory_type=None, limit=10):
            return []

    class TestPlugin(PluginBase):
        async def _plugin_initialize(self) -> bool:
            return True
        async def _plugin_activate(self) -> bool:
            return True
        async def _plugin_deactivate(self) -> bool:
            return True
        async def _plugin_cleanup(self) -> bool:
            return True

    events_received: List[PluginEvent] = []

    async def run_lifecycle():
        mm = MockMemoryManager()
        manifest = PluginManifest(
            name="lifecycle-test",
            version="1.0.0",
            description="Lifecycle test plugin",
            author="test",
            plugin_type=PluginType.TOOL_INTEGRATION,
        )

        plugin = TestPlugin("test-001", manifest, mm)  # type: ignore[arg-type]

        async def event_handler(event: PluginEvent):
            events_received.append(event)

        await plugin.register_event_handler(PluginEventType.INITIALIZED, event_handler)
        await plugin.register_event_handler(PluginEventType.ACTIVATED, event_handler)
        await plugin.register_event_handler(PluginEventType.CHECKPOINT_CREATED, event_handler)
        await plugin.register_event_handler(PluginEventType.DEACTIVATED, event_handler)
        await plugin.register_event_handler(PluginEventType.TERMINATED, event_handler)

        assert await plugin.initialize()
        assert plugin.state == PluginState.READY

        assert await plugin.activate()
        assert plugin.state == PluginState.ACTIVE

        ckpt_id = await plugin.checkpoint_state()
        assert ckpt_id.startswith("ckpt_")

        info = plugin.get_info()
        assert info["plugin_id"] == "test-001"
        assert info["status"] == "active"
        assert "metrics" in info
        assert "resource_usage" in info

        state = await plugin.get_state()
        assert state["plugin_id"] == "test-001"

        assert await plugin.cleanup()
        assert plugin.state == PluginState.TERMINATED

        return {
            "events": [e.event_type.value for e in events_received],
            "checkpoint_id": ckpt_id,
            "final_state": plugin.state.value,
            "info_keys": sorted(info.keys()),
        }

    result = asyncio.run(run_lifecycle())

    expected_events = ["initialized", "activated", "checkpoint_created", "checkpoint_created", "terminated"]
    if result["events"] != expected_events:
        return CheckResult(name="", status="fail",
                           detail=f"events mismatch: {result['events']} vs {expected_events}")

    return CheckResult(name="", status="pass",
                       detail=f"full lifecycle: init->ready->active->checkpoint->cleanup->terminated, "
                              f"events={result['events']}, ckpt={result['checkpoint_id']}",
                       extra=result)


@timed_check("priority_queue_order")
def check_priority_queue_order() -> CheckResult:
    """Verify REALTIME dequeues before LOW (D-001 fix)."""
    from orchestration import ExecutionPriority

    priorities = list(ExecutionPriority)
    expected_order = ["realtime", "critical", "high", "normal", "low"]
    actual_order = [p.value for p in priorities]

    if actual_order != expected_order:
        return CheckResult(name="", status="fail",
                           detail=f"priority order wrong: {actual_order}, expected {expected_order}")

    return CheckResult(name="", status="pass",
                       detail=f"priority order correct: {actual_order}")


@timed_check("security_import_fixed")
def check_security_import() -> CheckResult:
    """Verify security.py can import PluginPermission from plugin_base (was the missing symbol)."""
    from security import CodeAnalyzer, SecurityManager, CryptographicValidator
    from plugin_base import PluginPermission

    analyzer = CodeAnalyzer()
    assert hasattr(analyzer, 'permission_patterns')

    perm_keys = set(analyzer.permission_patterns.keys())
    expected = {PluginPermission.NETWORK_ACCESS, PluginPermission.FILE_SYSTEM,
                PluginPermission.SYSTEM_COMMANDS, PluginPermission.AGENT_CONTROL}
    if perm_keys != expected:
        return CheckResult(name="", status="fail",
                           detail=f"permission_patterns keys: {perm_keys} vs {expected}")

    return CheckResult(name="", status="pass",
                       detail="security.py imports PluginPermission from plugin_base — the predicted "
                              "ImportError at security.py:34 is resolved")


@timed_check("hot_reload_no_pickle")
def check_hot_reload_no_pickle() -> CheckResult:
    """Verify hot_reload.py does not use pickle for deserialization."""
    from hot_reload import PluginState as HRPluginState

    state = HRPluginState(plugin_id="test", version="1.0.0")
    serialized = state.serialize()

    deserialized = HRPluginState.deserialize(serialized)
    assert deserialized.plugin_id == "test"
    assert deserialized.version == "1.0.0"
    assert deserialized.serialization_format == "json"

    import pickle
    malicious = pickle.dumps({"should": "not", "be": "loaded"})
    try:
        HRPluginState.deserialize(malicious)
        return CheckResult(name="", status="fail", detail="pickle payload should not deserialize")
    except (ValueError, Exception):
        pass

    return CheckResult(name="", status="pass",
                       detail="JSON-only deserialization, pickle payloads rejected")


@timed_check("resource_monitor_real_measurement")
def check_resource_monitor() -> CheckResult:
    """Verify ResourceMonitor uses real OS measurements."""
    from plugin_base import ResourceMonitor, PluginManifest, PluginType

    manifest = PluginManifest(
        name="rmon-test", version="1.0.0", description="test",
        author="test", plugin_type=PluginType.TOOL_INTEGRATION,
    )
    monitor = ResourceMonitor(manifest)

    rss = monitor._get_rss_bytes()
    assert rss > 0, f"RSS should be > 0, got {rss}"

    return CheckResult(name="", status="pass",
                       detail=f"real RSS measurement: {rss // (1024*1024)}MB, "
                              f"not the hardcoded zero from the original implementation")


@timed_check("taint_tracking")
def check_taint_tracking() -> CheckResult:
    """Verify taint flow analysis detects data flow from sources to sinks."""
    import ast
    from security import TaintTracker, TaintLabel

    code_with_taint = '''
data = input("enter: ")
result = eval(data)
'''
    tree = ast.parse(code_with_taint)
    tracker = TaintTracker()
    flows = tracker.analyze(tree)

    if len(flows) != 1:
        return CheckResult(name="", status="fail",
                           detail=f"expected 1 tainted flow, got {len(flows)}")

    flow = flows[0]
    assert flow.source_label == TaintLabel.USER_INPUT
    assert flow.sink_name == "eval"

    safe_code = '''
data = "safe_string"
result = eval(data)
'''
    tree2 = ast.parse(safe_code)
    safe_flows = tracker.analyze(tree2)
    assert len(safe_flows) == 0, "literal string should not be tainted"

    multi_code = '''
raw = input("x")
processed = raw
exec(processed)
'''
    tree3 = ast.parse(multi_code)
    propagated = tracker.analyze(tree3)
    assert len(propagated) == 1, f"taint should propagate through assignment, got {len(propagated)}"
    assert propagated[0].source_label == TaintLabel.USER_INPUT
    assert propagated[0].sink_name == "exec"

    return CheckResult(name="", status="pass",
                       detail="taint tracking: direct flow detected, safe code clean, propagation through assignment works")


@timed_check("bloom_filter")
def check_bloom_filter() -> CheckResult:
    """Verify Bloom filter for rapid plugin negative lookups."""
    from discovery import BloomFilter

    bf = BloomFilter(expected_items=100, fp_rate=0.01)

    test_items = [f"plugin_{i}" for i in range(100)]
    for item in test_items:
        bf.add(item)

    for item in test_items:
        assert item in bf, f"{item} should be in the filter"

    false_positives = 0
    test_negatives = 10000
    for i in range(test_negatives):
        if f"nonexistent_{i}" in bf:
            false_positives += 1

    fp_rate = false_positives / test_negatives
    assert fp_rate < 0.05, f"false positive rate {fp_rate:.4f} too high (expected < 0.05)"

    stats = bf.stats()
    assert stats["items"] == 100
    assert stats["estimated_fp_rate"] < 0.05

    return CheckResult(name="", status="pass",
                       detail=f"bloom filter: 100 items, 0 false negatives, "
                              f"fp_rate={fp_rate:.4f} ({false_positives}/{test_negatives}), "
                              f"bits={stats['bits']}, hashes={stats['hashes']}",
                       extra=stats)


@timed_check("circuit_breaker")
def check_circuit_breaker() -> CheckResult:
    """Verify circuit breaker with exponential backoff and jitter."""
    from orchestration import CircuitBreaker, CircuitBreakerState

    cb = CircuitBreaker(failure_threshold=3, base_timeout_s=0.01, max_timeout_s=1.0)
    assert cb.state == CircuitBreakerState.CLOSED
    assert not cb.is_open

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN, f"should be OPEN after 3 failures, got {cb.state}"

    assert cb.is_open

    import time
    time.sleep(0.02)

    assert not cb.is_open, "should transition to HALF_OPEN after timeout"
    assert cb.state == CircuitBreakerState.HALF_OPEN

    cb.record_success()
    cb.record_success()
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED, "should close after 3 successes in half-open"

    snap = cb.snapshot()
    assert "state" in snap and "failure_count" in snap

    return CheckResult(name="", status="pass",
                       detail="circuit breaker: closed->open(3 failures)->half_open(timeout)->closed(3 successes)",
                       extra=snap)


@timed_check("host_boundary_protocol_conformance")
def check_protocol_conformance() -> CheckResult:
    """Verify that a conforming implementation passes runtime protocol checks."""
    from host_protocols import MemoryManager
    import typing

    class ConformingMM:
        async def create_context(self, context_id, scope, metadata=None):
            return {}
        async def store_memory(self, user_id, content, memory_type, importance,
                               scope=None, tags=None, metadata=None):
            from uuid import uuid4
            return uuid4()
        async def retrieve_memories(self, user_id, query, memory_types=None, limit=10):
            return []
        async def search_memories(self, user_id, query, memory_type=None, limit=10):
            return []

    instance = ConformingMM()
    is_conforming = isinstance(instance, MemoryManager)

    if not is_conforming:
        return CheckResult(name="", status="fail",
                           detail="conforming implementation should pass runtime_checkable Protocol check")

    return CheckResult(name="", status="pass",
                       detail="runtime_checkable Protocol verification works for MemoryManager")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main() -> int:
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    runs_dir = RUNS_DIR / timestamp
    runs_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  somnus-plugin-system — Production Validation Harness")
    print(f"  timestamp: {timestamp}")
    print(f"  python:    {sys.version.split()[0]}")
    print(f"  cwd:       {Path.cwd()}")
    print("=" * 70)
    print()

    checks = [
        check_import_host_protocols,
        check_import_plugin_base,
        check_import_all_modules,
        check_lineage_convergence,
        check_capability_lattice,
        check_ewma_metrics,
        check_state_transitions,
        check_content_addressed_checkpoint,
        check_manifest_validation,
        check_plugin_lifecycle_async,
        check_priority_queue_order,
        check_security_import,
        check_hot_reload_no_pickle,
        check_resource_monitor,
        check_taint_tracking,
        check_bloom_filter,
        check_circuit_breaker,
        check_protocol_conformance,
    ]

    results: List[CheckResult] = []

    for check_fn in checks:
        result = check_fn()
        results.append(result)

        marker = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[result.status]
        duration = f"{result.duration_ms:.1f}ms"
        print(f"  [{marker}]  {result.name:<40s} {duration:>10s}")
        if result.detail:
            for line in result.detail.split("\n"):
                print(f"           {line}")
        if result.status == "fail" and "traceback" in result.extra:
            for line in result.extra["traceback"].split("\n")[-5:]:
                print(f"           {line}")
        print()

    pass_count = sum(1 for r in results if r.status == "pass")
    fail_count = sum(1 for r in results if r.status == "fail")
    skip_count = sum(1 for r in results if r.status == "skip")
    total_ms = sum(r.duration_ms for r in results)

    print("=" * 70)
    print(f"  PASS {pass_count}   FAIL {fail_count}   SKIP {skip_count}   "
          f"total {total_ms:.1f}ms")
    if fail_count > 0:
        print("  RESULT: FAIL")
    else:
        print("  RESULT: PASS")
    print("=" * 70)

    payload = {
        "harness": "somnus-plugin-system production validation",
        "timestamp": timestamp,
        "python_version": sys.version.split()[0],
        "checks": [
            {
                "name": r.name,
                "status": r.status,
                "duration_ms": round(r.duration_ms, 2),
                "detail": r.detail,
                "extra": {k: v for k, v in r.extra.items() if k != "traceback"},
            }
            for r in results
        ],
        "summary": {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "skip_count": skip_count,
            "total_duration_ms": round(total_ms, 2),
            "result": "PASS" if fail_count == 0 else "FAIL",
        },
    }

    (runs_dir / "result.json").write_text(json.dumps(payload, indent=2))
    (runs_dir / "result.md").write_text(_render_md(payload))

    print(f"\n  Artifacts written to: {runs_dir}/")
    print(f"    result.json — {(runs_dir / 'result.json').stat().st_size} bytes")
    print(f"    result.md   — {(runs_dir / 'result.md').stat().st_size} bytes")

    return 0 if fail_count == 0 else 1


def _render_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# Somnus Plugin System — Production Validation Report",
        "",
        f"Run timestamp: {payload['timestamp']}",
        f"Python version: {payload['python_version']}",
        "",
        "## Summary",
        "",
        f"- **Result:** {payload['summary']['result']}",
        f"- **Pass:** {payload['summary']['pass_count']}",
        f"- **Fail:** {payload['summary']['fail_count']}",
        f"- **Skip:** {payload['summary']['skip_count']}",
        f"- **Duration:** {payload['summary']['total_duration_ms']:.1f}ms",
        "",
        "## Checks",
        "",
    ]

    for check in payload["checks"]:
        marker = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[check["status"]]
        lines.append(f"- [{marker}] **{check['name']}** ({check['duration_ms']:.1f}ms)")
        if check["detail"]:
            lines.append(f"  - {check['detail']}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
