# File Tree — somnus-plugin-system

**Generated:** 2026-09-22
**Root:** somnus-plugin-system
**Base commit:** `7a7be24` plus the defect-closure working tree

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
├── validate_system.py         Production validation harness (15 checks)
├── python_production_doctor.py  Somnus diagnostic toolkit
│
├── host_protocols.py          HOST BOUNDARY — Protocol contracts for embedding system
├── plugin_base.py             CANONICAL — manifest, capabilities, lifecycle, consciousness, network
├── plugin_manager.py          Loader, FastAPI mount, publisher signature check
├── security.py                Trust boundary: AST analysis, sandbox, safe_extract_zip
├── discovery.py               Discovery, dependency graph, watcher drain on stop
├── orchestration.py           Priority dispatch, workflows, manifest admission
├── hot_reload.py              Development reload. Snapshot type is PluginRuntimeSnapshot
├── marketplace.py             Distribution. Network off. Local registry. RSA-PSS trust
├── __init__.py          0 L   Empty. Flat layout is intentional — see HOST_BOUNDARY.md
│
├── docs/
│   ├── ARCHITECTURE.md        Wiring diagrams (Mermaid): lineages, collisions, lifecycles
│   └── DEFECT_INDEX.md        EVIDENCE — D-001..D-022 closed 2026-09-22; original mechanisms preserved
│
├── packets/
│   ├── PACKET-001-dependency-and-import-truth.md    LANDED
│   ├── PACKET-002-lineage-convergence.md            LANDED
│   ├── PACKET-003-host-boundary-realization.md      LANDED
│   └── PACKET-004-reference-plugin.md               LANDED
│
├── .claude/
│   ├── settings.json                        Permissions derived from THIS layout
│   └── agents/
│       ├── lineage-convergence-surgeon.md   Executes PACKET-002
│       ├── plugin-contract-auditor.md       Read-only SPEC.md conformance audit
│       └── host-boundary-validator.md       Read-only donor-seam guard
│
├── installed/                 Plugin installation root
│   ├── example_plugin/        REFERENCE — somnus_reference, canonical PluginBase, mounted API
│   │   ├── manifest.json
│   │   ├── plugin.py          class Plugin(plugin_base.PluginBase)
│   │   ├── api/               __init__.py exports router; routes.py; models.py
│   │   ├── agents/            action catalog loaded by plugin.py
│   │   ├── workflows/         node descriptors loaded by plugin.py
│   │   ├── memory/extensions/ directory — user_checkpoint classification
│   │   └── assets/contract.md
│   ├── community/             experimental/ featured/ verified/ — all empty
│   ├── sandbox/untrusted/     empty
│   └── templates/             agent_action/ api_extension/ basic_plugin/
│                              ui_component/ workflow_node/ — all empty
│
├── experiments/
│   ├── prove_defect_closure.py     D-001..D-022 runtime proof
│   ├── prove_reference_plugin.py   somnus_reference load and route proof
│   └── reports/                    JSON and Markdown artifacts from those proofs
│
├── test/
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
- **`installed/example_plugin/` is the reference plugin `somnus_reference`.** It loads through
  `PluginManager` and mounts `/contract`, `/lifecycle`, and `/checkpoint`.
- **`installed/templates/` and `installed/community/` assert a taxonomy no code reads.** They are
  empty directories.
- **There is no `tests/` directory and no test suite**, by design. Validation here is
  experimentation, not pytest.
- **Directory position implies nothing about authority.** Use `AUTHORITY_MAP.md`.
