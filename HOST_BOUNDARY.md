# HOST BOUNDARY — What the Embedding System Must Supply

> **Normative.** This document owns the contract between somnus-plugin-system and whatever
> larger system embeds it.
>
> **This is the most misread surface in the repository.** The embedding seam is
> `host_protocols.py` (PACKET-003 strategy 1). Donor `from core.*` / `from schemas.*`
> imports are gone. An agent that "fixes" the seam by vendoring stubs, writing
> mock modules, adding `try/except ImportError`, or reintroducing `from core.*`
> has destroyed the cross-ecosystem contract that is the entire purpose of this
> repository.
>
> Operator ruling, 2026-09-05: this package is designed to be embedded inside larger Somnus
> systems. It will not be a standalone distribution. Declare the boundary as Protocols;
> do not vendor host implementations here.

---

## 1. The contract — 3 donor modules realized as 7 Protocol/enum/alias symbols

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
| `create_context(...)` | `PluginBase.initialize` | Establishes the plugin's memory context |
| `store_memory(...)` | façade / `framework_store_memory` during checkpoint | Persists plugin-owned canonical state |
| `retrieve_memories(...)` | `PluginBase.restore_checkpoint` | Reads checkpoint rows by id |

`MemoryType` must expose at least `USER`. `MemoryScope` must expose at least `USER`.

> **Checkpoint scoping.** Live checkpoint writes use `MemoryType.USER` /
> `MemoryScope.USER`. The Protocol vocabulary still includes `SYSTEM` and
> `PLUGIN`. Confirm which your host provides before relying on those variants.
> See `docs/DEFECT_INDEX.md` D-021.

Memory namespacing convention: `plugin:{plugin_id}`. The host `MemoryManager` is
held by `PluginManager` and handed to `HostCapabilityFacade`; plugins never
receive the raw manager.

### `schemas.session` — realized as `host_protocols` type aliases

| Symbol | Kind | Consumed at |
|---|---|---|
| `SessionID` | type alias (`str`) | `plugin_base.PluginContext` |
| `UserID` | type alias (`str`) | `plugin_base.PluginContext` |

**Required behavior.** Both are used as type annotations on `PluginContext`
(`session_id: SessionID`, `user_id: UserID`). Any type the host uses to
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
