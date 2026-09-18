# Memory Log

> Persistent codebase memory substrate.
>
> This file is expected to become **large**. Do not prune it merely to keep it readable.
> Append durable, source-backed project knowledge continuously as the codebase evolves.
>
> `CONTEXT.md` is the traversal/index layer for this file. A context entry should carry enough
> matching date/title/keys that an agent can locate the corresponding memory stratum without
> rereading the entire repository.
>
> This is not only a decisions log. Preserve architecture discoveries, implementation truth,
> experiments, failures, verification results, provenance, boundaries, changed assumptions,
> file relationships, runtime behavior, operator doctrine, and unresolved questions whenever
> they will matter to future work.

## Memory Operating Contract

- **Append, do not flatten history.** Later entries may supersede earlier entries; preserve both and mark the newer truth clearly.
- **Write after substantial work.** Memory is part of the codebase runtime, not an end-of-project archive.
- **Prefer source-backed truth.** Name files, symbols, commands, artifacts, commits, reports, tests, and observed behavior.
- **Record negative knowledge.** Failed approaches, disproven assumptions, unsafe shortcuts, and "do not repeat" findings are valuable memory.
- **Preserve uncertainty.** Distinguish verified facts, operator directives, current interpretations, hypotheses, and open questions.
- **Keep chronology searchable.** Each substantial entry begins with a date and a high-signal title.
- **Emit traversal keys.** Reuse stable nouns, filenames, symbols, subsystem names, artifact names, and doctrine terms that can also appear in `CONTEXT.md`.
- **Do not over-compress.** If a future agent would need the details to avoid rediscovery, keep the details here.
- **Do not use MEMORY as scratch space.** Ephemeral reasoning belongs in `NOTEPAD.md`; promote only durable outcomes here.
- **Do not silently rewrite old entries.** Prefer a new dated correction/supersession entry unless fixing a factual typo.

## Retrieval Model

Typical traversal:

`AGENTS.md` → `CONTEXT.md` → matching date/title/keys → `MEMORY.md` → named code/docs/artifacts → live verification

A useful entry therefore answers:

- What changed or was learned?
- Where in the repo does that truth live?
- What evidence established it?
- What interpretation or boundary should persist?
- What should a future agent search/read next?
- What was ruled out, superseded, or left unresolved?

---

## 2026-09-05 — EXTRACTION PROVENANCE: THE DONOR BOUNDARY IS A CONTRACT, NOT A DEFECT

**Keys:** `extraction` · `somnus-os` · `host-boundary` · `core.memory_core` · `schemas.session` · `core.security_layer` · `5278e3c`

**Status:** `OPERATOR-DIRECTIVE` + `VERIFIED`

### Durable findings

- This repository was carved out of the private `somnus-os` donor codebase and pushed as commit
  `5278e3c` on 2026-09-05. The operator's stated intent, recorded verbatim in that commit
  message: dedicate a solo workspace so the plugin system can become a cross-ecosystem
  agnostic codebase, deliberately over-engineered, explicitly not thin adapters or shims.
- **The unresolved donor imports are the host boundary, not bugs.** Operator ruling
  2026-09-05: this package is designed to be embedded inside larger Somnus systems. It will
  never be a standalone distribution. An agent that "fixes" these by vendoring stubs or
  deleting the imports has destroyed the cross-ecosystem contract.
- The correct response to a donor import is to **declare** it in `HOST_BOUNDARY.md`, not to
  resolve it.

### Code / architecture truth

- `core.memory_core` → `MemoryManager`, `MemoryType`, `MemoryImportance`, `MemoryScope`
  — imported at `plugin_base.py:22`, `plugin_manager.py:46`, `hot_reload.py:34`.
- `schemas.session` → `SessionID`, `UserID` — imported at `plugin_base.py:23`,
  `plugin_manager.py:45`.
- `core.security_layer` → `SecurityEnforcer` — imported at `plugin_manager.py:47`.
- No `core/`, `schemas/`, or `backend/` directory exists in this repository. There is no
  `backend.*` import anywhere.

### Interpretation / boundary

- **Proves:** the three donor modules are a stable, enumerable interface — three modules, six
  symbols, six import sites.
- **Does not prove:** that the donor's implementations are the only valid ones. A different
  host may supply conforming implementations.
- **Boundary:** `HOST_BOUNDARY.md` owns this contract. `plugin_base.py` consumes it.

### Retrieval anchors

- `HOST_BOUNDARY.md`
- `packets/PACKET-003-host-boundary-realization.md`
- Context index key: `2026-09-05 — CONTROL PLANE INSTALLED`

---

## 2026-09-05 — LINEAGE RULING: `plugin_base.py` IS CANONICAL

**Keys:** `lineage-schism` · `plugin_base` · `plugin_manager` · `PluginManifest` · `PluginBase` · `consumer-count` · `PACKET-002`

**Status:** `OPERATOR-DIRECTIVE` (ruling) + `VERIFIED` (evidence)

### Durable findings

- This repository contained **two rival, incompatible plugin lineages in one flat directory**.
  This is the single most important fact about the codebase and the reason nothing worked
  end to end.
- **Lineage B — `plugin_base.py` plus `discovery.py`, `security.py`, `orchestration.py`,
  `hot_reload.py`, `marketplace.py`.** Pydantic-validated 32-field manifest, 8-state lifecycle,
  checkpointing, consciousness gating.
- **Lineage A — `plugin_manager.py`, alone.** Dataclass manifest hand-parsed with `.get()`
  defaults, 7-state status, three lifecycle hooks, no state persistence, no consciousness model.
- **The deciding evidence is the inbound consumer count.** `plugin_base.py` has **four**
  consumers: `discovery.py:24`, `orchestration.py:20`, `security.py:34`, `marketplace.py:27`.
  `plugin_manager.py` has **zero**. Nothing in the repository imports it. It is an orphan in
  the dependency graph.
- **Operator ruling 2026-09-05: `plugin_base.py` is canonical.** `plugin_manager.py`'s unique
  mechanisms are re-based onto it; its duplicate types are deleted.

### Code / architecture truth

- Contract divergence, side by side:
  - Manifest: `plugin_base.py:79` pydantic `BaseModel`, 32 fields, real validation, raises on
    malformed input — versus `plugin_manager.py:88` `@dataclass`, hand-parsed at `:118-144`,
    silent tolerance of malformed input. **Opposite tolerance postures.**
  - Base class: `plugin_base.py:230` `PluginBase(PluginInterface, StateInterface, ABC)`,
    four hooks `_plugin_initialize/_activate/_deactivate/_cleanup` (`:548-566`) — versus
    `plugin_manager.py:147` `PluginBase(ABC)`, three hooks `on_initialize/on_activate/on_deactivate`
    (`:303-316`). **No cleanup hook exists in Lineage A.**
  - Lifecycle: `PluginState` 8 values (`plugin_base.py:40`) versus `PluginStatus` 7 values
    (`plugin_manager.py:52`).
  - Permissions: closed `PluginPermission` enum, 8 values (`plugin_manager.py:75`) versus
    free-form `List[str]` (`plugin_base.py:101`). **Lineage A has the better model here** —
    which is why it is absorbed rather than discarded.
  - Capabilities: `PluginCapability` (`plugin_base.py:28`) is a **different axis** from
    permissions — 8 values covering memory integration, consciousness access, multi-agent
    coordination, recursive processing, real-time adaptation, cross-session persistence,
    quantum coherence, temporal manipulation. Do not conflate the two.
  - State persistence: `get_state`/`set_state`/`checkpoint_state`/`restore_checkpoint`
    (`plugin_base.py:392-474`) exist only in Lineage B.
  - Consciousness gating: `_synchronize_consciousness` (`plugin_base.py:529-540`) blocks
    activation when `consciousness_level < manifest.consciousness_level_required`
    (`:313-316`). Absent from Lineage A entirely.
- **Absorbed from `plugin_manager.py` into the canonical lineage (PACKET-002):**
  `PluginPermission` (75), `PluginType` (63), the `Plugin`-class loader convention (700-706),
  the FastAPI mount path (763-809), `create_plugin_api_routes` (956), `initialize_plugin_system`
  (1024).
- **Deleted from `plugin_manager.py` (PACKET-002):** `PluginManifest` (88), `PluginBase` (147),
  `PluginDiscovery` (498), `PluginFileWatcher` (446).

### Interpretation / boundary

- **Proves:** the schism is real, enumerable, and has a determinate resolution direction.
- **Does not prove:** that the convergence is trivial. `plugin_manager.py`'s loader gates on
  `issubclass(plugin_class, PluginBase)` using its **local** `PluginBase` at `:147`. A plugin
  authored against the canonical `plugin_base.PluginBase` at `:230` is **rejected by the only
  working loader**. That gate is the load-bearing edge of the convergence.
- **Boundary:** `SPEC.md` owns the resulting contract. `AUTHORITY_MAP.md` §4 records the
  contradictions. `packets/PACKET-002-lineage-convergence.md` executes the merge.

### Failures / rejected paths

- **Rejected: keep `plugin_manager.py` as canonical and re-base the other five modules onto it.**
  Would discard pydantic validation, checkpointing, the consciousness model, and the capability
  axis, and would require rewriting four modules instead of one. Consumer count points the
  other way.
- **Rejected: treat the two lineages as peers and maintain both.** Two `PluginManifest`s and
  two `PluginBase`s in one importable namespace is the defect, not a feature.
- **Do not repeat:** do not author a plugin against `plugin_base.PluginBase` and expect the
  current loader to accept it. It will not, until PACKET-002 lands.

### Open threads

- PACKET-002 must decide what happens to `plugin_manager.PluginSecurityManager` (334), which
  overlaps `security.py`'s `SecurityManager` (609) in role but not in implementation.

### Retrieval anchors

- `SPEC.md`, `AUTHORITY_MAP.md` §4 CONTRADICTION-01 through CONTRADICTION-03
- `packets/PACKET-002-lineage-convergence.md`
- `docs/ARCHITECTURE.md` — two-lineage class ownership map
- Context index key: `2026-09-05 — CONTROL PLANE INSTALLED`

---

## 2026-09-05 — SEVEN NAME COLLISIONS ACROSS MODULES

**Keys:** `collisions` · `PluginState` · `ResourceMonitor` · `PluginStatus` · `PluginDiscovery` · `PluginFileWatcher`

**Status:** `VERIFIED`

### Durable findings

Seven type names are each defined in more than one module. Two of them mean genuinely
different things under the same name, which is the dangerous kind.

| Name | Site A | Site B | Resolution |
|---|---|---|---|
| `PluginManifest` | `plugin_base.py:79` pydantic | `plugin_manager.py:88` dataclass | A wins, B deleted |
| `PluginBase` | `plugin_base.py:230` | `plugin_manager.py:147` | A wins, B deleted |
| `PluginDiscovery` | `discovery.py:578` | `plugin_manager.py:498` | A wins, B deleted |
| `PluginFileWatcher` | `discovery.py:64` | `plugin_manager.py:446` | A wins, B deleted |
| `PluginStatus` | `plugin_manager.py:52` | `marketplace.py:40` | Both superseded by `plugin_base.PluginState`; marketplace keeps a distinct listing-status type under a new name |
| **`PluginState`** | `plugin_base.py:40` **Enum, lifecycle** | `hot_reload.py:56` **dataclass, runtime snapshot** | **Unrelated meanings.** A keeps the name; B is renamed |
| **`ResourceMonitor`** | `plugin_base.py:569` **per-plugin** | `orchestration.py:105` **workflow-level** | **Genuinely different scopes.** Both survive under distinct names |

### Interpretation / boundary

- No runtime shadowing occurs today, because every import is a named-symbol import
  (`orchestration.py:20`, `discovery.py:24`, `security.py:34`, `marketplace.py:27`). The
  collisions are a comprehension hazard now and a merge hazard during PACKET-002.
- `PluginState` and `ResourceMonitor` are the two that must **not** be resolved by simple
  deletion. They name different concepts.

### Retrieval anchors

- `docs/ARCHITECTURE.md` — collision map
- `AUTHORITY_MAP.md` §4 CONTRADICTION-02, CONTRADICTION-03

---

## 2026-09-05 — NEGATIVE KNOWLEDGE: DISPROVEN INHERITED CLAIMS

**Keys:** `TODO.md` · `disproven` · `example_plugin` · `production-ready` · `NOTEPAD-contamination`

**Status:** `VERIFIED` (disproof) + `SUPERSEDED` (the claims)

### Durable findings

The documents inherited with the extraction asserted things the source disproves. Recorded here
so no future agent re-adopts them.

- **DISPROVEN — "PRODUCTION-READY … 95% Complete … Total Estimated Completion Time for Remaining
  Tasks: 2-4 hours."** Asserted throughout the former `TODO.md` (dated August 13 2025).
  Disproven by the lineage schism, by `security.py:34`'s missing symbol, and by the empty
  reference plugin. The file was deleted 2026-09-05; recover from git at `5278e3c` if the
  historical text is ever needed.
- **DISPROVEN — `installed/example_plugin/` is a "Complete example with all interfaces"**
  (former `TODO.md:68`). It is **14 files totalling 0 bytes**, committed empty in `5278e3c`.
  Git history contains no populated version. `installed/example_plugin/memory/extensions` is a
  0-byte **regular file** that was a directory in the donor and got flattened during extraction.
- **DISPROVEN — the per-file line counts in the former `TODO.md`** ("750+ lines", "500+ lines").
  Actual: `plugin_manager.py` 1,055; `plugin_base.py` 620; `security.py` 914; `discovery.py` 824;
  `hot_reload.py` 834; `orchestration.py` 734; `marketplace.py` 845. Total 5,826.
- **CONTAMINATION — the inherited `NOTEPAD.md`** held 436 lines belonging to an unrelated OSINT
  investigation, carrying `holomodal-work` paths. It was never this repository's history. The
  operator's ruling: that document supplied the **structural form** to copy, nothing more. The
  foreign content was deleted 2026-09-05 and the form retained.
- **CONTAMINATION — `AGENTS.md` and `CLAUDE.md` were byte-identical** (27,955 bytes each) and
  hardcoded absolute paths into `/home/daeron/LAB/Experiments/projects/holomodal-work/`. Two
  identical routers carry no more information than one.

### Interpretation / boundary

- **Do not repeat:** do not trust an inherited status claim in this repository without checking
  it against source. Extraction carries documentation forward unchanged while the code's context
  changes underneath it.
- Verification in this repository is **experimentation**, not a pytest suite, per operator
  doctrine. An honest `NOT RUN` outranks a green check that proves nothing.

### Retrieval anchors

- `AUTHORITY_MAP.md` §4 CONTRADICTION-04, CONTRADICTION-05, CONTRADICTION-06
- `docs/DEFECT_INDEX.md`
- git: `git show 5278e3c:TODO.md`

---

## 2026-09-05 — REJECTED PATH: SEVERING THE HOST BOUNDARY WITH LOCAL VALUE OBJECTS

**Keys:** `host-boundary` · `schemas.session` · `SessionID` · `identifiers.py` · `hard-ban-1` · `rejected-path`

**Status:** `FAILED` / `REJECTED` — recorded so it is not attempted again

### Durable findings

- During the control-plane session, a subagent's scaffolding skill produced
  `tools/native/plugin/identifiers.py` (154 lines). It was competent code, not filler: frozen
  dataclasses, a compiled `SESSION_ID_PATTERN`, a `TypedDict` payload, a domain-specific
  `IdentifierValidationError`, and a 354-line smoke harness.
- Its docstring stated the intent plainly: *"Provide stdlib-first agnostic plugin identity value
  objects that sever donor `schemas.session` coupling without adapter indirection."*
- **This is a hard-ban-1 violation.** `schemas.session` is not a coupling to be severed. It is
  the host boundary — the seam by which this substrate attaches to an embedding system. See
  `2026-09-05 — EXTRACTION PROVENANCE: THE DONOR BOUNDARY IS A CONTRACT, NOT A DEFECT`.
- Deleted 2026-09-05 by operator decision, after preservation at commit `b9586ea`.

### Interpretation / boundary

- **Why this is worth recording rather than simply deleting:** the approach is *attractive*. It
  makes `import plugin_base` succeed, it is stdlib-only, and it produces clean typed code. An
  agent optimizing for "make the imports work" will reinvent it.
- **Why it is wrong:** a local `SessionID` that satisfies the type annotation is not the host's
  `SessionID`. Plugins would carry identity objects the embedding system does not recognize, and
  the substrate would silently stop being embeddable — the exact property this repository exists
  to have. The failure would be invisible until integration.
- The legitimate strategies are enumerated in `HOST_BOUNDARY.md` section 4: protocol declaration,
  host-supplied injection, or namespace package. All three keep the host as the source of the
  concrete type. `packets/PACKET-003-host-boundary-realization.md` owns the choice.

### Failures / rejected paths

- **REJECTED — reimplement host types locally to make imports resolve.** Severs the
  cross-ecosystem contract. Fails silently at integration time, not at import time.
- **DO NOT** recover `identifiers.py` from history as prior art. `git show b9586ea:tools/native/plugin/identifiers.py`
  exists for provenance only.

### Retrieval anchors

- `HOST_BOUNDARY.md` section 4 · `AUTHORITY_MAP.md` section 6
- `AGENTS.md` section 9, hard ban 1
- `packets/PACKET-003-host-boundary-realization.md` Hard Bans
- Related memory: `2026-09-05 — EXTRACTION PROVENANCE`

---

## 2026-09-05 — DOCTRINE SPECIALIZATION: NOTEPAD IS HISTORY, NEVER AUTHORITY

**Keys:** `doctrine` · `source-hierarchy` · `NOTEPAD` · `STATE.md` · `CONTEXT.md` · `PLAN.md`

**Status:** `OPERATOR-DIRECTIVE`

### Durable findings

The inherited constitution contained a self-contradiction: its source-hierarchy table ranked
`NOTEPAD.md` at priority 2, while prose in the same document stated `NOTEPAD.md` "is not canon
authority and does not replace `AGENTS.md`, `STATE.md`, `MEMORY.md`, or `CONTEXT.md`."

**Specialization ruling for this repository:**

- `NOTEPAD.md` is **History**. Append-only. It records what happened and what follows. It is
  never consulted to determine what is currently true, and it never overrides a normative
  surface. It was removed from the authority hierarchy entirely.
- `STATE.md` owns **single-screen current runtime truth**: does it import, what is the gate
  posture, what is the active packet. Refreshed on every state change.
- `CONTEXT.md` owns the **dated chronological traversal index** into `MEMORY.md`. These two
  charters are deliberately non-overlapping so they cannot become rival current-state surfaces.
- **`PLAN.md` was deliberately not created.** `TASK.md` plus `packets/` already fills that role.
  A second planning surface would be a rival authority, which is the exact failure mode this
  control plane exists to prevent.

### Interpretation / boundary

- **Proves:** the repository now has one current-state surface, one index, one history, one
  board, and one router — each with a distinct charter.
- The surfaces relate through a field of functional relations, not a single authority tree.
  `AUTHORITY_MAP.md` §2 is the map of those relations.

### Retrieval anchors

- `AGENTS.md` — Source Hierarchy section
- `AUTHORITY_MAP.md` §2, §4 CONTRADICTION-06

---

## Canon / Authority Lock

Canonical implementation surfaces:
- `plugin_base.py` — the plugin contract. Canonical per the 2026-09-05 lineage ruling.
- `discovery.py` — discovery and dependency resolution.
- `security.py` — trust boundary and code analysis.
- `orchestration.py` — execution scheduling and workflow interpretation.
- `hot_reload.py` — development reload and state preservation.
- `marketplace.py` — distribution.

Superseded implementation surface:
- `plugin_manager.py` — retains the only loader and FastAPI mount until PACKET-002 re-bases them.
  Its duplicate types are scheduled for deletion. Do not build on them.

Persistent authority / state surfaces:
- `AGENTS.md` — router and doctrine
- `SPEC.md` — plugin contract
- `HOST_BOUNDARY.md` — embedding contract
- `OPSEC.md` — trust boundary posture
- `STATE.md` — current runtime truth
- `MEMORY.md` — this file
- `CONTEXT.md` — traversal index

Historical / non-canon surfaces:
- `NOTEPAD.md` — append-only history. Never authority.
- `filetree.md` — generated topology. Never routing.

Authority rule:
`OPERATOR DIRECTIVE` → `LIVE SOURCE` → `NORMATIVE DOCS` (`SPEC.md`, `HOST_BOUNDARY.md`, `OPSEC.md`)
→ `CURRENT STATE` (`STATE.md`, `TASK.md`, active packet) → `GENERATED MAPS` (`filetree.md`)
→ `HISTORY` (`NOTEPAD.md`, superseded `MEMORY.md` entries).

A generated map, a summary, or the router never owns behavior it merely describes.

---

## Long-Lived System Map

### `plugin-contract`

- Authority: `plugin_base.py`, specified in `SPEC.md`
- Key symbols: `PluginManifest` (79), `PluginBase` (230), `PluginCapability` (28), `PluginState` (40)
- Inputs: `manifest.json` per plugin directory
- Outputs: a validated, lifecycle-managed plugin instance
- Depends on: host `core.memory_core`, `schemas.session`
- Feeds: `discovery.py`, `orchestration.py`, `security.py`, `marketplace.py`
- Current invariant: 33 manifest fields, 8 lifecycle states, 4 author-implemented hooks
- Search keys: `PluginManifest`, `_plugin_initialize`, `consciousness_level_required`

### `plugin-loading`

- Authority: `plugin_manager.py:668-809` until PACKET-002 re-bases it into the canonical lineage
- Key symbols: `load_plugin` (668), `_load_plugin_module` (730), `_register_plugin_api` (763)
- Current invariant: a plugin module must expose a module-level class named exactly `Plugin`;
  an API extension must expose `router` in `api/__init__.py` — **not** `api/routes.py`
- Known hazard: the `issubclass` gate at `:701` binds to the superseded `PluginBase`
- Search keys: `getattr(plugin_module, 'Plugin'`, `_register_plugin_api`

### `extension-points`

- Authority: declared in `plugin_base.py:107-111`, consumed by **nothing**
- Current invariant: `api_endpoints`, `ui_components`, `agent_actions`, `workflow_nodes`,
  `memory_extensions` are manifest fields that no loader code path reads. The
  `agents/`, `workflows/`, `memory/`, `assets/` directory convention mirrors those field names
  but is currently conventional, not functional. Only `plugin.py` and `api/__init__.py` are
  ever touched by loader code.
- Search keys: `agent_actions`, `workflow_nodes`, `memory_extensions`

---

## Durable Operator / Repository Doctrine

- **The donor imports are a contract, not a defect.** Declare them in `HOST_BOUNDARY.md`.
  Never vendor stubs or delete them to make an import succeed.
- **The flat layout is intentional.** This package is embedded in larger Somnus systems. No
  `src/` migration, no standalone-distribution packaging assumptions.
- **No stubs, no fallbacks, no shims, no thin adapters.** The stated goal is strict deep
  integration. If a main file must orchestrate, everything works within it — not some of it.
- **Tests are experimentation.** Do not manufacture a pytest suite to produce a green check.
  Record `NOT RUN` or `NOT VERIFIABLE` when a prerequisite is absent.
- **Language discipline.** Do not describe operator-built code with `thin`, `quick`, `small`,
  or `easy`. Describe limited scope concretely instead.
- **Python is the canvas, not necessarily the end runtime.** Components may be trained; mark
  downstream ordering dependencies when discovered.
- **Read `filetree.md` between file reads** to prevent codebase blindness — but never route
  work from it.

---

## Known Hazards / Anti-Rediscovery Index

- `LOADER-GATE` — the only working loader rejects plugins written against the canonical base
  class. `plugin_manager.py:701`. See `2026-09-05 — LINEAGE RULING`.
- `MISSING-PERMISSION-SYMBOL` — `security.py:34` imports `PluginPermission` from a module that
  does not define it. Predicted `ImportError`, not yet observed. See `AUTHORITY_MAP.md`
  CONTRADICTION-01.
- `PLUGINSTATE-AMBIGUITY` — `PluginState` names a lifecycle Enum in one module and a runtime
  snapshot dataclass in another. See `2026-09-05 — SEVEN NAME COLLISIONS`.
- `EMPTY-REFERENCE-PLUGIN` — `installed/example_plugin/` is 0 bytes throughout. Do not read it
  as an example. See `2026-09-05 — NEGATIVE KNOWLEDGE`.
- `PHANTOM-REGISTRY` — `marketplace.py` targets `marketplace.morpheus.ai` and
  `community.morpheus.ai`, neither of which exists. See `docs/DEFECT_INDEX.md` D-016.
- `FAKE-SIGNATURE` — `marketplace.py:346` compares a server-supplied hash to a locally computed
  SHA-256 and calls it signature verification. See `OPSEC.md` and `docs/DEFECT_INDEX.md` D-004.
- `INHERITED-DOC-DRIFT` — extraction carried documentation forward while the code's context
  changed. Verify any inherited status claim against source. See `2026-09-05 — NEGATIVE KNOWLEDGE`.
- `BOUNDARY-SEVERING` — reimplementing host types locally to make imports resolve is attractive,
  clean, and wrong. See `2026-09-05 — REJECTED PATH: SEVERING THE HOST BOUNDARY`.
- `ENV-NO-DEPS` — **superseded 2026-09-18.** `.venv` exists; modules import; the remaining
  hazard is ambient in-process execution, not missing dependencies.

## 2026-09-18 — AUTHORITY CONVERGENCE LANDED

**Keys:** `PACKET-002` · `PACKET-004` · `plugin_identity` · `example_plugin_1.0.0` · `SecurityEnforcer` · `SecurityManager`

- `plugin_base.py` is canonical in source. Manager-local contract types are deleted.
- Plugin identity is `{name}_{version}` via `plugin_identity()`.
- `SecurityEnforcer` survives as the host policy Protocol. Static analysis is
  `security.SecurityManager`. The always-true signature stub is gone.
- Checkpoints hash canonical plugin-owned state. Duplicate content returns the
  existing stored checkpoint id.
- `installed/example_plugin/` is the reference. Production path proven in
  `validate_system.py` check `production_load_path`.
- Permissions remain descriptive until PACKET-005.

---

## Memory Maintenance Notes

- The file may contain apparently conflicting historical entries. Resolve by date, status, provenance, and explicit supersession rather than deleting history.
- When a finding becomes important enough to guide near-term work, add or refresh its compact mirror in `CONTEXT.md`.
- When `CONTEXT.md` points here, preserve the same nouns and keys. Retrieval quality depends on lexical continuity.
- If memory grows beyond convenient direct reading, that is expected. Improve indexing and traversal; do not neuter the memory substrate.
