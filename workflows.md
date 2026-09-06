# workflows.md — Tool Composition for somnus-plugin-system

> This repository's operational compilation layer between agent intent and the available
> substrate. It is expected to evolve. When a recurring sequence, failure mode, validation
> pattern, or recovery path becomes materially better understood, update this file so later
> agents inherit the improvement rather than rediscovering it.
>
> `AGENTS.md` defines how to operate here. This file defines how to compose tools here.

---

## Substrate availability

| Substrate | Available to Claude Code here | Notes |
|---|---|---|
| SovereignMCP (`bb7_*`) | **No** | Codex-side substrate. Absence is not permission to pretend it was used. See `CLAUDE.md` section 1 for the equivalence table. |
| `codegraph` MCP | Yes | Structural intelligence. Not repository truth. |
| `somnus-debug` | Host-installed | Cannot analyze these modules until PACKET-001 lands. |
| Native tools | Yes | Read, Grep, Glob, Bash, Edit, Write. |
| `gate.sh` | Yes | The repository's own validation entrypoint. |

Codex, opencode, and commandcode operate under SovereignMCP and should compose per their own
doctrine, using this file for repository-specific sequences.

---

## Workflow 1 — Cold entry

Three reads, then act. Do not tour the codebase.

```
AGENTS.md  →  STATE.md  →  TASK.md  →  the named packet in packets/
```

Do **not** read all 7 modules to orient. `docs/ARCHITECTURE.md` already contains the wiring
diagram, and `AUTHORITY_MAP.md` already classifies every surface. Reading source to build a
mental map that already exists in the repository is the failure mode this control plane exists
to prevent.

## Workflow 2 — "What does this symbol do and who uses it?"

```bash
codegraph query <symbol>     # fuzzy symbol search across the index
codegraph impact <symbol>    # cross-module blast radius — WORKS for classes
codegraph callers <symbol>   # function/method call edges only — see caution below
codegraph callees <symbol>
```

**`codegraph callers` does not resolve class references.** Measured 2026-09-05:
`codegraph callers PluginBase` reports "No callers found" even though four modules import that
class. For import-level consumers, grep the import statements directly:

```bash
grep -rn 'from plugin_base import' ./*.py
```

Use `codegraph impact` when you need a type's blast radius before changing it.

**Caution specific to this repository:** several symbol names are defined in more than one
module — `PluginManifest`, `PluginBase`, `PluginDiscovery`, `PluginFileWatcher`, `PluginState`,
`PluginStatus`, `ResourceMonitor`. A `codegraph query` on any of these returns multiple
definition sites and that is correct, not an index error. Cross-check against
`MEMORY.md` → `2026-09-05 — SEVEN NAME COLLISIONS ACROSS MODULES` before drawing a conclusion.

The lineage ruling was established by import-statement grep, not codegraph. Re-run
`grep -rn 'from plugin_manager import' ./*.py` after PACKET-002 to confirm the convergence.

## Workflow 3 — Before changing a plugin type

```
SPEC.md section 1        # is this type canonical or superseded?
AUTHORITY_MAP.md §1      # what consumes it?
codegraph callers <T>    # confirm against the index
```

Then dispatch `.claude/agents/plugin-contract-auditor` on the result before committing.

If the type is one of the seven collisions, read the ruling in `MEMORY.md` first. Two of them —
`PluginState` and `ResourceMonitor` — must **not** be resolved by deletion.

## Workflow 4 — An import does not resolve

Decide which of three cases it is **before** touching anything:

1. **Host boundary** (`core.*`, `schemas.*`) → `HOST_BOUNDARY.md`. **Correct behavior. Do not
   fix.** Dispatch `.claude/agents/host-boundary-validator` if unsure.
2. **Missing dependency** → `pyproject.toml`. PACKET-001 territory.
3. **Missing symbol from a sibling module** → this is CONTRADICTION-01 territory. Read
   `AUTHORITY_MAP.md` section 4 before assuming it is new.

**Never** resolve any of the three with a stub, a mock, or `try/except ImportError`.

## Workflow 5 — Executing a packet

```bash
node ~/.claude/skills/somnus-accelerate/scripts/validate-packet.mjs packets/<PACKET>.md
# read Required Reads, in order
# implement against Surfaces, respecting Hard Bans
bash gate.sh
# fill Exit, append handoff to NOTEPAD.md
```

Then synchronize per `AGENTS.md` section 7: `NOTEPAD.md`, `STATE.md`, `CONTEXT.md`, `MEMORY.md`,
`TASK.md`, and `filetree.md` if structure changed.

## Workflow 6 — Dispatching a subagent

1. Assign a **disjoint file lane by explicit path**. Two agents never hold the same file.
2. State write bans **in the prompt**, by path. The agent type's tool list is not sufficient —
   `Explore` excludes `Write` but retains `Bash` and `Skill`, and has written to this repository
   before. See `CLAUDE.md` section 3a.
3. Pre-load the schism. An agent that has to rediscover the two lineages wastes its context.
4. After it returns, run `git status --short` before trusting the tree.

## Workflow 7 — Verifying repository state before trusting a document

```bash
bash gate.sh
git status --short
git diff --stat -- '*.py'
grep -rn '^from \(core\|schemas\|backend\)\.' *.py   # must be exactly 6 lines
```

This repository's documents were inherited from a donor codebase whose context changed underneath
them. **Live source outranks every document here.** When a document and the source disagree,
source wins and the document is repaired in the same turn.

---

## Known failure modes and recovery

| Failure mode | Recovery |
|---|---|
| Agent starts adding features on top of a broken foundation | Route it to `STATE.md`. Nothing imports. PACKET-001 first. |
| Agent "fixes" a host-boundary import | Revert. Read `HOST_BOUNDARY.md`. Dispatch `host-boundary-validator`. |
| Agent treats `installed/example_plugin/` as a reference | It is 14 files at 0 bytes. See `MEMORY.md` → NEGATIVE KNOWLEDGE. |
| Agent authors a plugin that validates but will not load | The loader gates on the superseded base class at `plugin_manager.py:701`. See `SPEC.md` section 7. |
| Agent reports a green gate | Check for `NOT RUN` lines. A `NOT RUN` is not a pass. |
| Agent trusts an inherited status claim | Verify against source. The former `TODO.md` claimed 95% complete and production-ready; it was deleted as disproven. |
| `codegraph` returns multiple definitions for one symbol | Expected. Seven names collide. See Workflow 2. |
