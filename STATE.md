# STATE — somnus-plugin-system

> **Charter:** single-screen current runtime truth. What is true *right now*.
>
> **Refresh on every state change.** A stale `STATE.md` is worse than none.

**Last refreshed:** 2026-09-22
**Working tree:** defect closure, reference plugin, and continuity updates on `cursor/defect-closure-adad`.

---

## 1. Does it run?

**Yes.** All 8 modules import (`host_protocols.py` plus the 7 root modules). `somnus_reference` loads through `PluginManager` and answers three mounted routes.

| Fact | Status |
|---|---|
| Dependencies installed | **OBSERVED** — `.venv` present |
| All modules import | **OBSERVED** — `gate.sh` section 6 |
| Host boundary | **OBSERVED** — `host_protocols.py` protocols. Donor modules are not vendored. |
| Lineage convergence | **OBSERVED** — `PluginManifest`, `PluginBase`, `PluginDiscovery`, `PluginFileWatcher` each defined once |
| Defect register D-001..D-022 | **CLOSED** — `experiments/prove_defect_closure.py` 38/38 |
| Reference plugin | **OBSERVED** — `experiments/prove_reference_plugin.py` 8/8 |
| Marketplace network | **OFF** — empty URL defaults, `network_enabled` false |
| Gate | **PASS** on runnable checks. Packet validation `NOT RUN` (validator absent). Pytest suite `NOT RUN` by design. Zero-byte `installed/` check clears once this tree is what the gate scans. |

## 2. What is the gate posture?

`bash gate.sh` passes the runnable checks: structural integrity, host-boundary injection, single lineage class definitions, and the import chain.

`NOT RUN`:

- Packet validation — `validate-packet.mjs` is not in this environment
- Test suite — no pytest suite, by design (`AGENTS.md` §7)

Proofs that the gate does not run:

- `experiments/prove_defect_closure.py` — 38/38
- `experiments/prove_reference_plugin.py` — 8/8

## 3. What is the active packet?

**None.** `PACKET-001`, `PACKET-002`, `PACKET-003`, and `PACKET-004` are landed.

## 4. What holds after this pass?

| Behavior | Where |
|---|---|
| Priority drain REALTIME first | `orchestration.py` |
| Manifest CPU and memory admission | `ExecutionResourceMonitor.check_manifest_budget` |
| Machine-share CPU, live RSS | `plugin_base.machine_cpu_percent`, `current_resident_bytes` |
| Reactive events and cycle-aware parallel graphs | `orchestration.WorkflowEngine` |
| Callback bound before enqueue | `PluginOrchestrator.execute_plugin_method` |
| Zip-slip refusal before write | `security.safe_extract_zip` |
| RSA-PSS required, checksum is not a signature | `marketplace.RegistryClient.verify_download` |
| No placeholder trust root, no default registry host | `marketplace.create_marketplace` |
| Local trust score, server score stored aside | `TrustSystem.calculate_trust_score` |
| Shared registry cache | `PluginMarketplace.registry_cache` |
| Watcher debounce cancelled on stop | `discovery.PluginDiscovery.stop_monitoring` |
| Per-route plugin injection | `plugin_manager._bind_plugin_endpoint` |
| Reference plugin | `installed/example_plugin/` |

## 5. What must not be assumed?

- **Do not enable the marketplace network** by flipping a default. An operator supplies URLs and keys.
- **Do not vendor `MemoryManager` or `SecurityEnforcer`.** The protocols are the seam.
- **Do not treat a sha256 checksum as a signature.**
- **Do not reintroduce the deleted rival classes** in `plugin_manager.py`.
- **`trusted: true` does not skip signature verification.**
