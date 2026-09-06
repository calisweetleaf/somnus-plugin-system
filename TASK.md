# TASK — Packet Board

> **Current state surface.** What is executable now, what is queued, what is blocked.
> Detail lives in `packets/`. Durable rationale lives in `MEMORY.md`.
>
> Supersedes the former `TODO.md`, which was deleted 2026-09-05 — its "PRODUCTION-READY / 95%
> Complete / 2-4 hours remaining" claims are disproven. See `MEMORY.md` →
> `2026-09-05 — NEGATIVE KNOWLEDGE: DISPROVEN INHERITED CLAIMS`.

**Extraction commit:** `5278e3c` · **Control plane:** `b9586ea` → `ae5d1cf` · **Board refreshed:** 2026-09-05

---

## Active

### `PACKET-001` — Dependency and Import Truth · **READY** · blocked on nothing

Establish the dependency environment and convert every PREDICTED runtime claim in this control
plane into an OBSERVED one. This is the unblocking packet — every other packet is gated behind
it, because the control plane currently cannot cite a single observed traceback.

→ `packets/PACKET-001-dependency-and-import-truth.md`

---

## Queued

| Packet | Mission | Status | Blocked on |
|---|---|---|---|
| `PACKET-002` | Lineage convergence — make `plugin_base.py` canonical in source, not only in ruling | QUEUED | 001 |
| `PACKET-003` | Host boundary realization — choose and implement the strategy for the 3 donor modules | QUEUED | 001 |
| `PACKET-004` | Reference plugin — populate `installed/example_plugin/` against `SPEC.md` | QUEUED | 002 |

→ `packets/PACKET-002-lineage-convergence.md`
→ `packets/PACKET-003-host-boundary-realization.md`
→ `packets/PACKET-004-reference-plugin.md`

---

## Not yet packetized

Recorded so they are not lost. Each needs a packet written before execution.

| Work | Why it waits | Evidence |
|---|---|---|
| Marketplace hardening | Seven security findings must be resolved before any network path is enabled | `OPSEC.md` SEC-02…SEC-08 |
| Orchestration defect sweep | Inverted priority queue, guaranteed shutdown `TypeError`, inert reactive mode, serial graph execution, hardcoded zero metrics | `docs/DEFECT_INDEX.md` D-001, D-002, D-009–D-014 (D-003–D-008 are marketplace, not orchestration) |
| Resource limit enforcement | `memory_limit_mb` / `cpu_limit_percent` are validated and unenforceable | `OPSEC.md` SEC-09 |
| `PluginSecurityManager` overlap | `plugin_manager.py:334` overlaps `security.py:609` in role, not implementation. PACKET-002 must rule | `MEMORY.md` → lineage ruling, Open threads |
| ~~Scaffolding artifact disposition~~ | **RESOLVED 2026-09-05.** Operator ruled: preserve in history, then delete. Preserved at `b9586ea`, removed in the following commit. `tools/native/plugin/identifiers.py` had attempted to sever the `schemas.session` host boundary — a hard-ban-1 violation. | `AUTHORITY_MAP.md` §6 |

---

## Landed

### 2026-09-05 — Control plane installation

Installed the routing, state, normative, evidence, and harness surfaces. Recorded the lineage
schism, the host boundary, and 22 verified defects. **Zero `.py` files modified.**

- Repaired: `AGENTS.md` (generic constitution → router), `CLAUDE.md` (de-duplicated)
- Filled: `MEMORY.md`, `CONTEXT.md` (were placeholder templates)
- Reset: `NOTEPAD.md` (held 436 lines of foreign OSINT content)
- Deleted: `TODO.md`
- New: `SPEC.md`, `HOST_BOUNDARY.md`, `OPSEC.md`, `AUTHORITY_MAP.md`, `STATE.md`, `TASK.md`,
  `README.md`, `workflows.md`, `pyproject.toml`, `gate.sh`, `docs/`, `packets/`, `.claude/`
- Validation: no tracked `.py` module modified — **PASS**. Note: two untracked `.py` files were
  introduced by a subagent outside the plan; see the scaffolding row above.

→ `NOTEPAD.md` for the handoff block.
