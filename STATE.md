# STATE — somnus-plugin-system

> **Charter:** single-screen current runtime truth. What is true *right now*.
>
> **Refresh on every state change.** A stale `STATE.md` is worse than none.

**Last refreshed:** 2026-09-18
**Working tree:** PACKET-006 landing on `cursor/plugin-runtime-heartbeat-863f`

---

## 1. Does it run?

**Yes.** Root modules plus `host_capabilities` and `plugin_worker` import. The
production loader loads a canonical plugin through a capability façade.

| Fact | Status |
|---|---|
| Dependencies installed | **OBSERVED** — `.venv` present |
| All modules import | **OBSERVED** — includes `host_protocols`, `host_capabilities`, `plugin_worker` |
| Host boundary | **OBSERVED** — Protocol seam. Zero donor imports. |
| Lineage convergence | **OBSERVED** — canonical types defined once. |
| Reference plugin | **OBSERVED** — `example_plugin_1.0.0` loads HOST_INTEGRATED with a façade |
| Production path | **OBSERVED** — discover → security → façade → load → ping → checkpoint → restore → unload |
| Capability denial | **OBSERVED** — verified plugin denied WRITE_MEMORY |
| Isolated timeout | **OBSERVED** — hang killed worker PID; crash stayed in worker |
| Validation harness | **22/22 PASS** — component checks + production path + three domain checks. This is **not** the adversarial suite (PACKET-007). |
| Gate | **PASS** on runnable checks. Packet validator NOT RUN. No pytest suite by design. |

## 2. What is the gate posture?

`bash gate.sh` → PASS on 19 runnable checks. 0 PENDING. 2 NOT RUN.

## 3. What is the active packet?

| Packet | Status |
|---|---|
| PACKET-001 | LANDED |
| PACKET-002 | LANDED |
| PACKET-003 | LANDED |
| PACKET-004 | LANDED |
| PACKET-005 | LANDED — execution boundary |
| PACKET-006 | LANDED — transactional lifecycle |
| PACKET-007 | ACTIVE — truth harness |

## 4. What must not be assumed

- Marketplace network path stays disabled.
- `validate_system.py` 25/25 is component + production + domain + lifecycle proofs, not the full adversarial suite until PACKET-007 labels it.
- In-process timeouts record `NOT TERMINABLE`. They do not kill the function.
