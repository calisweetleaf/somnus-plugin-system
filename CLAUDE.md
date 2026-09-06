# CLAUDE.md — somnus-plugin-system

**Claude Code runtime specialization. Extends `AGENTS.md`; does not replace or duplicate it.**

`AGENTS.md` owns project identity, the surface router, source hierarchy, packet route,
validation route, hard bans, and doctrine. **Read it first.** This file covers only what is
different when the executing agent is Claude Code.

> Before 2026-09-05 this file was a byte-identical copy of `AGENTS.md` (27,955 bytes each). Two
> identical routers carry no more information than one. It was differentiated during the control
> plane installation. If you find these two files converging again, that is drift — repair it.

---

## 1. Substrate reality for Claude Code

**SovereignMCP is not available here.** The `bb7_*` surfaces described in the Somnus
constitution are a Codex-side substrate. Claude Code in this repository has native tools and the
`codegraph` MCP server.

Per doctrine: *absence of SovereignMCP is not permission to pretend it was used.* Do not write
`bb7_exo_reflect` into a handoff you did not run. When continuity would have been persisted via
`bb7_memory_store`, persist it to `MEMORY.md` and `CONTEXT.md` instead — those are the durable
substrate in this repository.

| Doctrine surface | Claude Code equivalent here |
|---|---|
| `bb7_memory_store` | Append to `MEMORY.md`, mirror the key in `CONTEXT.md` |
| `bb7_capture_insight` | `NOTEPAD.md` append; promote to `MEMORY.md` if durable |
| `bb7_log_event` | `NOTEPAD.md` handoff block |
| `bb7_exo_reflect` | The Exit and Handoff fields of the active packet |
| SovereignMCP routing | `AGENTS.md` §2 session-entry table |

## 2. Tool posture

- **Prefer `codegraph` over grep sweeps** for structural questions, but know its limits here.
  Measured 2026-09-05: `codegraph callers` resolves function and method call edges only — it
  returns "No callers found" for `PluginBase` despite four modules importing that class. Use
  `codegraph impact <symbol>` for a type's cross-module blast radius. The lineage ruling came
  from `grep -rn 'from plugin_base import' ./*.py` (4 hits) versus
  `grep -rn 'from plugin_manager import' ./*.py` (0 hits), not from codegraph.
- **Read `filetree.md` between file reads** to prevent codebase blindness. Never route from it.
- `somnus-debug structure <file.py>` gives an AST-only view of a single module. It cannot run
  against this repository's modules until dependencies exist — see `PACKET-001`.
- Independent tool calls go in one message. Do not serialize reads that have no dependency.

## 3. Subagent lanes

Subagents work **ahead of and behind** the main operator, not instead of. The main agent owns
the core implementation and every surface that defines authority. Subagents are boosters.

**Lane discipline — the one rule that matters:** two agents must never hold the same file.
Assign disjoint file lanes in the brief, explicitly, by path.

| Agent | Lane | Never touches |
|---|---|---|
| `defense-grade-doc-engine` | `docs/**` — diagrams, defect register, evidence presentation | Any authority surface: `AGENTS.md`, `SPEC.md`, `MEMORY.md`, `AUTHORITY_MAP.md`, `HOST_BOUNDARY.md`, `OPSEC.md`, `STATE.md` |
| `.claude/agents/lineage-convergence-surgeon` | The 7 modules during `PACKET-002` | Control-plane documents |
| `.claude/agents/plugin-contract-auditor` | Read-only audit against `SPEC.md` | Everything — it reports, it does not write |
| `.claude/agents/host-boundary-validator` | Read-only check of the donor seam | Everything — it reports |
| `Explore` | Read-only reconnaissance | **Everything.** See §3a |

### 3a. Hazard — subagents can write even when you believe they cannot

On 2026-09-05, during plan mode, a subagent dispatched for read-only reconnaissance invoked a
scaffolding skill that created `SCOPE.md`, `SOTA_RUN.md`, `requirements.txt`, `tools/`, `test/`,
and `snapshots/` in this repository. The `Explore` agent type excludes `Edit`/`Write` but retains
`Bash` and `Skill`, so the tool-level restriction did not prevent filesystem writes.

**Consequences for how you brief agents here:**

1. State write bans **explicitly in the prompt**, by path. Do not rely on the agent type's tool
   list to enforce read-only.
2. After any subagent returns, run `git status --short` before trusting the working tree.
3. A subagent reporting "I did not write anything" is reporting its intent, not the filesystem.
   Verify.

## 4. Plan mode and packets

They are the same shape at different scales. A plan-mode plan is a packet that has not been
written to `packets/` yet.

- Entering plan mode for a packet already written in `packets/` is redundant — the packet already
  carries Mission, Required Reads, Invariant, Surfaces, Hard Bans, Validation, Exit, Handoff.
  Execute it.
- Entering plan mode is correct when the work is not yet packetized, when the operator's intent
  spans multiple packets, or when a state reconciliation is needed first.
- When a plan is approved and it is a coherent cross-surface transaction, **write it to
  `packets/` before executing**, so the next agent inherits it.

## 5. Permissions

`.claude/settings.json` is derived from this repository's **actual layout**.

The global `~/CLAUDE.md` permission shape (`Write(src/**)`, `Write(tests/**)`, deny
`Write(manifest.json)`) does not apply here. This repository has no `src/`, no `tests/`, and
`installed/example_plugin/manifest.json` is a legitimate target for `PACKET-004`. Copying that
shape would lock every agent out of every file. If you are adding a permission, derive it from
what exists.

## 6. Session close

There is no `ctmv3` engine wired into this repository. The close protocol is the one in
`AGENTS.md` §7:

1. Append the handoff block to `NOTEPAD.md`
2. Refresh `STATE.md`
3. Append the routing entry to `CONTEXT.md`
4. Add durable decisions to `MEMORY.md`
5. Update `TASK.md`
6. Refresh `filetree.md` if structure changed

Run `bash gate.sh` before claiming anything is done, and report its output verbatim — including
`NOT RUN`.
