# File Tree — somnus-plugin-system

**Generated:** 2026-09-18
**Root:** somnus-plugin-system
**Base commit:** `82dab8d` → authority convergence (`cursor/plugin-runtime-heartbeat-863f`)

> **Whole-codebase awareness, not dispatch.** Consult this when regaining orientation, after a
> focused read sequence, or after structural change. **Do not route the active task from it** —
> route from `AGENTS.md` and `TASK.md`. **Do not infer ownership or authority from directory
> position.** Refresh after adds, moves, deletions, or ownership reshaping.

```
somnus-plugin-system/
│
├── AGENTS.md                  ROUTER — cognitive bootstrap, surface map, doctrine, hard bans
├── CLAUDE.md                  Claude Code runtime specialization; defers to AGENTS.md
├── README.md                  Narrative anchor
│
├── SPEC.md                    NORMATIVE — the adjudicated plugin contract (32-field manifest)
├── HOST_BOUNDARY.md           NORMATIVE — what the embedding system must supply
├── OPSEC.md                   NORMATIVE — trust boundary and security posture
├── AUTHORITY_MAP.md           Surface classification + contradictions register
│
├── STATE.md                   CURRENT — single-screen runtime truth
├── TASK.md                    CURRENT — packet board
├── CONTEXT.md                 Dated traversal index into MEMORY.md
├── MEMORY.md                  Durable decisions, stable vocabulary, negative knowledge
├── NOTEPAD.md                 HISTORY — append-only log; never authority
├── workflows.md               Tool composition for this repository
├── filetree.md                This file — topology
│
├── pyproject.toml             Dependency contract (9 deps, no pins)
├── gate.sh                    Validation entrypoint — honest, reports NOT RUN
├── validate_system.py         Production validation harness (component vs E2E)
├── tools/state_probe.py       Mechanical STATE facts for gate.sh / STATE.md
├── python_production_doctor.py  Somnus diagnostic toolkit
│
├── host_protocols.py          HOST BOUNDARY — Protocol contracts for embedding system
├── host_capabilities.py       Object-capability façade + execution domains
├── plugin_worker.py           Isolated worker process + parent handle
├── plugin_lifecycle.py        Zip-safe install, generations, host-route descriptors
├── plugin_base.py             CANONICAL — manifest, lifecycle, exported actions
├── plugin_manager.py          LOADER — façade assembly, domain-aware load
├── security.py        914 L   Trust boundary: AST analysis, sandbox, crypto validation
├── discovery.py       824 L   Discovery, dependency graph, topological resolution
├── orchestration.py   734 L   Priority-queued async dispatch, workflow interpretation
├── hot_reload.py      834 L   Development reload with state preservation
├── marketplace.py     845 L   Distribution, trust scoring, installation
├── __init__.py          0 L   Empty. Flat layout is intentional — see HOST_BOUNDARY.md
│
├── docs/
│   ├── ARCHITECTURE.md        Wiring diagrams (Mermaid): lineages, collisions, lifecycles
│   └── DEFECT_INDEX.md        EVIDENCE — 22 verified defects, D-001..D-022
│
├── packets/
│   ├── PACKET-001-dependency-and-import-truth.md    LANDED
│   ├── PACKET-002-lineage-convergence.md            LANDED
│   ├── PACKET-003-host-boundary-realization.md      LANDED
│   ├── PACKET-004-reference-plugin.md               LANDED
│   ├── PACKET-005-execution-boundary.md             LANDED
│   ├── PACKET-006-transactional-lifecycle.md        LANDED
│   └── PACKET-007-truth-harness.md                  LANDED
│
├── .claude/
│   ├── settings.json                        Permissions derived from THIS layout
│   └── agents/
│       ├── lineage-convergence-surgeon.md   Executes PACKET-002
│       ├── plugin-contract-auditor.md       Read-only SPEC.md conformance audit
│       └── host-boundary-validator.md       Read-only donor-seam guard
│
├── installed/                 Plugin installation root
│   ├── example_plugin/        LIVE reference — plugin_base.PluginBase, id example_plugin_1.0.0
│   │   ├── manifest.json      0 B      → PACKET-004 populates this
│   │   ├── plugin.py          0 B
│   │   ├── __init__.py        0 B
│   │   ├── requirements.txt   0 B
│   │   ├── agents/            actions.py, __init__.py — both 0 B; no loader reads this dir
│   │   ├── api/               routes.py, models.py, __init__.py — 0 B; loader reads __init__ only
│   │   ├── workflows/         nodes.py, __init__.py — 0 B; no loader reads this dir
│   │   ├── memory/            __init__.py 0 B; `extensions` is a 0-B FILE (was a dir in donor)
│   │   └── assets/            __init__.py 0 B
│   ├── community/             experimental/ featured/ verified/ — all empty
│   ├── sandbox/untrusted/     empty
│   └── templates/             agent_action/ api_extension/ basic_plugin/
│                              ui_component/ workflow_node/ — all empty
│
├── test/
│   ├── harness_plugins/       verified_probe, isolated_probe, isolated_crash
│   └── system/
│       └── runs/                  Timestamped validation harness results
│           └── <timestamp>/       result.json, result.md per run
│
└── (no foreign artifacts — the 2026-09-05 scaffolding was deleted; see AUTHORITY_MAP.md §6)
```

## Not tracked

`.venv/` · `.git/` · `.remember/` · `__pycache__/` · `.codegraph/`

## Structural facts worth knowing before you navigate

- **The 7 modules are flat at root by operator ruling.** This package is embedded inside larger
  Somnus systems, not distributed standalone. There is no `src/` and there will not be.
- **`installed/example_plugin/` is not an example.** Every file is 0 bytes. The former `TODO.md`
  claimed otherwise; that claim was disproven and the file deleted.
- **`installed/templates/` and `installed/community/` assert a taxonomy no code reads.** They are
  empty directories.
- **There is no `tests/` directory and no test suite**, by design. Validation here is
  experimentation, not pytest.
- **Directory position implies nothing about authority.** Use `AUTHORITY_MAP.md`.
