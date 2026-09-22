# SPEC — The Plugin Contract

> **Normative.** This document owns the plugin authoring contract for somnus-plugin-system.
> When source and this document disagree, source wins and this document is repaired in the
> same turn. When two source modules disagree, this document names which one is canonical.
>
> Adjudicated 2026-09-05 by operator ruling. Evidence in `MEMORY.md` →
> `2026-09-05 — LINEAGE RULING: plugin_base.py IS CANONICAL`.

---

## 0. Status of this contract

This specification describes the contract that source implements. Clauses are marked:

- **LIVE** — implemented in source now.

Lineage convergence has landed. Author against `plugin_base.PluginBase` with a class named
`Plugin`. The worked example is `installed/example_plugin/` (`somnus_reference`).

---

## 1. Canonical authority

| Concern | Canonical surface | Status |
|---|---|---|
| Manifest schema | `plugin_base.PluginManifest` (pydantic `BaseModel`) | LIVE |
| Capability taxonomy | `plugin_base.PluginCapability` | LIVE |
| Lifecycle states | `plugin_base.PluginState` | LIVE |
| Runtime context | `plugin_base.PluginContext` | LIVE |
| Runtime metrics | `plugin_base.PluginMetrics` | LIVE |
| Base class | `plugin_base.PluginBase` | LIVE |
| Permission taxonomy | `plugin_base.PluginPermission` | LIVE |
| Type taxonomy | `plugin_base.PluginType` | LIVE |
| Loader | `plugin_manager.PluginManager.load_plugin` | LIVE |
| API mounting | `plugin_manager.PluginManager._register_plugin_api` | LIVE |

The rival `PluginManifest`, `PluginBase`, `PluginDiscovery`, and `PluginFileWatcher` that used
to live in `plugin_manager.py` are deleted. `hot_reload` names its snapshot
`PluginRuntimeSnapshot`. Marketplace listing state is `ListingStatus`. The orchestrator's
monitor is `ExecutionResourceMonitor`.

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
| `plugin_type` | `PluginType` | — |

`plugin_type` is `plugin_base.PluginType`. A string that is not one of the eight enum values
fails validation.

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
| `permissions` | `List[PluginPermission]` | `[]` | eight closed values | — |
| `trusted` | `bool` | `False` | — | 102 |
| `signature` | `Optional[str]` | `None` | — | 103 |
| `security_level` | `int` | `1` | `ge=1, le=5` | 104 |

`permissions` is `List[PluginPermission]`. `security.py` consumes the enum. `trusted` is a
self-assertion and does not skip signature verification.

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

`plugin_base.PluginPermission`. **LIVE.** Eight values.

`read_memory` · `write_memory` · `network_access` · `file_system` · `system_commands` ·
`user_interface` · `session_access` · `agent_control`

## 5. Type taxonomy — `PluginType`

`plugin_base.PluginType`. **LIVE.** It is the type of the `plugin_type` manifest field. Eight values.

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

Checkpoints persist through `memory_manager.store_memory(...)` as `MemoryType.USER` and
`MemoryScope.USER`. That classification is the checkpoint contract. D-021 is closed.

### Consciousness and network interfaces

`PluginBase` implements `ConsciousnessInterface` and `NetworkInterface`. Consciousness methods
are `consciousness_sync`, `quantum_coherence_check`, `recursive_depth_analysis`,
`enter_recursive_frame`, and `leave_recursive_frame`. Network methods are `network_request`,
`websocket_connect`, and `p2p_communicate`. `network_request` and `websocket_connect` require
`PluginPermission.NETWORK_ACCESS` and speak http(s) or ws(s). `p2p_communicate` delivers to
another loaded plugin in-process and requires the same permission. D-020 is closed.

---

## 7. Loader contract — read this before authoring

`plugin_manager.PluginManager.load_plugin`. **LIVE.** It constructs `plugin_base.PluginManifest`
and accepts `plugin_base.PluginBase`.

### Plugin module

`_load_plugin_module` (`:730-761`) uses `importlib.util.spec_from_file_location` against
`plugin.py`. The module **must** expose a module-level class named exactly `Plugin`:

```python
plugin_class = getattr(plugin_module, 'Plugin', None)          # plugin_manager.py:700
if not plugin_class or not issubclass(plugin_class, PluginBase):  # :701
    return False
plugin_instance = plugin_class(plugin_id, manifest, self.memory_manager)  # :706
```

The `issubclass` check resolves `PluginBase` to `plugin_base.PluginBase`. A plugin authored
against this specification is what the loader accepts.

Construction is three positional arguments: `(plugin_id, manifest, memory_manager)`.
`PluginBase.__init__` accepts a fourth, `consciousness_level=0.0`, defaulted — so the
three-argument call site remains compatible.

### API extension

`_register_plugin_api` imports **`api/__init__.py`** — **not** `api/routes.py` —
and expects a module attribute named `router`. Each route is bound to the loaded instance
through a per-route closure. The wrapper's public signature omits `plugin_instance`, and
FastAPI therefore does not require the client to send it. The router is mounted at
`/api/plugins/{plugin_id}`.

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

Discovery indexes a plugin by `manifest.name` and reads `manifest.json` per subdirectory.
`somnus_reference` is the id of the reference plugin, not `somnus_reference_1.0.0`.

`installed/example_plugin/` is that reference. Its manifest validates, `class Plugin` subclasses
`plugin_base.PluginBase`, and `api/__init__.py` exports `router`. `memory/extensions/` is a
directory. Load proof: `experiments/prove_reference_plugin.py`.

---

## 9. What this contract does not cover

- **Scheduling, distribution, and hot reload internals.** Those modules are part of the
  substrate. Their defect register is closed; see `docs/DEFECT_INDEX.md`. They are not required
  reading for authoring a plugin.
- **Host-supplied types.** `MemoryManager`, `MemoryType`, `MemoryImportance`, `MemoryScope`,
  `SessionID`, `UserID`, `SecurityEnforcer` are the embedding system's. See `HOST_BOUNDARY.md`.
  This repository satisfies them with protocols in `host_protocols.py`. Do not vendor replacements.
- **Trust and signing.** See `OPSEC.md`. A signature is `rsa_pss_sha256:<hex>` over the canonical
  tree with the signature field excluded. The marketplace network path stays off unless configured.
