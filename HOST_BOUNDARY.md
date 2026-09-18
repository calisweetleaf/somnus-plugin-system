# HOST BOUNDARY — What the Embedding System Must Supply

> **Normative.** This document owns the contract between somnus-plugin-system and whatever
> larger system embeds it.
>
> **This is the most misread surface in the repository.** Three imports in this codebase do not
> resolve here. They are **not broken imports.** They are the seam where this plugin substrate
> attaches to a host. An agent that "fixes" them by vendoring stubs, writing mock modules, or
> deleting the import lines has destroyed the cross-ecosystem contract that is the entire
> purpose of this repository.
>
> Operator ruling, 2026-09-05: this package is designed to be embedded inside larger Somnus
> systems. It will not be a standalone distribution. Declare the boundary; do not resolve it.

---

## 1. The contract — 3 modules, 7 symbols, 6 import sites

### `core.memory_core` — realized as `host_protocols` Protocol declarations

| Symbol | Kind | Consumed at |
|---|---|---|
| `MemoryManager` | Protocol | `plugin_base.py`, `plugin_manager.py`, `hot_reload.py` |
| `MemoryType` | enum vocabulary | same |
| `MemoryImportance` | enum vocabulary | same |
| `MemoryScope` | enum vocabulary | `plugin_base.py` |

Import sites (LIVE, PACKET-003 strategy 1):
- `plugin_base.py` — `from host_protocols import MemoryManager, MemoryType, MemoryImportance, MemoryScope, ...`
- `plugin_manager.py` — `from host_protocols import MemoryManager, SecurityEnforcer`
- `hot_reload.py` — `from host_protocols import MemoryManager, MemoryType, MemoryImportance`

**Required behavior.** `MemoryManager` must provide, at minimum:

| Method | Called at | Purpose |
|---|---|---|
| `create_context(...)` | `plugin_base.py:274-279` | Establishes the plugin's memory context during `initialize()` |
| `store_memory(...)` | `plugin_base.py:444-446` (checkpointing), `plugin_manager.py:248-262` | Persists plugin state and plugin-namespaced data |
| `retrieve_memory(...)` | `plugin_manager.py:264-282` | Reads plugin-namespaced data |

`MemoryType` must expose at least `USER`. `MemoryScope` must expose at least `USER`.

> **Drift warning.** `plugin_base.py:444-446` carries an in-place hand-patch changing
> `MemoryType.SYSTEM` → `MemoryType.USER` and `MemoryScope.PLUGIN` → `MemoryScope.USER`, with
> the prior values still visible in the surrounding comments. The donor's memory API shifted
> underneath this code and the repair was not completed. A host supplying `SYSTEM` and `PLUGIN`
> variants would satisfy the original design; a host supplying only `USER` satisfies the current
> source. **Confirm which your host provides before relying on checkpoint scoping.** See
> `docs/DEFECT_INDEX.md` D-021.

Memory namespacing convention observed in the superseded lineage: `plugin:{plugin_id}`
(`plugin_manager.py:248-282`).

### `schemas.session` — realized as `host_protocols` type aliases

| Symbol | Kind | Consumed at |
|---|---|---|
| `SessionID` | type alias (`str`) | `plugin_base.py`, `plugin_manager.py` |
| `UserID` | type alias (`str`) | same |

**Required behavior.** Both are used as type annotations on `PluginContext`
(`plugin_base.py:55-56`): `session_id: SessionID`, `user_id: UserID`. Any type the host uses to
identify a session and a user satisfies this. There is no behavioral requirement beyond being
constructible and comparable.

### `core.security_layer` — realized as `host_protocols.SecurityEnforcer`

| Symbol | Kind | Consumed at |
|---|---|---|
| `SecurityEnforcer` | Protocol | `plugin_manager.py` |

**PACKET-002 ruling.** `SecurityEnforcer` **survives**. It is the host runtime-policy surface.
Static analysis authority is `security.SecurityManager`. `PluginSecurityManager` was deleted.
The enforcer is stored on `PluginManager` and is bound by PACKET-005's capability façade.
Do not vendor an implementation here.

---

## 2. What is NOT part of this boundary

These resolve inside this repository and must never be treated as host-supplied:

`plugin_base` · `plugin_manager` · `security` · `discovery` · `orchestration` · `hot_reload` ·
`marketplace`

These are ordinary third-party packages declared in `pyproject.toml`, not host responsibilities:

`pydantic` · `fastapi` · `aiofiles` · `aiohttp` · `watchdog` · `cryptography` · `semver` ·
`certifi` · `importlib_metadata`

**There is no `backend.*` import anywhere in this repository.** If you find one, it is new and
must be justified against this document.

---

## 3. Verification

The boundary is stable and enumerable, which means it is checkable. To confirm no new host
dependency has been introduced:

```bash
grep -rn '^from \(core\|schemas\|backend\)\.' *.py
grep -n '^from host_protocols import' plugin_base.py plugin_manager.py hot_reload.py
```

Expected: **zero** donor `core`/`schemas`/`backend` imports. The Protocol seam is
`from host_protocols import ...` at `plugin_base.py`, `plugin_manager.py`, and `hot_reload.py`.

**Any new donor import is a boundary expansion and requires an operator decision.** This check
runs in `gate.sh`.

---

## 4. Realization — chosen: Protocol declaration

**Chosen 2026-09-06, confirmed 2026-09-18.** Strategy 1: `host_protocols.py` declares
`typing.Protocol` contracts. The host's concrete classes structurally satisfy them. This
repository does not implement `MemoryManager` or `SecurityEnforcer`.

Rejected:

- **Host-supplied injection** — would remove the module-scope contract that hosts can type-check
  before constructing a manager.
- **Namespace package** (`core` / `schemas` on `sys.path`) — that is the donor layout, not this
  substrate's declared seam.

**Hard ban across all three:** no stub module that returns fake data, no `try/except ImportError`
fallback, no mock. Per operator doctrine, this repository has no fallbacks and no shims. If the
host is absent, the correct behavior is to fail, not to pretend.
