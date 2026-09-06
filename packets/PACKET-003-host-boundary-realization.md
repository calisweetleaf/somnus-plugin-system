# PACKET-003 — Host Boundary Realization

**Owner:** next executing agent
**Status:** QUEUED
**Depends on:** PACKET-001
**Size:** one session
**Priority:** medium — required before this substrate can be embedded in any host

## Mission

Choose and implement the strategy by which an embedding system satisfies this repository's three
donor imports, and make the boundary mechanically checkable rather than merely documented. Today
`core.memory_core`, `schemas.session`, and `core.security_layer` are imported at module scope in
three files and resolve nowhere. `HOST_BOUNDARY.md` records the contract in prose; this packet
turns it into something a host can be verified against. The goal is that a host integrator can
determine, before running anything, whether their system satisfies this substrate.

## Required Reads

- `HOST_BOUNDARY.md` — the entire document. Section 4 lists the three candidate strategies.
- `docs/IMPORT_TRUTH.md` — produced by PACKET-001. Shows which host-boundary failures actually
  occur and in what order.
- `MEMORY.md` entry `2026-09-05 — EXTRACTION PROVENANCE: THE DONOR BOUNDARY IS A CONTRACT, NOT A DEFECT`
- `plugin_base.py` lines 20 to 25, and 270 to 285, and 440 to 450 — every host-type consumption site
- `plugin_manager.py` lines 44 to 48, and 245 to 285
- `hot_reload.py` lines 32 to 36
- `AGENTS.md` section 9, hard ban 1

## Invariant

- The boundary stays a boundary. This repository never gains a working implementation of
  `MemoryManager`, `SessionID`, `UserID`, or `SecurityEnforcer`.
- Whatever strategy is chosen must fail loudly when the host is absent. A missing host is an
  error condition, not a degraded mode.
- The six import sites enumerated in `HOST_BOUNDARY.md` section 3 remain the complete boundary.
  Any expansion requires an operator decision, not an implementer's judgment.
- The plugin authoring contract in `SPEC.md` is unaffected. Plugin authors do not see this seam.

## Surfaces

Implementation, depending on the chosen strategy:
- `plugin_base.py`, `plugin_manager.py`, `hot_reload.py` — the three files carrying donor imports
- A protocol module, if strategy 1 is chosen. Flat at root, consistent with the layout ruling.

Evidence:
- `gate.sh` — the boundary check is already present; extend it if the strategy adds a checkable
  property
- `docs/ARCHITECTURE.md` — the trust-zone diagram updated to show the realized mechanism

Continuity:
- `HOST_BOUNDARY.md` — section 4 rewritten from candidate options to the chosen mechanism, with
  a host integrator's checklist
- `MEMORY.md` — a dated entry recording the choice and the rejected alternatives
- `CONTEXT.md`, `STATE.md`, `NOTEPAD.md`, `TASK.md`

## Hard Bans

- Do not write a stub module that returns fake data. Per operator doctrine this repository has no
  stubs, no subs, no fallbacks.
- Do not add `try/except ImportError` around a donor import.
- Do not add a mock `MemoryManager` even for development convenience.
- Do not vendor the donor's implementations into this repository.
- Do not silently expand the boundary. Six import sites is the contract.
- Do not implement a host `SecurityEnforcer` before PACKET-002 has ruled on whether
  `core.security_layer` survives the convergence at all.
- Do not make the host optional. This substrate does not run standalone by design.

## Validation

```bash
grep -rn '^from \(core\|schemas\|backend\)\.' *.py
bash gate.sh
./.venv/bin/python -c "import plugin_base" 2>&1 | tail -20
```

Expected:

- The boundary grep returns exactly the set recorded in `HOST_BOUNDARY.md` section 3 — six lines
  if the namespace-package strategy is chosen, or zero if injection removed the module-scope
  imports entirely. Either is acceptable; an unexplained count is not.
- `gate.sh` boundary check passes.
- If strategy 1 or 3 was chosen, `import plugin_base` still fails without a host present, and the
  failure message names the missing host module clearly rather than producing an opaque error.
- If strategy 2 was chosen, `import plugin_base` succeeds and the host types are supplied at
  `initialize_plugin_system(...)` instead.

Record which outcome occurred. Do not describe an unrun check as passing.

## Exit

Record in `NOTEPAD.md` and `HOST_BOUNDARY.md`:

- The chosen strategy and, explicitly, why the other two were rejected
- Files changed, commit hash
- The exact boundary grep output after the change
- A host integrator's checklist: what a host must provide, in what form, verified how
- Whether `core.security_layer` survived, per the PACKET-002 ruling
- `bash gate.sh` output verbatim

## Handoff

Execute PACKET-004 next to build the reference plugin, which is the first artifact that exercises
the contract end to end.

Hazards: strategy 2 (host-supplied injection) is the largest change — it removes module-scope
imports across three files and alters the initialization signature. If chosen, confirm no
consumer relies on importing a host type directly from `plugin_base` before proceeding.
