# TASK — Packet Board

> **Current state surface.** What is executable now, what is queued, what is blocked.
> Detail lives in `packets/`. Durable rationale lives in `MEMORY.md`.

**Board refreshed:** 2026-09-18

---

## Active

### `PACKET-005` — Execution Boundary · READY · blocked on nothing

Permissions become object-capability policy. Graduated execution domains. Exported
actions. Isolated worker for untrusted plugins.

→ `packets/PACKET-005-execution-boundary.md`

---

## Queued

| Packet | Mission | Status | Blocked on |
|---|---|---|---|
| `PACKET-006` | Transactional lifecycle — staged install, generation reload, host route | QUEUED | 005 |
| `PACKET-007` | Truth harness — adversarial E2E + mechanical STATE | QUEUED | 006 |

---

## Landed

| Packet | Status |
|---|---|
| PACKET-001 dependency and import truth | LANDED |
| PACKET-002 lineage convergence | LANDED 2026-09-18 |
| PACKET-003 host boundary realization | LANDED |
| PACKET-004 reference plugin | LANDED 2026-09-18 |

---

## Not yet packetized beyond 007

Marketplace network enablement remains forbidden until SEC-02 through SEC-08 are closed
inside PACKET-006's local-archive path and a later network packet.
