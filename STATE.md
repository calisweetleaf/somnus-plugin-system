# STATE — somnus-plugin-system

> **Charter:** single-screen current runtime truth. What is true *right now*.
>
> **Refresh on every state change.** A stale `STATE.md` is worse than none.

**Last refreshed:** 2026-09-06
**Working tree:** uncommitted changes present — control plane documents being updated.

---

## 1. Does it run?

**Yes.** All 8 modules import successfully (7 root modules + `host_protocols.py`).

| Fact | Status |
|---|---|
| Dependencies installed | **OBSERVED** — `.venv` present, all 9 deps import |
| All modules import | **OBSERVED** — `gate.sh` section 6 reports PASS for all 7 |
| Host boundary resolved | **OBSERVED** — Protocol declaration strategy (HOST_BOUNDARY.md §4 option 1) via `host_protocols.py` |
| Missing PluginPermission symbol | **RESOLVED** — absorbed from `plugin_manager.py` into `plugin_base.py` during lineage convergence |
| Lineage convergence | **PARTIAL** — `PluginPermission` and `PluginType` absorbed. Duplicate class names still exist in `plugin_manager.py` (its own `PluginManifest`, `PluginBase`, `PluginDiscovery`, `PluginFileWatcher`). Gate reports 4 PENDING. |
| Validation harness | **PASS** — 15/15 checks pass (`validate_system.py`) |
| Gate | **PASS** on runnable checks. 6 PENDING (known work), 2 NOT RUN (missing prereqs). |

## 2. What is the gate posture?

`bash gate.sh` → **PASS** on 11 runnable checks. 6 PENDING. 2 NOT RUN.

The PENDING items are:
- 4× duplicate class definitions (`PluginManifest`, `PluginBase`, `PluginDiscovery`, `PluginFileWatcher`) in `plugin_manager.py` — deletable once `plugin_manager.py`'s loader is re-based onto canonical lineage
- 8 zero-byte files under `installed/example_plugin/` — PACKET-004 work
- 1 untracked `.py` file (`validate_system.py`) — operator decision

The NOT RUN items are:
- Packet validation — `validate-packet.mjs` not present in cloud environment
- Test suite — by design per AGENTS.md §7

## 3. What is the active packet?

**PACKET-001, PACKET-002, and PACKET-003 are landed.**

| Packet | Status | Notes |
|---|---|---|
| `PACKET-001` dependency and import truth | **LANDED** | .venv created, all modules import |
| `PACKET-002` lineage convergence | **PARTIAL** | PluginPermission/PluginType absorbed, manifest narrowed. Superseded types still exist in plugin_manager.py |
| `PACKET-003` host boundary realization | **LANDED** | Protocol declaration strategy via host_protocols.py |
| `PACKET-004` reference plugin | BLOCKED | on full PACKET-002 completion |

## 4. What SOTA++ improvements have landed?

| Feature | Module | Description |
|---|---|---|
| Protocol-based host boundary | `host_protocols.py` | `typing.Protocol` contracts for MemoryManager, SecurityEnforcer |
| Capability lattice algebra | `plugin_base.py` | `CapabilitySet` with meet/join/complement/subsumes/gap |
| Content-addressed checkpoints | `plugin_base.py` | Merkle-hashed state snapshots with deduplication |
| EWMA metrics | `plugin_base.py` | Exponentially-weighted moving average for execution times |
| Validated state machine | `plugin_base.py` | Directed graph of legal transitions, `InvalidStateTransition` |
| Typed event bus | `plugin_base.py` | `PluginEventType` enum, frozen `PluginEvent` dataclass |
| Real resource monitoring | `plugin_base.py` | stdlib `resource` module for actual RSS measurement |
| Semver validation | `plugin_base.py` | `field_validator` on manifest version field |
| D-001 fix | `orchestration.py` | Priority queue order corrected (REALTIME first) |
| D-002 fix | `orchestration.py` | ThreadPoolExecutor.shutdown TypeError resolved |
| D-011 fix | `orchestration.py` | CPU metrics estimated from execution time (was hardcoded 0.0) |
| Pickle removal | `hot_reload.py` | JSON-only deserialization, pickle payloads rejected |

## 5. What must not be assumed?

- **Do not assume the full lineage convergence is complete.** `plugin_manager.py` still defines its own `PluginManifest`, `PluginBase`, `PluginDiscovery`, and `PluginFileWatcher`. These are the gate's 4 PENDING items. Deleting them requires re-basing the loader onto the canonical lineage.
- **Do not author a plugin against `plugin_manager.PluginBase`.** It is superseded. Use `plugin_base.PluginBase`.
- **Do not treat `installed/example_plugin/` as an example.** It is 14 files at 0 bytes.
- **Do not enable the marketplace network path.** See `OPSEC.md`.
