# Project Context

> High-density traversal index for the repository's persistent memory.
>
> This file is **not** a single mutable "current state" snapshot and it is not a replacement for
> `MEMORY.md`. It remains chronological and continuously written, but entries are intentionally
> shorter than their memory counterparts.
>
> Its job is to let an agent rapidly answer:
> 1. What strata of project history/state are relevant?
> 2. What exact keys should I use to traverse `MEMORY.md`?
> 3. What files/symbols/artifacts should I open next?
> 4. What truth is current enough to act on without rereading the whole repo?
>
> Think of `CONTEXT.md` as the codebase's index/routing layer and `MEMORY.md` as the deep store.
>
> **Charter boundary:** `STATE.md` owns single-screen current runtime truth. This file owns the
> dated chronological index. They are deliberately non-overlapping so they cannot become rival
> current-state surfaces.

## Context Operating Contract

- **Keep dated sections.** Do not collapse the file into one latest-state block.
- **Append after substantial turns.** Context evolves with the codebase.
- **Compress, do not amputate.** Preserve the nouns, symbols, filenames, status, and boundaries needed for retrieval.
- **Mirror MEMORY keys.** Use the same date/title vocabulary and stable search terms whenever possible.
- **Bias toward navigation.** A context entry should quickly route the agent toward the right memory entry and live repo surfaces.
- **Carry current truth explicitly.** If an older entry is superseded, add a newer dated entry saying so.
- **Keep details short here.** Deep rationale, logs, provenance, test output, alternatives, and forensic detail belong in `MEMORY.md`.
- **Preserve high-value negative state.** Active hazards, failed lanes, forbidden assumptions, and unresolved gaps belong here when they affect routing.
- **Never treat this as disposable handoff prose.** It is persistent codebase context.

## Traversal Model

Typical codebase reasoning loop:

`AGENTS.md`
→ scan newest/relevant `CONTEXT.md` entries
→ extract date/title/keys
→ jump into matching `MEMORY.md` strata
→ open named code/docs/artifacts
→ inspect/execute/validate live state
→ write `NOTEPAD.md` during work
→ persist new findings back into `MEMORY.md`
→ append/update compact routing entry here

Recommended lookup order:

1. Exact filename / symbol / artifact key
2. Subsystem / capability key
3. Date + title
4. Related canon/state doc
5. Live code verification

---

## 2026-09-05 — CONTROL PLANE INSTALLED; LINEAGE SCHISM RECORDED

**Keys:** `control-plane` · `lineage-schism` · `plugin_base` · `plugin_manager` · `host-boundary` · `AUTHORITY_MAP.md` · `PACKET-001`

- **State:** The repository was extracted from the private `somnus-os` donor codebase at commit
  `5278e3c` (2026-09-05) and had no control plane describing itself. This session installed one.
  **No source `.py` file was modified.** The defining architectural fact — two rival plugin
  lineages in one flat directory — is now recorded rather than latent.
- **Authority:** `AUTHORITY_MAP.md` for surface classification; `SPEC.md` for the plugin
  contract; `HOST_BOUNDARY.md` for the embedding contract; `AGENTS.md` for routing.
- **Changed:** `AGENTS.md` repaired into a router and de-duplicated from `CLAUDE.md` (they were
  byte-identical at 27,955 bytes and pointed at `holomodal-work` paths). `MEMORY.md`,
  `CONTEXT.md` filled from templates. `NOTEPAD.md` foreign OSINT content deleted and reset.
  `TODO.md` deleted — its "PRODUCTION-READY / 95% Complete" claims are disproven. New:
  `SPEC.md`, `HOST_BOUNDARY.md`, `OPSEC.md`, `STATE.md`, `TASK.md`, `AUTHORITY_MAP.md`,
  `README.md`, `workflows.md`, `pyproject.toml`, `gate.sh`, `docs/`, `packets/`, `.claude/`.
- **Boundary:** Installing the control plane proves nothing about whether the code runs. It
  records what was read from source. Every runtime claim in these documents is marked
  **PREDICTED** until `PACKET-001` observes it.
- **Evidence:** `git diff --stat -- '*.py'` — empty, as required. `accelerate-probe.mjs`
  inventory. Direct source reads across all 7 modules.
- **Next read:** `MEMORY.md` → `2026-09-05 — LINEAGE RULING: plugin_base.py IS CANONICAL`
- **Then inspect:** `AUTHORITY_MAP.md` §4 · `SPEC.md` · `packets/PACKET-001-dependency-and-import-truth.md`
- **Open:** Nothing in this repository imports today. `PACKET-001` is the unblocking packet.

## 2026-09-05 — LINEAGE RULING RECORDED

**Keys:** `lineage-schism` · `consumer-count` · `PluginManifest` · `PluginBase` · `PACKET-002`

- **State:** `plugin_base.py` is canonical. `plugin_manager.py` is superseded but retains the
  only working loader and FastAPI mount until `PACKET-002` re-bases them.
- **Authority:** operator ruling 2026-09-05, recorded in `MEMORY.md`; contract in `SPEC.md`.
- **Changed:** the fork is adjudicated. It is no longer an open question.
- **Boundary:** the ruling is recorded, **not executed**. All seven name collisions still exist
  in source. Do not assume convergence has happened.
- **Evidence:** inbound consumer count — `plugin_base.py` has 4 (`discovery.py:24`,
  `orchestration.py:20`, `security.py:34`, `marketplace.py:27`); `plugin_manager.py` has 0.
- **Next read:** `MEMORY.md` → `2026-09-05 — LINEAGE RULING: plugin_base.py IS CANONICAL`
- **Then inspect:** `plugin_base.py:79` · `plugin_manager.py:88` · `plugin_manager.py:701`
- **Open:** `PACKET-002` blocked on `PACKET-001`.

## 2026-09-05 — HOST BOUNDARY DECLARED

**Keys:** `host-boundary` · `core.memory_core` · `schemas.session` · `core.security_layer`

- **State:** Three donor modules and six symbols are supplied by the embedding system, not by
  this repository. This is a contract, not a defect.
- **Authority:** `HOST_BOUNDARY.md`.
- **Changed:** the boundary is written down for the first time.
- **Boundary:** an agent that vendors stubs or deletes these imports to make something import
  has destroyed the cross-ecosystem contract. Do not.
- **Evidence:** `plugin_base.py:22-23`, `plugin_manager.py:45-47`, `hot_reload.py:34`.
- **Next read:** `MEMORY.md` → `2026-09-05 — EXTRACTION PROVENANCE`
- **Then inspect:** `HOST_BOUNDARY.md` · `packets/PACKET-003-host-boundary-realization.md`
- **Open:** none.

---

## Current Canon / Authority Index

- `AGENTS.md` — cognitive bootstrap and execution router; doctrine
- `CLAUDE.md` — Claude Code runtime specialization of `AGENTS.md`
- `SPEC.md` — the adjudicated plugin contract
- `HOST_BOUNDARY.md` — what the embedding system must supply
- `OPSEC.md` — trust boundary and security posture
- `AUTHORITY_MAP.md` — surface classification and contradictions register
- `STATE.md` — single-screen current runtime truth
- `TASK.md` — packet board
- `MEMORY.md` — deep persistent codebase memory
- `CONTEXT.md` — chronological memory index / traversal layer
- `NOTEPAD.md` — append-only history; never authority
- `filetree.md` — generated topology; never routing
- `docs/DEFECT_INDEX.md` — verified defect register
- `gate.sh` — validation entrypoint

### Authority precedence

`OPERATOR DIRECTIVE` → `LIVE SOURCE` → `NORMATIVE DOCS` → `CURRENT STATE` → `GENERATED MAPS` → `HISTORY`

---

## Active Runtime / Architecture Keys

| Key | Current meaning | Authority / next surface |
|---|---|---|
| `canonical lineage` | `plugin_base.py` — 4 inbound consumers, pydantic manifest, 8-state lifecycle | `SPEC.md` · `plugin_base.py:79` |
| `superseded lineage` | `plugin_manager.py` — 0 consumers, but holds the only loader | `plugin_manager.py:668` |
| `loader convention` | Module-level class named exactly `Plugin`; `router` attr in `api/__init__.py` | `plugin_manager.py:700-706`, `:763-809` |
| `host boundary` | 3 donor modules, 6 symbols, supplied by the embedding system | `HOST_BOUNDARY.md` |
| `extension points` | `agent_actions`/`workflow_nodes`/`memory_extensions`/`ui_components` are declared but read by no loader | `plugin_base.py:107-111` |
| `validation posture` | `NOT RUN` — no dependencies installed, no test suite exists | `gate.sh` · `STATE.md` |
| `active packet` | `PACKET-001` — dependency and import truth | `TASK.md` |

---

## Active Hazards / Drift Keys

- `LOADER-GATE` — `plugin_manager.py:701` gates on its **local** `PluginBase`; a plugin written
  against canonical `plugin_base.PluginBase` is rejected — memory: `2026-09-05 — LINEAGE RULING`
- `MISSING-PERMISSION-SYMBOL` — `security.py:34` imports `PluginPermission` from `plugin_base`,
  which does not define it. **PREDICTED ImportError, NOT YET OBSERVED** — inspect: `security.py:34`
- `ENV-NO-DEPS` — no `.venv`, zero required dependencies installed, Python 3.12.3 host. Nothing
  imports today — inspect: `packets/PACKET-001-dependency-and-import-truth.md`
- `EMPTY-REFERENCE-PLUGIN` — `installed/example_plugin/` is 14 files at 0 bytes. Not an example
  — memory: `2026-09-05 — NEGATIVE KNOWLEDGE`
- `INHERITED-DOC-DRIFT` — extraction carried docs forward while code context changed. Verify
  inherited claims against source — memory: `2026-09-05 — NEGATIVE KNOWLEDGE`
- `PHANTOM-REGISTRY` — `marketplace.py` targets two hosts that do not exist — `docs/DEFECT_INDEX.md` D-016
- `FAKE-SIGNATURE` — `marketplace.py:346` is a checksum presented as signature verification —
  `OPSEC.md` · `docs/DEFECT_INDEX.md` D-004

---

## Open Threads / Resume Keys

- `PACKET-001` — dependency and import truth. Unblocks everything — next: `packets/PACKET-001-dependency-and-import-truth.md`
- `PACKET-002` — lineage convergence. Blocked on 001 — memory: `2026-09-05 — LINEAGE RULING`
- `PACKET-003` — host boundary realization. Blocked on 001 — next: `HOST_BOUNDARY.md`
- `PACKET-004` — populate the reference plugin. Blocked on 002 — next: `SPEC.md`
- `PluginSecurityManager overlap` — `plugin_manager.py:334` overlaps `security.py:609` in role,
  not implementation. PACKET-002 must decide — memory: `2026-09-05 — LINEAGE RULING`, Open threads

---

## Recent Verification Index

- `2026-09-05` — `git diff --stat -- '*.py'` — `PASS` (empty; no source modified this session)
- `2026-09-05` — `accelerate-probe.mjs --format markdown` — `OBSERVED` — pre-install inventory
  reported `None observed` for gate entrypoints, authority surfaces, and evidence roots
- `2026-09-05` — `python3 -c "import plugin_base"` — `FAIL` — `ModuleNotFoundError: No module
  named 'pydantic'`. Blocked before reaching the `PluginPermission` break; the deeper failure
  remains **unobserved**
- `2026-09-05` — full test suite — `NOT RUN` — no test suite exists in this repository

## 2026-09-06 — PACKET-001/002/003 LANDED; SOTA++ INTEGRATION

**Keys:** `PACKET-001` · `PACKET-002` · `PACKET-003` · `host_protocols` · `PluginPermission` · `PluginType` · `CapabilitySet` · `EWMA` · `Merkle` · `validate_system`

- **State:** The codebase imports. All 8 modules (7 root + host_protocols) pass import checks.
  The host boundary is realized via Protocol declaration. The lineage convergence is partial —
  `PluginPermission` and `PluginType` are absorbed, but `plugin_manager.py` still defines its
  own `PluginManifest`, `PluginBase`, `PluginDiscovery`, `PluginFileWatcher`.
- **Changed:** `plugin_base.py` rewritten with SOTA++ features (capability lattice, EWMA metrics,
  Merkle checkpoints, validated state machine, typed events, real resource monitoring).
  `host_protocols.py` created. `security.py`, `discovery.py`, `orchestration.py`, `hot_reload.py`,
  `marketplace.py`, `plugin_manager.py` updated for new imports. Defects D-001, D-002, D-011 fixed.
  Pickle vulnerability removed. `validate_system.py` created with 15 checks, all PASS.
- **Evidence:** `gate.sh` PASS (11 runnable), `validate_system.py` 15/15 PASS.
- **Next read:** `STATE.md` for current runtime truth, `NOTEPAD.md` latest entry for the full
  handoff block with proof facts.
- **Open:** PACKET-002 completion (delete superseded types from plugin_manager), PACKET-004
  (reference plugin).

---

## 2026-09-18 — AUTHORITY CONVERGENCE; ONE HEARTBEAT

**Keys:** `PACKET-002` · `PACKET-004` · `PACKET-005` · `example_plugin` · `plugin_identity` · `production_load_path`

- **State:** The loader runs the canonical lineage. Gate duplicate-class PENDING items are gone.
  19/19 harness PASS is component checks plus one production path — not adversarial coverage.
- **Next read:** `STATE.md`, `packets/PACKET-005-execution-boundary.md`
- **Open:** capability façade, transactional install/reload, truth harness.

---

## 2026-09-18 — EXECUTION BOUNDARY LANDED

**Keys:** `PACKET-005` · `HostCapabilityFacade` · `ExecutionDomain` · `IsolatedPluginHandle` · `ExportedAction` · `NOT TERMINABLE`

- **State:** Permissions are object-capability policy. Isolated plugins import
  in a worker. 22/22 harness PASS is still not adversarial coverage.
- **Next read:** `STATE.md`, `packets/PACKET-006-transactional-lifecycle.md`
- **Open:** staged install, blue/green generations, host-owned route, truth harness.

---

## Context Maintenance Notes

- A context entry can be only a handful of bullets if those bullets preserve the right traversal keys.
- Prefer exact repo nouns over generic summaries: filenames, classes, functions, configs, tests, artifacts, run IDs, model/checkpoint names.
- Do not erase old context solely because it is old; historical routing is useful when debugging regressions or provenance.
- When context gets large, improve headings, keys, and jump tables. Do not replace the chronological substrate with a tiny status dashboard.
- If an entry needs substantial explanation, put that explanation in `MEMORY.md` and point to it from here.
