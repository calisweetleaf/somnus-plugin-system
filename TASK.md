# TASK — Packet Board

> **Current state surface.** What is executable now, what is queued, what is blocked.
> Detail lives in `packets/`. Durable rationale lives in `MEMORY.md`.

**Extraction commit:** `5278e3c` · **Board refreshed:** 2026-09-22

---

## Active

None. The queued board through `PACKET-004` is landed. The next packet is whatever the operator names.

---

## Landed

| Packet | Status | Evidence |
|---|---|---|
| `PACKET-001` dependency and import truth | **LANDED** | Modules import under `.venv` |
| `PACKET-002` lineage convergence | **LANDED** | One definition each of the four collided classes. Loader accepts `plugin_base.PluginBase` |
| `PACKET-003` host boundary realization | **LANDED** | `host_protocols.py`. Donor imports are not stubbed |
| `PACKET-004` reference plugin | **LANDED** | `installed/example_plugin/` loads. `experiments/prove_reference_plugin.py` 8/8 |
| Defect register D-001..D-022 | **CLOSED** | `experiments/prove_defect_closure.py` 38/38. `docs/DEFECT_INDEX.md` closure ledger |
| SEC-01..SEC-10 | **CLOSED** | `OPSEC.md`. Marketplace network stays off |

### 2026-09-05 — Control plane installation

Installed the routing, state, normative, evidence, and harness surfaces. Recorded the lineage
schism, the host boundary, and 22 verified defects. That historical entry stands. The defects
it recorded are closed in source as of 2026-09-22.

---

## Not yet packetized

| Work | Why it waits |
|---|---|
| Operator decision to enable a marketplace network | Defaults stay off. Requires operator-supplied registry URLs and `SOMNUS_MARKETPLACE_TRUST_KEYS`. |
