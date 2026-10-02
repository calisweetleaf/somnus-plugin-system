# SPEC — The Plugin Contract

> **Normative.** This document owns the plugin authoring contract for somnus-plugin-system.
> When source and this document disagree, source wins and this document is repaired in the
> same turn. When two source modules disagree, this document names which one is canonical.
>
> Adjudicated 2026-09-05 by operator ruling. Evidence in `MEMORY.md` →
> `2026-09-05 — LINEAGE RULING: plugin_base.py IS CANONICAL`.

---

## 0. Status of this contract

This specification describes the **live** contract through PACKET-007.

- **LIVE** — implemented in source now, at the cited surface.
The contract is live through PACKET-007. Host embedding is the remaining work.

An agent authoring a plugin **today** subclasses `plugin_base.PluginBase`, implements the
four `_plugin_*` hooks, declares `agent_actions`, and loads through
`PluginManager.load_plugin()`. The third constructor argument is a
`HostCapabilityFacade`, not a raw host `MemoryManager`. Permissions are
object-capability policy.

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
| Plugin identity | `plugin_base.plugin_identity(name, version)` → `{name}_{version}` | LIVE |
| Discovery | `discovery.PluginDiscovery` | LIVE |
| Static security | `security.SecurityManager` | LIVE |
| Loader | `plugin_manager.PluginManager.load_plugin` | LIVE |
| API mounting | Host route `/api/plugins/{plugin_id}/{path:path}` | LIVE |
| Install | `marketplace.PluginInstaller.install_from_archive` zip-safe + staged | LIVE |
| Reload | Blue/green `PluginManager.reload_plugin` | LIVE |
| Reference plugin | `installed/example_plugin/` | LIVE |
| Capability façade | `host_capabilities.HostCapabilityFacade` | LIVE |
| Execution domain | `host_capabilities.select_execution_domain` | LIVE |
| Isolated worker | `plugin_worker.IsolatedPluginHandle` | LIVE |
| Exported actions | `plugin_base.ExportedAction` | LIVE |

**Deleted by PACKET-002:** manager-local `PluginManifest`, `PluginBase`, `PluginDiscovery`,
`PluginFileWatcher`, `PluginStatus`, `PluginPermission`, `PluginType`, `PluginSecurityManager`.

---

## 2. Manifest schema — 32 fields

Source of truth: `plugin_base.PluginManifest` (`plugin_base.py`, class body).
Loaded via `PluginManifest.from_file()`, which delegates to pydantic
`cls(**data)` — **malformed input raises**. This is the opposite tolerance
posture from the superseded dataclass manifest, which hand-parsed with `.get()`
defaults and silently accepted anything. Cite symbols, not frozen line numbers.

### Required — 5 fields, no defaults

| Field | Type | Line |
|---|---|---|
| `name` | `str` | 444 |
| `version` | `str` | 445 |
| `description` | `str` | 446 |
| `author` | `str` | 447 |
| `plugin_type` | `PluginType` | 448 |

`plugin_type` is `PluginType`. `permissions` is `List[PluginPermission]`. Malformed values raise.

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
| `permissions` | `List[PluginPermission]` | `[]` | — | 460 |
| `trusted` | `bool` | `False` | — | 102 |
| `signature` | `Optional[str]` | `None` | — | 103 |
| `security_level` | `int` | `1` | `ge=1, le=5` | 104 |

**LIVE.** `permissions` is `List[PluginPermission]`. The loader assembles a
`HostCapabilityFacade` from this list. A missing permission is the **absence of
the capability object**, not a flag the plugin is trusted to honor.

Domain selection (`host_capabilities.select_execution_domain`):

- `trusted=True` or `security_level <= 2` → `HOST_INTEGRATED`
- `security_level >= 4` and not trusted → `ISOLATED`
- otherwise → `VERIFIED`

`HOST_INTEGRATED` and `VERIFIED` stay in-process. `ISOLATED` imports `plugin.py`
only inside `plugin_worker.worker_entry`. All three receive a façade. None
receive a raw ambient `MemoryManager`.

### Integration points — 5 fields

| Field | Type | Default | Line |
|---|---|---|---|
| `api_endpoints` | `List[str]` | `[]` | 107 |
| `ui_components` | `List[str]` | `[]` | 108 |
| `agent_actions` | `List[str]` | `[]` | 109 |
| `workflow_nodes` | `List[str]` | `[]` | 110 |
| `memory_extensions` | `List[str]` | `[]` | 111 |

`agent_actions` is the invocation allow-list. `PluginBase` binds declared names
to handlers at construction. `orchestration.PluginExecutor.execute_plugin_method`
dispatches only registered actions — `initialize`, `_plugin_*`, and other
lifecycle methods are refused. API endpoint descriptors register into the generation table. The host owns
`/api/plugins/{plugin_id}/{path:path}` permanently. Generation swing changes
the dispatcher, not the FastAPI graph.

### Resource requirements — 4 fields

| Field | Type | Default | Constraint | Line |
|---|---|---|---|---|
| `memory_limit_mb` | `int` | `512` | `ge=1, le=8192` | 114 |
| `cpu_limit_percent` | `float` | `10.0` | `ge=0.1, le=100.0` | 115 |
| `network_access_required` | `bool` | `False` | — | 116 |
| `file_system_access` | `List[str]` | `[]` | — | 117 |

**Enforcement note:** orchestrator CPU is sampled over the request window
(`time.process_time()` / `time.monotonic()`), not `loop.time()` since process
start. In-process domains cannot kill a Python thread on timeout — they cancel
the await and record `NOT TERMINABLE`. Isolated timeouts terminate the worker.

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

`plugin_base.py`. **LIVE.** Eight values.

`read_memory` · `write_memory` · `network_access` · `file_system` · `system_commands` ·
`user_interface` · `session_access` · `agent_control`

## 5. Type taxonomy — `PluginType`

`plugin_base.py`. **LIVE.** Eight values. The `plugin_type` manifest field is this enum.

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

### State persistence — `PluginBase.get_state` / `checkpoint_state`. **LIVE.**

`get_state()` · `set_state()` · `checkpoint_state()` · `restore_checkpoint()`

Checkpoints persist through the façade's `framework_store_memory` (or
`store_memory` when `WRITE_MEMORY` is present). Canonical payload is
content-addressed; telemetry lives in the envelope. Live checkpoint writes use
`MemoryType.USER` / `MemoryScope.USER`. A host must supply at least those
variants. `MemoryType.SYSTEM` / `MemoryScope.PLUGIN` remain in the Protocol
vocabulary for other calls. See `docs/DEFECT_INDEX.md` D-021.

### Declared but unimplemented interfaces

`ConsciousnessInterface` and `NetworkInterface` are `@runtime_checkable`
Protocols on `plugin_base`. Nothing implements them. `PluginBase` inherits
`ABC` only; the other Protocols are structural, not bases. Do not assume a
plugin can rely on those interfaces.

---

## 7. Loader contract — read this before authoring

`plugin_manager.PluginManager.load_plugin`. **LIVE** on the canonical lineage.

Discovery keys plugins as `{name}_{version}` via `plugin_identity()`. The loader
`issubclass` gate resolves `PluginBase` to `plugin_base.PluginBase` for
in-process domains. Isolated plugins never enter host `exec_module`.

### Plugin module

In-process load uses `importlib.util.spec_from_file_location` against `plugin.py`.
The module **must** expose a module-level class named exactly `Plugin` that
subclasses `plugin_base.PluginBase`. Construction is:

```python
facade = HostCapabilityFacade(host_memory, security_enforcer, manifest, plugin_id)
plugin_instance = plugin_class(plugin_id, manifest, facade)
```

The third argument is the façade. Isolated load stages a copy into a
`SecurityManager.create_sandbox` tree and starts `IsolatedPluginHandle`.

`HOST_INTEGRATED` / `VERIFIED` timeouts cancel the await and record
`NOT TERMINABLE`. Isolated timeouts terminate the worker PID.

### API extension

`PluginManager._collect_plugin_endpoints` imports **`api/__init__.py`** — **not**
`api/routes.py` — and expects a module attribute named `router`. Endpoint
descriptors register into the generation table. The host owns
`/api/plugins/{plugin_id}/{path:path}` permanently via
`_mount_host_plugin_routes` / `dispatch_plugin_http`. Generation swing changes
the dispatcher, not the FastAPI graph. `include_router` on the manager is the
management API at `/api/plugins`, not a per-plugin mount.

**Unstated contract made explicit here:** if you split an API extension into `routes.py` and
`models.py`, `api/__init__.py` **must re-export `router`**. Nothing else in the tree is imported.

### Directories the loader never touches

`agents/`, `workflows/`, `memory/`, and `assets/` are **never referenced by any loader code
path.** `api_endpoints`, `ui_components`, `workflow_nodes`, and `memory_extensions`
remain reserved manifest fields. `agent_actions` is functional — it is the
exported-action allow-list bound by `PluginBase._bind_declared_actions`.

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

Discovery keys plugins as `plugin_identity(name, version)` and reads
`manifest.json` per subdirectory (`discovery.PluginDiscovery` / `PluginIndex`).

`installed/example_plugin/` is the live reference. Runtime id: `example_plugin_1.0.0`.
It subclasses `plugin_base.PluginBase`, exports `router` from `api/__init__.py`, and
loads through `PluginManager.load_plugin()`.

---

## 9. What this contract does not cover

- **Authoring against `hot_reload.py`.** Reload authority is
  `PluginManager.reload_plugin` (blue/green generations). `hot_reload.py` is a
  file-watch integration that schedules that path; it is not the production
  load path. Install authority is `marketplace.PluginInstaller.install_from_archive`.
  Dispatch authority is `orchestration.PluginExecutor.execute_plugin_method`
  (exported actions only). Remaining defects live in `docs/DEFECT_INDEX.md`.
- **Host-supplied types.** `MemoryManager`, `MemoryType`, `MemoryImportance`, `MemoryScope`,
  `SessionID`, `UserID`, `SecurityEnforcer` are the embedding system's. See `HOST_BOUNDARY.md`.
- **Trust and signing.** See `OPSEC.md`. Do not rely on `marketplace.py`'s signature path.
