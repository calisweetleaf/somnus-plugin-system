# PACKET-001 — Dependency and Import Truth

**Owner:** next executing agent
**Status:** READY
**Depends on:** nothing
**Size:** one session
**Priority:** blocking — every other packet is gated behind this one

## Mission

Establish the dependency environment for this repository and convert every runtime claim in the
control plane from PREDICTED to OBSERVED. Today no document in this repository can cite a single
observed traceback, because nothing has ever been imported successfully. Create a `.venv`,
install the declared dependency contract from `pyproject.toml`, then run the import chain module
by module and record exactly what happens. Where an import fails, capture the verbatim traceback.
Where it succeeds, say so. The deliverable is truth about the runtime, not a fix — do not repair
anything you discover in this packet. Repairs belong to PACKET-002 and PACKET-003.

Specifically resolve the standing question: `security.py:34` imports `PluginPermission` from
`plugin_base`, which grep proves does not define it. The resulting `ImportError` has never been
observed because the interpreter dies earlier on the missing `pydantic`. Confirm or refute it.

## Required Reads

- `STATE.md` — current runtime posture, the four blockers
- `pyproject.toml` — the dependency contract to install
- `HOST_BOUNDARY.md` — the three donor modules that will NOT resolve, and must not be made to
- `AUTHORITY_MAP.md` section 4, CONTRADICTION-01 — the exact claim under test
- `security.py` lines 30 to 40 — the import under test
- `plugin_base.py` lines 17 to 30 — what that module actually exports
- `AGENTS.md` section 9 — the hard bans, especially bans 1 and 7

## Invariant

- No `.py` file in this repository is modified by this packet. This is an observation packet.
- The three host-boundary imports remain unresolved and unstubbed. `core.memory_core`,
  `schemas.session`, and `core.security_layer` are expected to fail. That failure is correct
  behavior and must be recorded as such, not repaired.
- No dependency is version-pinned unless a genuine incompatibility is observed and recorded with
  its traceback.
- An import that fails is recorded as failing. Do not add `try/except ImportError` anywhere to
  make output look cleaner.

## Surfaces

Implementation and environment:
- `.venv/` — created, not committed. Confirm `.gitignore` already excludes it.
- `pyproject.toml` — corrected only if an install failure proves a declared dependency name or
  constraint is wrong.

Evidence:
- `docs/IMPORT_TRUTH.md` — new. The verbatim per-module import results and tracebacks.

Continuity:
- `STATE.md` — section 1 rewritten with observed results
- `CONTEXT.md` — new dated entry and Recent Verification Index rows
- `MEMORY.md` — a dated entry for anything durable, especially a pydantic major-version finding
- `NOTEPAD.md` — appended handoff block
- `TASK.md` — this packet marked landed, next packet dispatched
- `AUTHORITY_MAP.md` — CONTRADICTION-01 status upgraded from PREDICTED to OBSERVED or refuted
- `OPSEC.md` — SEC-01 status upgraded likewise

## Hard Bans

- Do not fix the `PluginPermission` import. Observing it is the mission. Fixing it is PACKET-002.
- Do not create `core/`, `schemas/`, or any stub package to satisfy a donor import.
- Do not add a `conftest.py`, a `tests/` directory, or a pytest suite. Validation here is
  experimentation, per `AGENTS.md` section 7.
- Do not modify any of the 7 root modules.
- Do not delete or "clean up" `SCOPE.md`, `SOTA_RUN.md`, `requirements.txt`, `tools/`, `test/`,
  or `snapshots/`. Their disposition is an open operator decision recorded in `TASK.md`.
- Do not commit `.venv/`.
- Do not report a module as importable without pasting the command that proved it.

## Validation

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .   # pyproject sets packages=[] so flat-layout auto-discovery
                               # does not error on docs/, packets/, installed/, tools/, test/
for m in plugin_base plugin_manager security discovery orchestration hot_reload marketplace; do
  echo "=== import $m ==="
  ./.venv/bin/python -c "import $m" 2>&1 | tail -20
done
bash gate.sh
```

Expected observations, to be confirmed or refuted:

- `plugin_base` — fails on `core.memory_core` (host boundary, correct behavior)
- `security` — fails on `ImportError: cannot import name 'PluginPermission' from 'plugin_base'`,
  **or** fails earlier on the host boundary. Record which comes first.
- `marketplace` — fails downstream of `security`
- `orchestration` — has zero third-party imports of its own; fails only via `plugin_base`
- Every failure must be a real traceback pasted into `docs/IMPORT_TRUTH.md`

A pass for this packet is **an accurate record**, not a successful import. If every module fails,
that is a complete and successful packet.

Additionally verify the pydantic major version. `plugin_base.py:19` imports `validator` and
`:136` calls `.dict()` — both are deprecated in pydantic v2. If v2 is installed, record whether
they warn or raise. This materially affects PACKET-002.

## Exit

Record in `NOTEPAD.md` and `docs/IMPORT_TRUTH.md`:

- Commit hash the work started from
- Exact `pip install` output tail, including resolved versions of all 9 dependencies
- Per-module import result, verbatim, all 7 modules
- Whether CONTRADICTION-01 is CONFIRMED or REFUTED, with the traceback
- The installed pydantic major version and whether `validator` / `.dict()` warn or raise
- Files changed
- `bash gate.sh` output verbatim

## Handoff

Execute PACKET-002 next. Before starting it, re-read `SPEC.md` section 7 — the loader hazard —
and confirm against the observed import results whether the convergence order stated there is
still correct. If PACKET-001 refuted CONTRADICTION-01, **stop and reconcile before touching source.** Follow
`AGENTS.md` section 2a step by step: preserve the historical record, classify each claim,
gather boundary-relevant evidence, and write a bounded reconciliation packet using the same
eight fields before any implementation packet resumes. The surfaces that assert CONTRADICTION-01
and would all need correcting are `AUTHORITY_MAP.md` section 4, `OPSEC.md` SEC-01, `SPEC.md`
section 1, `STATE.md` section 1, `CONTEXT.md` Active Hazards, and `MEMORY.md`. Do not correct
them piecemeal mid-packet.

Hazards: none observed yet. This packet exists to find them.
