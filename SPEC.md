# SPEC — The Plugin Contract

> **Normative.** This document owns the plugin authoring contract for somnus-plugin-system.
> When source and this document disagree, source wins and this document is repaired in the
> same turn. When two source modules disagree, this document names which one is canonical.
>
> Adjudicated 2026-09-05 by operator ruling. Evidence in `MEMORY.md` →
> `2026-09-05 — LINEAGE RULING: plugin_base.py IS CANONICAL`.

---

## 0. Status of this contract

This specification describes the **target** contract. Part of it is live in source today and
part of it lands in `packets/PACKET-002-lineage-convergence.md`. Every clause is marked:

- **LIVE** — implemented in source now, at the cited line.
- **PENDING-002** — ruled, specified, not yet in source. Do not assume it works.

An agent authoring a plugin **today** must read §7 before writing anything, because the only
working loader still gates against the superseded base class.

---

## 1. Canonical authority

| Concern | Canonical surface | Status |
|---|---|---|
| Manifest schema | `plugin_base.py:79` `PluginManifest` (pydantic `BaseModel`) | LIVE |
| Capability taxonomy | `plugin_base.py:28` `PluginCapability` | LIVE |
| Lifecycle states | `plugin_base.py:40` `PluginState` | LIVE |
| Runtime context | `plugin_base.py:53` `PluginContext` | LIVE |
| Runtime metrics | `plugin_base.py:67` `PluginMetrics` | LIVE |
| Base class | `plugin_base.py:230` `PluginBase` | LIVE |
| Permission taxonomy | `PluginPermission`, moving from `plugin_manager.py:75` into `plugin_base.py` | PENDING-002 |
| Type taxonomy | `PluginType`, moving from `plugin_manager.py:63` into `plugin_base.py` | PENDING-002 |
| Loader | `load_plugin`, moving from `plugin_manager.py:668` onto the canonical base | PENDING-002 |
| API mounting | `_register_plugin_api`, moving from `plugin_manager.py:763` | PENDING-002 |

**Superseded and scheduled for deletion in PACKET-002:** `plugin_manager.py`'s `PluginManifest`
(88), `PluginBase` (147), `PluginDiscovery` (498), `PluginFileWatcher` (446), `PluginStatus` (52).

---

## 2. Manifest schema — 32 fields

Source of truth: `plugin_base.py:79-136`. Loaded via `PluginManifest.from_file()` (`:126`),
which delegates to pydantic `cls(**data)` — **malformed input raises**. This is the opposite
tolerance posture from the superseded dataclass manifest, which hand-parsed with `.get()`
defaults and silently accepted anything.

### Required — 5 fields, no defaults

| Field | Type | Line |
|---|---|---|
| `name` | `str` | 81 |
| `version` | `str` | 82 |
| `description` | `str` | 83 |
| `author` | `str` | 84 |
| `plugin_type` | `str` | 85 |

**Known contract weakness:** `plugin_type` is typed as a bare `str` here, while the superseded
lineage typed it as the `PluginType` enum (`plugin_manager.py:66`). PACKET-002 narrows this
field to `PluginType`. Until then any string validates.

### Advanced capabilities — 4 fields

| Field | Type | Default | Constraint | Line |
|---|---|---|---|---|
| `capabilities` | `List[PluginCapability]` | `[]` | — | 88 |
| `consciousness_level_required` | `float` | `0.0` | `ge=0.0, le=1.0` | 89 |
| `recursive_depth_limit` | `int` | `10` | `ge=1, le=100` | 90 |
| `quantum_coherence_required` | `bool` | `False` | — | 91 |

### Dependencies and compatibility — 5 fields

| Field | Type | Default | Line |
|---|---|---|---|
| `morpheus_version_min` | `str` | `"1.0.0"` | 94 |
| `morpheus_version_max` | `str` | `"2.0.0"` | 95 |
| `python_version_min` | `str` | `"3.11"` | 96 |
| `dependencies` | `List[str]` | `[]` | 97 |
| `plugin_dependencies` | `List[str]` | `[]` | 98 |

### Security and permissions — 4 fields

| Field | Type | Default | Constraint | Line |
|---|---|---|---|---|
| `permissions` | `List[str]` | `[]` | — | 101 |
| `trusted` | `bool` | `False` | — | 102 |
| `signature` | `Optional[str]` | `None` | — | 103 |
| `security_level` | `int` | `1` | `ge=1, le=5` | 104 |

**PENDING-002:** `permissions` is narrowed from free-form `List[str]` to
`List[PluginPermission]`. `security.py` already consumes it as the enum (`:220`, `:223`,
`:226`, `:229`, `:419`, `:433`, `:703-705`) — the type is the thing that is missing, not the
intent.

### Integration points — 5 fields

| Field | Type | Default | Line |
|---|---|---|---|
| `api_endpoints` | `List[str]` | `[]` | 107 |
| `ui_components` | `List[str]` | `[]` | 108 |
| `agent_actions` | `List[str]` | `[]` | 109 |
| `workflow_nodes` | `List[str]` | `[]` | 110 |
| `memory_extensions` | `List[str]` | `[]` | 111 |

**These five fields are declared and read by no loader code path.** Repository-wide grep finds
only their declarations. See §6.

### Resource requirements — 4 fields

| Field | Type | Default | Constraint | Line |
|---|---|---|---|---|
| `memory_limit_mb` | `int` | `512` | `ge=1, le=8192` | 114 |
| `cpu_limit_percent` | `float` | `10.0` | `ge=0.1, le=100.0` | 115 |
| `network_access_required` | `bool` | `False` | — | 116 |
| `file_system_access` | `List[str]` | `[]` | — | 117 |

**Enforcement note:** `cpu_limit_percent` is currently unenforceable. `orchestration.py:635`
hardcodes CPU usage to `0.0`, so `ResourceMonitor.check_resource_limits` (`:124`) can never
trip its CPU branch (`:132`). See `docs/DEFECT_INDEX.md` D-011.

### Metadata — 5 fields

| Field | Type | Default | Line |
|---|---|---|---|
| `tags` | `List[str]` | `[]` | 120 |
| `license` | `str` | `"MIT"` | 121 |
| `homepage` | `Optional[str]` | `None` | 122 |
| `repository` | `Optional[str]` | `None` | 123 |
| `documentation` | `Optional[str]` | `None` | 124 |

---

## 3. Capability taxonomy — `PluginCapability`

`plugin_base.py:28-37`. **LIVE.** Eight values. This is a *different axis* from permissions:
capabilities describe what a plugin participates in; permissions describe what it is allowed to
touch. Do not conflate them.

| Value | Wire string |
|---|---|
| `MEMORY_INTEGRATION` | `memory_integration` |
| `CONSCIOUSNESS_ACCESS` | `consciousness_access` |
| `MULTI_AGENT_COORDINATION` | `multi_agent_coordination` |
| `RECURSIVE_PROCESSING` | `recursive_processing` |
| `REAL_TIME_ADAPTATION` | `real_time_adaptation` |
| `CROSS_SESSION_PERSISTENCE` | `cross_session_persistence` |
| `QUANTUM_COHERENCE` | `quantum_coherence` |
| `TEMPORAL_MANIPULATION` | `temporal_manipulation` |

## 4. Permission taxonomy — `PluginPermission`

Currently `plugin_manager.py:75-84`. **PENDING-002** — moves into `plugin_base.py`. Eight values.

`read_memory` · `write_memory` · `network_access` · `file_system` · `system_commands` ·
`user_interface` · `session_access` · `agent_control`

## 5. Type taxonomy — `PluginType`

Currently `plugin_manager.py:63-72`. **PENDING-002** — moves into `plugin_base.py` and becomes
the type of the `plugin_type` manifest field. Eight values.

`api_extension` · `ui_component` · `agent_action` · `memory_extension` · `workflow_node` ·
`tool_integration` · `research_module` · `creative_engine`

The `installed/templates/` directory asserts five of these as scaffold names
(`agent_action`, `api_extension`, `basic_plugin`, `ui_component`, `workflow_node`). Those
directories are currently empty.

---

## 6. Lifecycle contract

### States — `PluginState`, `plugin_base.py:40-49`. **LIVE.**

`INITIALIZING` → `READY` → `ACTIVE` → `PROCESSING` → `SUSPENDED` → `ERROR` → `TERMINATING` → `TERMINATED`

### Framework-provided transitions — `plugin_base.py:266-390`. **LIVE.**

`initialize()` · `activate()` · `deactivate()` · `cleanup()`

These wrap the author hooks and additionally perform: memory-context creation via
`MemoryManager.create_context()` (`:274-279`), consciousness-coherence synchronization
(`_synchronize_consciousness`, `:529-540`), resource-monitor start/stop, and event emission
(`_emit_event`, `:508-518`).

**Consciousness gate.** Activation is blocked when
`consciousness_level < manifest.consciousness_level_required` (`:313-316`). A plugin declaring
a non-zero `consciousness_level_required` will not activate in a host that does not supply a
matching level.

### Author-implemented hooks — `plugin_base.py:548-566`. **LIVE.** Four, all `@abstractmethod`, all `async`, all returning `bool`.

```python
async def _plugin_initialize(self) -> bool: ...
async def _plugin_activate(self)   -> bool: ...
async def _plugin_deactivate(self) -> bool: ...
async def _plugin_cleanup(self)    -> bool: ...
```

The underscore prefix is the canonical convention. The superseded lineage used public `on_*`
names with no cleanup hook. **Do not write `on_initialize`.**

### State persistence — `plugin_base.py:392-474`. **LIVE.**

`get_state()` · `set_state()` · `checkpoint_state()` · `restore_checkpoint()`

Checkpoints persist through `memory_manager.store_memory(...)`. Note `plugin_base.py:444-446`
carries an in-place hand-patch from `MemoryType.SYSTEM`/`MemoryScope.PLUGIN` to
`MemoryType.USER`/`MemoryScope.USER`, with the prior values still visible in comments —
evidence of an incomplete repair against a shifted donor API. See `docs/DEFECT_INDEX.md` D-021.

### Declared but unimplemented interfaces

`ConsciousnessInterface` (`plugin_base.py:168`) and `NetworkInterface` (`:211`) are declared
ABCs that nothing implements. `PluginBase` (`:230`) inherits only `PluginInterface`,
`StateInterface`, `ABC`. Do not assume a plugin can rely on them.

---

## 7. Loader contract — read this before authoring

Currently `plugin_manager.py:668-809`. **PENDING-002** for re-basing; the mechanism itself is
LIVE and is what actually loads plugins today.

### Plugin module

`_load_plugin_module` (`:730-761`) uses `importlib.util.spec_from_file_location` against
`plugin.py`. The module **must** expose a module-level class named exactly `Plugin`:

```python
plugin_class = getattr(plugin_module, 'Plugin', None)          # plugin_manager.py:700
if not plugin_class or not issubclass(plugin_class, PluginBase):  # :701
    return False
plugin_instance = plugin_class(plugin_id, manifest, self.memory_manager)  # :706
```

> **LOAD-BEARING HAZARD.** The `issubclass` check at `:701` resolves `PluginBase` to the
> **superseded** local class at `plugin_manager.py:147` — not the canonical
> `plugin_base.PluginBase` at `:230`. **A plugin authored against this specification is
> rejected by the current loader.** This is the single edge PACKET-002 exists to remove.
> Until it lands, authoring against §6 produces a plugin that validates and does not load.

Construction is three positional arguments: `(plugin_id, manifest, memory_manager)`. The
canonical `PluginBase.__init__` (`plugin_base.py:236-240`) accepts a fourth,
`consciousness_level=0.0`, defaulted — so the three-argument call site remains compatible.

### API extension

`_register_plugin_api` (`:763-809`) imports **`api/__init__.py`** — **not** `api/routes.py` —
and expects a module attribute named `router` (`:783`). Each route's endpoint is wrapped to
inject the plugin instance (`:791-796`) and mounted at `/api/plugins/{plugin_id}` (`:799-803`).

**Unstated contract made explicit here:** if you split an API extension into `routes.py` and
`models.py`, `api/__init__.py` **must re-export `router`**. Nothing else in the tree is imported.

### Directories the loader never touches

`agents/`, `workflows/`, `memory/`, and `assets/` are **never referenced by any loader code
path.** Repository-wide grep for those names, `actions.py`, and `nodes.py` returns a single hit
— `plugin_manager.py:766`, which is `api/__init__.py`.

The directory convention mirrors the manifest field names in §2 "Integration points", but
neither the directories nor those five manifest fields are read by anything today. They are
conventional, not functional. Treat them as reserved surface.

---

## 8. Plugin directory layout

```
<plugin_name>/
├── manifest.json          REQUIRED — validated against §2
├── plugin.py              REQUIRED — must define class Plugin(PluginBase)
├── requirements.txt        optional
├── api/
│   └── __init__.py         must export `router` if plugin_type is api_extension
├── agents/                 reserved — no loader reads this
├── workflows/              reserved — no loader reads this
├── memory/                 reserved — no loader reads this
└── assets/                 reserved — no loader reads this
```

Discovery keys plugins as `f"{name}_{version}"` and reads `manifest.json` per subdirectory
(`plugin_manager.py:498-564`).

`installed/example_plugin/` currently matches this layout with **every file at 0 bytes**. It is
a skeleton, not a reference. A real reference implementation lands in
`packets/PACKET-004-reference-plugin.md`.

---

## 9. What this contract does not cover

- **Runtime behavior of `orchestration.py`, `marketplace.py`, `hot_reload.py`.** Those modules
  are unreferenced by anything today and carry the defects registered in
  `docs/DEFECT_INDEX.md`. They are not part of the plugin authoring contract.
- **Host-supplied types.** `MemoryManager`, `MemoryType`, `MemoryImportance`, `MemoryScope`,
  `SessionID`, `UserID`, `SecurityEnforcer` are the embedding system's. See `HOST_BOUNDARY.md`.
- **Trust and signing.** See `OPSEC.md`. Do not rely on `marketplace.py`'s signature path.
