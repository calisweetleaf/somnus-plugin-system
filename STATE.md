# STATE — somnus-plugin-system

> **Charter:** single-screen current runtime truth. What is true *right now*.
>
> **Refresh on every state change.** A stale `STATE.md` is worse than none.

**Last refreshed:** 2026-09-18
**Working tree:** PACKET-002 remainder + PACKET-004 in progress on `cursor/plugin-runtime-heartbeat-863f`

---

## 1. Does it run?

**Yes.** All 8 modules import. The production loader loads a canonical plugin.

| Fact | Status |
|---|---|
| Dependencies installed | **OBSERVED** — `.venv` present |
| All modules import | **OBSERVED** — `gate.sh` section 6 PASS including `host_protocols` |
| Host boundary | **OBSERVED** — Protocol seam in `host_protocols.py`. Zero donor imports. |
| Lineage convergence | **OBSERVED** — `PluginManifest`, `PluginBase`, `PluginDiscovery`, `PluginFileWatcher` each defined once. Gate section [3] PASS. |
| Reference plugin | **OBSERVED** — `installed/example_plugin/` is populated. Runtime id `example_plugin_1.0.0`. |
| Production path | **OBSERVED** — `validate_system.py` `production_load_path` PASS: discover → security → load → ping → checkpoint → restore → unload |
| Validation harness | **19/19 PASS** — 18 component checks + 1 production-path check. This is **not** the adversarial suite (PACKET-007). |
| Gate | **PASS** on runnable checks. 0 PENDING. 2 NOT RUN (packet validator missing; no pytest suite by design). |

## 2. What is the gate posture?

`bash gate.sh` → PASS on 19 runnable checks. 0 PENDING. 2 NOT RUN.

## 3. What is the active packet?

| Packet | Status |
|---|---|
| PACKET-001 | LANDED |
| PACKET-002 | LANDED |
| PACKET-003 | LANDED |
| PACKET-004 | LANDED |
| PACKET-005 | ACTIVE — execution boundary |
| PACKET-006 | QUEUED — transactional lifecycle |
| PACKET-007 | QUEUED — truth harness |

## 4. What must not be assumed

- Permissions are still **descriptive**. The production path proves load, not enforcement.
- `_load_plugin_module` still `exec_module`s in the host interpreter.
- Marketplace `extractall` is still unsafe. Network path stays disabled.
- Hot reload is still in-place, not blue/green.
- FastAPI still mounts plugin routers; host-owned dispatch is PACKET-006.
- `validate_system.py` 19/19 is component + one production path, not adversarial coverage.
