# Authority Map — somnus-plugin-system

> Repository archaeology output. Produced 2026-09-05 by direct source reading, not inference.
>
> This file records **what each surface actually is**, who owns it, what enforces it, and where
> it contradicts another surface. It is the first thing to read when a claim in any other
> document is in doubt.
>
> Classification vocabulary is the Somnus Accelerate archaeology taxonomy. A file may hold more
> than one relation but is never promoted to a stronger authority class for convenience.

## Classification vocabulary

| Class | Meaning |
|---|---|
| Current state | What is actively true now |
| Context | Material needed to understand active work |
| Cognition | Router, operating protocol, vocabulary, execution constraints |
| History | Append-only record, provenance, past decisions |
| Proposal | Roadmap, future design, unlanded plan |
| Normative | Defines a boundary or owns a behavior locally |
| Evidence | Tests, traces, fixtures, measurements, known repros |
| Generated | Downstream artifact produced from another surface |
| Metadata | Build, package, CI, manifest, tool configuration |
| Noise | Stale, duplicate, abandoned, or untrusted material |

Enforcement levels: **mechanical** (a command fails), **conventional** (agents are expected to
comply), **none** (descriptive only).

---

## 1. Implementation surfaces

### `plugin_base.py` — 620 lines — **CANONICAL**

- **Class:** Normative. This module owns the plugin contract.
- **Owner:** the plugin authoring boundary.
- **Enforcement:** mechanical at runtime via pydantic validation (`PluginManifest`, line 79);
  conventional for the abstract hook set.
- **Defines:** `PluginCapability` (28), `PluginState` (40, `str` Enum, 8 lifecycle values),
  `PluginContext` (53), `PluginMetrics` (67), `PluginManifest` (79, pydantic `BaseModel`,
  32 fields), `PluginInterface` (139), `ConsciousnessInterface` (168), `StateInterface` (187),
  `NetworkInterface` (211), `PluginBase` (230), `ResourceMonitor` (569).
- **Consumers:** `discovery.py:24`, `orchestration.py:20`, `security.py:34`, `marketplace.py:27`.
  **Four inbound edges — the hub of the real dependency graph.**
- **Evidence for canonical status:** consumer count (4 vs 0 for `plugin_manager.py`), richer
  lifecycle contract (checkpointing at 392-474, consciousness gating at 529-540), and runtime
  schema validation. Operator ruling recorded 2026-09-05.
- **Does not own:** plugin loading, module import, FastAPI mounting, permission enumeration.
  Those mechanisms exist only in `plugin_manager.py` today and are scheduled to be re-based
  into this lineage by `packets/PACKET-002-lineage-convergence.md`.
- **Contradictions:** `security.py:34` imports `PluginPermission` from this module; the symbol
  is **not defined here**. See §4 CONTRADICTION-01.

### `plugin_manager.py` — 1,055 lines — **SUPERSEDED, PARTIALLY ABSORBED**

- **Class:** Normative (superseded) + Normative (retained mechanisms).
- **Enforcement:** mechanical for anything that actually loads a plugin — it holds the only loader.
- **Zero inbound consumers.** Nothing in this repository imports this module.
- **Superseded — scheduled for deletion in PACKET-002:** `PluginManifest` (88, `@dataclass`
  duplicate), `PluginBase` (147, ABC duplicate), `PluginDiscovery` (498, duplicate),
  `PluginFileWatcher` (446, duplicate), `PluginStatus` (52, superseded by `plugin_base.PluginState`).
- **Retained — scheduled for absorption into `plugin_base.py` in PACKET-002:**
  `PluginPermission` (75, 8-value enum), `PluginType` (63, 8-value enum),
  `PluginSecurityManager` (334), `PluginManager` (567), `create_plugin_api_routes` (956),
  `initialize_plugin_system` (1024), the `Plugin`-class loader convention (700-706), and the
  FastAPI mount path (763-809).
- **Load-bearing hazard:** its loader gates on `issubclass(plugin_class, PluginBase)` using its
  **local** `PluginBase` (147). A plugin authored against the canonical `plugin_base.PluginBase`
  (230) is **rejected by the only working loader**. This is the sharpest edge in the repository.

### `security.py` — 914 lines

- **Class:** Normative for the plugin trust boundary.
- **Enforcement:** mechanical — AST analysis, cryptographic validation, sandbox construction.
- **Defines:** `SecurityIssue` (40), `SecurityReport` (51), `SecurityLevel` (62),
  `SandboxEnvironment` (70), `restricted_import` (158), `CodeAnalyzer` (181),
  `CryptographicValidator` (442), `DependencyAnalyzer` (529), `SecurityManager` (609).
- **Consumers:** `marketplace.py:28`.
- **Current state:** **not importable.** See §4 CONTRADICTION-01.
- **Security posture detail:** `OPSEC.md`.

### `discovery.py` — 824 lines

- **Class:** Normative for plugin discovery and dependency resolution.
- **Defines:** `PluginIndex` (30), `DependencyNode` (46), `DiscoverySource` (55),
  `PluginFileWatcher` (64), `DependencyResolver` (130), `PluginCompatibilityChecker` (350),
  `PluginScanner` (420), `PluginDiscovery` (578).
- **Owns:** dependency graph construction (134) and topological sort (304). Note that
  dependency resolution lives **here**, not in `orchestration.py`.
- **Consumers:** none. Imported by no module.

### `orchestration.py` — 734 lines

- **Class:** Normative for execution scheduling and workflow interpretation.
- **What it actually is:** a priority-queued async method-dispatch scheduler with a circuit
  breaker, plus a step-list workflow interpreter. It is **not** an event bus, **not** pub/sub,
  and **not** where dependency resolution lives.
- **Defines:** `ExecutionMode` (25), `ExecutionPriority` (33), `WorkflowState` (41),
  `ExecutionRequest` (51), `ExecutionResult` (67), `WorkflowDefinition` (79),
  `WorkflowExecution` (93), `ResourceMonitor` (105), `ExecutionQueue` (151),
  `PluginExecutor` (198), `WorkflowEngine` (259), `PluginOrchestrator` (456).
- **Consumers:** none. Unreferenced island; takes an untyped duck-typed `plugin_manager`
  parameter at `orchestration.py:457`.
- **Zero third-party imports of its own** — everything at lines 6-18 is stdlib. Its only
  external coupling is `plugin_base` at line 20.
- **Known defects:** D-001, D-002, D-009, D-010, D-011, D-012, D-013, D-014 in
  `docs/DEFECT_INDEX.md`.

### `hot_reload.py` — 834 lines

- **Class:** Normative for development-time reload and state preservation.
- **Defines:** `ReloadType` (39), `StatePreservationLevel` (47), `PluginState` (56),
  `DependencyGraph` (112), `StateManager` (242), `HotReloadEngine` (460),
  `PluginFileHandler` (709), `HotReloadIntegration` (793), `setup_hot_reload` (830).
- **Consumers:** none.
- **Contradictions:** its `PluginState` (56) is a **dataclass holding a runtime snapshot**;
  `plugin_base.PluginState` (40) is a **`str` Enum of lifecycle states**. Same name, unrelated
  meaning, different modules. See §4 CONTRADICTION-02.

### `marketplace.py` — 845 lines

- **Class:** Normative for plugin distribution; **Proposal** in practice, because its transport
  targets hosts that do not exist.
- **Defines:** `MarketplaceProvider` (33), `PluginStatus` (40), `DistributionChannel` (49),
  `MarketplaceConfig` (56), `PluginRating` (70), `PluginStatistics` (79), `PluginListing` (89),
  `DownloadProgress` (118), `TrustSystem` (127), `RegistryClient` (191), `PluginInstaller` (437),
  `UpdateManager` (616), `PluginMarketplace` (714), `create_marketplace` (835).
- **Consumers:** none. Unreferenced island; duck-typed `plugin_manager` param at line 715.
- **Current state:** not importable, downstream of CONTRADICTION-01 via line 28.
- **Known defects:** D-003 through D-008 and D-015 through D-018 in `docs/DEFECT_INDEX.md`.

### `__init__.py` — 0 bytes

- **Class:** Metadata.
- **Current state:** the package exports nothing. Combined with flat absolute sibling imports
  (`from plugin_base import ...` rather than `from .plugin_base import ...`), these modules
  import only when the repository root is `sys.path[0]`.
- **Operator ruling 2026-09-05:** the flat layout is **intentional and retained**. This package
  is designed to be embedded inside larger Somnus systems, not distributed standalone. No
  `src/` migration. The host boundary is declared in `HOST_BOUNDARY.md` rather than removed.

### `installed/` — scaffold skeleton

- **Class:** Metadata (directory convention) + Noise (its current contents).
- **Current state:** `installed/example_plugin/` is **14 files totalling 0 bytes**, committed
  empty in `5278e3c`. It subclasses nothing and demonstrates nothing.
- `installed/example_plugin/memory/extensions` is a **0-byte regular file** that was a directory
  in the donor codebase and was flattened during extraction.
- **Contradiction:** `TODO.md:68` describes this as "Complete example with all interfaces."
  That claim is false. See §4 CONTRADICTION-04.
- `installed/community/{experimental,featured,verified}`, `installed/sandbox/untrusted`, and
  `installed/templates/{agent_action,api_extension,basic_plugin,ui_component,workflow_node}`
  are empty directories asserting a taxonomy no code currently reads.

---

## 2. Control-plane surfaces

| Path | Class | Owns | Enforcement | Read when |
|---|---|---|---|---|
| `AGENTS.md` | Cognition | Routing, execution topology, doctrine | conventional | Every cold entry |
| `CLAUDE.md` | Cognition | Claude Code runtime specialization of `AGENTS.md` | conventional | Cold entry, Claude runtime only |
| `SPEC.md` | Normative | The adjudicated plugin contract | conventional | Before touching any plugin type |
| `HOST_BOUNDARY.md` | Normative | What the embedding system must supply | conventional | Before touching a donor import |
| `OPSEC.md` | Normative | Security posture and trust boundary | conventional | Before touching `security.py` or `marketplace.py` |
| `STATE.md` | Current state | Single-screen runtime truth | conventional | Start of every turn |
| `CONTEXT.md` | Context | Dated traversal index into `MEMORY.md` | conventional | Resuming work |
| `MEMORY.md` | History + Normative | Durable decisions, stable vocabulary | conventional | Looking up a past ruling |
| `NOTEPAD.md` | History | Append-only state-change log | conventional | Reconstructing what happened |
| `TASK.md` | Current state | Packet board | conventional | Choosing what to execute |
| `packets/*.md` | Current state | Bounded executable work | mechanical via `validate-packet.mjs` | Executing |
| `AUTHORITY_MAP.md` | Cognition | This file — surface classification | conventional | A claim is in doubt |
| `filetree.md` | Generated | Whole-repo topology | none | Regaining orientation |
| `workflows.md` | Cognition | Tool composition for this repository | conventional | Choosing an approach |
| `README.md` | Descriptive | Narrative anchor | none | First contact |
| `docs/ARCHITECTURE.md` | Descriptive + Evidence | Wiring diagrams | none | Understanding structure |
| `docs/DEFECT_INDEX.md` | Evidence | Verified defect register | none | Before trusting any module |
| `pyproject.toml` | Metadata | Dependency contract | mechanical once installed | Environment work |
| `gate.sh` | Evidence | Validation entrypoint | mechanical | Before claiming done |
| `.claude/` | Metadata | Claude Code harness | mechanical | Harness changes |

### Deleted this session

| Path | Was | Why removed |
|---|---|---|
| `TODO.md` | Noise | Asserted "PRODUCTION-READY / 95% Complete / 2-4 hours remaining" (dated August 13 2025). Disproven by CONTRADICTION-01 and CONTRADICTION-04. Superseded by `TASK.md` + `packets/`. Disproof preserved in `MEMORY.md`; content recoverable from git history at `5278e3c`. |

### Reset this session

| Path | Was | Now |
|---|---|---|
| `NOTEPAD.md` | 436 lines of an unrelated OSINT investigation (Thiel / Ellison / Schmidt), carrying `holomodal-work` paths | Clean append-only log for this repository. The foreign document supplied the structural form only; its content was never this repository's history. |

---

## 3. Host boundary surfaces

These imports do **not** resolve inside this repository and are **not** defects. They are the
contract the embedding system fulfils. Full detail in `HOST_BOUNDARY.md`.

| Import | Symbols | Call sites |
|---|---|---|
| `core.memory_core` | `MemoryManager`, `MemoryType`, `MemoryImportance`, `MemoryScope` | `plugin_base.py:22`, `plugin_manager.py:46`, `hot_reload.py:34` |
| `schemas.session` | `SessionID`, `UserID` | `plugin_base.py:23`, `plugin_manager.py:45` |
| `core.security_layer` | `SecurityEnforcer` | `plugin_manager.py:47` |

---

## 4. Contradictions register

Recorded, not resolved. Each names the surface that wins and the packet that lands the fix.

**CONTRADICTION-01 — `PluginPermission` is on the wrong side of the seam.**
`security.py:34` does `from plugin_base import PluginManifest, PluginPermission`. Repository-wide,
`class PluginPermission` exists only at `plugin_manager.py:75`. `security.py` consumes the symbol
at lines 220, 223, 226, 229, 419, 433, and 703-705.
*Winner:* `plugin_base.py` — the symbol belongs in the canonical lineage.
*Status:* grep-verified absent. The `ImportError` itself is **PREDICTED, NOT YET OBSERVED** —
the prerequisite (dependency install) has not run. Do not report it as observed.
*Lands in:* PACKET-002, gated behind PACKET-001.

**CONTRADICTION-02 — `PluginState` names two unrelated concepts.**
`plugin_base.py:40` is a `str` Enum of 8 lifecycle states. `hot_reload.py:56` is a dataclass
holding a runtime snapshot.
*Winner:* `plugin_base.py` keeps the name. `hot_reload.py`'s type is renamed.
*Lands in:* PACKET-002.

**CONTRADICTION-03 — five further duplicate type names.**
`PluginManifest` (`plugin_base.py:79` vs `plugin_manager.py:88`), `PluginBase`
(`:230` vs `:147`), `PluginDiscovery` (`discovery.py:578` vs `plugin_manager.py:498`),
`PluginFileWatcher` (`discovery.py:64` vs `plugin_manager.py:446`), `ResourceMonitor`
(`plugin_base.py:569` vs `orchestration.py:105`), `PluginStatus` (`plugin_manager.py:52` vs
`marketplace.py:40`).
*Winner:* the canonical lineage in every case, except `ResourceMonitor` where the two are
genuinely different scopes (per-plugin vs workflow-level) and both survive under distinct names.
*Lands in:* PACKET-002.

**CONTRADICTION-04 — `installed/example_plugin/` is described as complete and is empty.**
`TODO.md:68` asserted "Complete example with all interfaces." All 14 files are 0 bytes.
*Winner:* the filesystem.
*Resolved:* `TODO.md` deleted this session. A real reference implementation lands in PACKET-004.

**CONTRADICTION-05 — `AGENTS.md` pointed at surfaces that did not exist.**
The pre-repair `AGENTS.md` referenced `workflows.md`, `OPSEC.md`, `STATE.md`, `PLAN.md`,
`README.md`, and `SPEC.md`, and hardcoded absolute paths into a different repository
(`/home/daeron/LAB/Experiments/projects/holomodal-work/`).
*Resolved:* this session, with one deliberate residue. Every dangling pointer was corrected
except one inside the **preserved doctrine block**: `AGENTS.md` "Packet Workflow" still opens
"For every `TASK.md` in the current `PLAN.md`". That sentence is inherited doctrine reproduced
verbatim per the operator's specialize-do-not-reduce instruction, and it is immediately preceded
by a specialization note stating that `PLAN.md` and `example.py` do not exist here and naming
`TASK.md` + `packets/` as this repository's actual route. **`PLAN.md` was deliberately not
created** — a second planning surface would create a rival authority.

**CONTRADICTION-06 — `NOTEPAD.md` was both priority 2 and "not canon authority."**
The inherited source-hierarchy table ranked `NOTEPAD.md` at priority 2 while the prose in the
same document said it "is not canon authority."
*Resolved:* this session. `NOTEPAD.md` is **History**, never authority. It records what
happened; `STATE.md` and `CONTEXT.md` carry what is true now. Recorded in `MEMORY.md`.

---

## 5. Enforcement reality

Honest statement of what actually fails versus what is merely written down.

| Mechanism | Status |
|---|---|
| Test suite | **Does not exist for this repository.** No `tests/` directory, no pytest configuration, no CI. Note: `test/plugin/smoke.py` exists on disk but was created by a subagent outside the approved plan and is not this repository's harness — see §6. |
| CI | **Does not exist.** |
| `gate.sh` | Installed this session. Reports `NOT RUN` for every dependency-gated check until PACKET-001 lands. |
| Packet field contract | Mechanical — `node ~/.claude/skills/somnus-accelerate/scripts/validate-packet.mjs` |
| pydantic manifest validation | Mechanical, but unreachable until dependencies are installed. |
| Everything in this file | Conventional. |

Per operator doctrine, validation in this repository is **experimentation**, not a pytest suite.
A green check that proves nothing is worse than an honest `NOT RUN`.


---

## 6. Foreign artifacts — operator decision pending

On 2026-09-05 at 19:35 CDT, during plan mode, a subagent dispatched for read-only reconnaissance
invoked a scaffolding skill that created the following in this repository. They were **not** part
of the approved plan and were **not** created by the main operator.

| Path | Class | Problem |
|---|---|---|
| `requirements.txt` | **Noise — actively hazardous** | Asserts "Slice 1 is stdlib-first: no third-party packages required." `pyproject.toml` declares nine dependencies. Because `requirements.txt` is a conventional filename, an arriving agent's reflex is `pip install -r requirements.txt`, which yields the wrong conclusion. |
| `tools/native/plugin/identifiers.py` | Noise | New Python source in a repository whose session guaranteed no source changes. |
| `tools/native/plugin/__init__.py` | Noise | Same origin. |
| `test/plugin/smoke.py` | Noise | Not this repository's test harness. Contradicts §5's statement that no test file exists. |
| `test/plugin/runs/` | Noise | Run artifacts from the above. |
| `SCOPE.md` | Noise | Declares a COMPOSE engagement against `tools/native/plugin/identifiers.py` that is not this repository's active work. |
| `SOTA_RUN.md` | Noise | Ledger for the same non-active engagement. |
| `snapshots/v0.1/manifest.json` | Noise | Same origin. |

**Authority ruling:** `pyproject.toml` is this repository's dependency contract. `TASK.md` plus
`packets/` is the work board. `SCOPE.md` and `SOTA_RUN.md` have no authority here.

**Status: DELETED 2026-09-05** by operator decision, after being preserved in commit `b9586ea`
as a recovery point. Recover any of them with `git show b9586ea:<path>`.

**Why deletion was correct, beyond the filename hazard.** `tools/native/plugin/identifiers.py`
(154 lines) was not inert scaffolding. Its own docstring states its purpose: *"Provide
stdlib-first agnostic plugin identity value objects that sever donor `schemas.session` coupling
without adapter indirection."* It implemented `SessionID`/`UserID` value objects to **replace**
a host-boundary type.

That is a direct violation of `AGENTS.md` hard ban 1 and of the operator ruling recorded in
`MEMORY.md` → `2026-09-05 — EXTRACTION PROVENANCE`: the donor imports are a **contract**, and
severing them destroys the cross-ecosystem seam this repository exists to provide. Had it
remained, a future agent could reasonably have read it as sanctioned prior art for resolving the
boundary locally. `packets/PACKET-003-host-boundary-realization.md` owns that decision, and its
hard bans forbid exactly this approach.

`gate.sh` section [5b] continues to detect any recurrence on every run.

**Root cause:** the `Explore` agent type excludes `Edit`/`Write` but retains `Bash` and `Skill`,
so its tool list did not prevent filesystem writes. See `CLAUDE.md` §3a.
