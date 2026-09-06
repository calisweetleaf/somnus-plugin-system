# somnus-plugin-system

Plugin substrate for the Somnus Sovereign Systems stack: plugin contract, discovery, security
analysis, execution orchestration, hot reload, and distribution.

**Private. Project-A119, Somnus MAIL-Room (Morpheus-Advanced-Intelligence-Labs).**
No external publication requirement.

---

## What this is

5,826 lines of Python across 7 flat modules, extracted from the private `somnus-os` donor
codebase at commit `5278e3c` on 2026-09-05 to become the cross-ecosystem-agnostic plugin system
for the Somnus stack.

It is designed to be **embedded inside larger systems**, never shipped standalone. Three of its
imports resolve only in a host — that is the contract, not a defect. See `HOST_BOUNDARY.md`.

| Module | Lines | Role |
|---|---|---|
| `plugin_base.py` | 620 | **Canonical.** Plugin contract: manifest, capabilities, lifecycle, base class |
| `plugin_manager.py` | 1,055 | Superseded lineage; holds the only working loader and FastAPI mount |
| `security.py` | 914 | Trust boundary: AST analysis, sandboxing, cryptographic validation |
| `discovery.py` | 824 | Discovery, dependency graph, topological resolution |
| `orchestration.py` | 734 | Priority-queued async dispatch and workflow interpretation |
| `hot_reload.py` | 834 | Development reload with state preservation |
| `marketplace.py` | 845 | Distribution, trust scoring, installation |

## Current state

**Nothing in this repository imports today.** No dependencies are installed and the repository
carries an unresolved architectural schism. This is known, recorded, and packetized — it is not a
surprise waiting for the next agent.

Read `STATE.md` for the current runtime truth. It is one screen.

## For an agent arriving here

Read three files, in this order:

1. **`AGENTS.md`** — the router. Project identity, surface map, source hierarchy, packet route,
   hard bans, doctrine.
2. **`STATE.md`** — what is true right now.
3. **`TASK.md`** — what to execute.

That is the cold-entry minimum. If it is not enough to start work, the router has failed and
repairing it is the first packet.

Claude Code operators additionally read `CLAUDE.md` for runtime specialization — substrate
availability, subagent lanes, and a hazard about subagent write access.

## Document map

| Surface | Answers |
|---|---|
| `AGENTS.md` | How do I operate here? |
| `CLAUDE.md` | What is different when I am Claude Code? |
| `STATE.md` | Does anything work right now? |
| `TASK.md` | What do I execute? |
| `SPEC.md` | What is the plugin contract? |
| `HOST_BOUNDARY.md` | What must the embedding system supply? |
| `OPSEC.md` | What is the security posture, and what only pretends to be? |
| `AUTHORITY_MAP.md` | Which surface owns this claim, and where do surfaces contradict? |
| `CONTEXT.md` | What happened, indexed by date and key? |
| `MEMORY.md` | Why is it this way? |
| `NOTEPAD.md` | What did the last session actually do? |
| `workflows.md` | How do I compose tools here? |
| `docs/ARCHITECTURE.md` | How is it wired? |
| `docs/DEFECT_INDEX.md` | What is verifiably broken? |
| `filetree.md` | Where is everything? |
| `gate.sh` | Is my change acceptable? |

## Validation

```bash
bash gate.sh
```

The gate is honest by construction. It reports `NOT RUN` where a prerequisite is absent rather
than passing vacuously. **A `NOT RUN` is not a pass.**

There is no test suite, by design. Validation in this repository is experimentation, not pytest.
See `AGENTS.md` section 7.

## Getting it running

Not yet possible. Execute `packets/PACKET-001-dependency-and-import-truth.md` — it creates the
environment and establishes what actually fails, replacing this control plane's predicted claims
with observed tracebacks.
