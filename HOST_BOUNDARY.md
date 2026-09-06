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

### `core.memory_core`

| Symbol | Kind | Consumed at |
|---|---|---|
| `MemoryManager` | class | `plugin_base.py:22`, `plugin_manager.py:46`, `hot_reload.py:34` |
| `MemoryType` | enum | same |
| `MemoryImportance` | enum | same |
| `MemoryScope` | enum | `plugin_base.py:22` only |

Import sites:
- `plugin_base.py:22` — `from core.memory_core import MemoryManager, MemoryType, MemoryImportance, MemoryScope`
- `plugin_manager.py:46` — `from core.memory_core import MemoryManager, MemoryType, MemoryImportance`
- `hot_reload.py:34` — `from core.memory_core import MemoryManager, MemoryType, MemoryImportance`

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

### `schemas.session`

| Symbol | Kind | Consumed at |
|---|---|---|
| `SessionID` | type | `plugin_base.py:23`, `plugin_manager.py:45` |
| `UserID` | type | same |

Import sites:
- `plugin_base.py:23` — `from schemas.session import SessionID, UserID`
- `plugin_manager.py:45` — `from schemas.session import SessionID, UserID`

**Required behavior.** Both are used as type annotations on `PluginContext`
(`plugin_base.py:55-56`): `session_id: SessionID`, `user_id: UserID`. Any type the host uses to
identify a session and a user satisfies this. There is no behavioral requirement beyond being
constructible and comparable.

### `core.security_layer`

| Symbol | Kind | Consumed at |
|---|---|---|
| `SecurityEnforcer` | class | `plugin_manager.py:47` |

Import site:
- `plugin_manager.py:47` — `from core.security_layer import SecurityEnforcer`

**Required behavior.** Consumed only by the superseded lineage. `packets/PACKET-002` must decide
whether this dependency survives the convergence, given that `security.py:609`'s
`SecurityManager` and `plugin_manager.py:334`'s `PluginSecurityManager` already overlap it in
role. **Do not implement a host `SecurityEnforcer` until PACKET-002 rules on it.**

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
```

Expected output is exactly six lines: `plugin_base.py:22`, `plugin_base.py:23`,
`plugin_manager.py:45`, `plugin_manager.py:46`, `plugin_manager.py:47`, `hot_reload.py:34`.

**Any additional line is a boundary expansion and requires an operator decision.** This check
runs in `gate.sh`.

---

## 4. Realization strategies

`packets/PACKET-003-host-boundary-realization.md` owns this work. The strategy is not yet
chosen. Recorded options, with the constraint that none may become a permanent stub:

1. **Protocol declaration.** Define `typing.Protocol` interfaces in this repository that the
   host's concrete classes structurally satisfy. Keeps the contract checkable without importing
   a host implementation. No runtime shim.
2. **Host-supplied injection.** The embedding system passes concrete instances at
   `initialize_plugin_system(...)` (`plugin_manager.py:1024`) rather than the modules being
   imported at module scope. Removes the import-time coupling entirely.
3. **Namespace package.** The host provides real `core` and `schemas` packages on the path.
   This is what the donor `somnus-os` did and what these imports were written against.

**Hard ban across all three:** no stub module that returns fake data, no `try/except ImportError`
fallback, no mock. Per operator doctrine, this repository has no fallbacks and no shims. If the
host is absent, the correct behavior is to fail, not to pretend.
