# PACKET-005 — Execution Boundary

**Owner:** next executing agent
**Status:** LANDED
**Depends on:** PACKET-002, PACKET-004
**Size:** one session
**Priority:** high — permissions must become policy

## Mission

Replace ambient in-process host authority with a capability-scoped host façade and
graduated execution domains. Trusted native plugins stay host-integrated. Verified
extensions receive narrower objects. Untrusted plugins execute in a worker process
whose import never enters the host interpreter. Exported actions become the only
invocation namespace.

## Required Reads

- `SPEC.md` sections 4 and 7
- `OPSEC.md` residual after SEC-01/SEC-10
- `plugin_base.py` `PluginBase.__init__`, `PluginPermission`
- `plugin_manager.py` `load_plugin`, `_load_plugin_module`
- `orchestration.py` `execute_plugin_method`
- `security.py` `SandboxEnvironment`, `create_sandbox`

## Invariant

- No plugin receives a raw ambient `MemoryManager`.
- Missing permission is absence of the object, not a flag.
- `HOST_INTEGRATED` / `VERIFIED` timeouts cancel the await and record `NOT TERMINABLE`.
- `ISOLATED` timeouts terminate the worker.
- Host protocols stay contracts. No vendored host implementation.

## Surfaces

- `host_capabilities.py` — new
- `plugin_worker.py` — new
- `plugin_base.py` — façade + exported actions
- `plugin_manager.py` — domain selection at load
- `orchestration.py` — action registry, kwargs, honest timeout, CPU window
- `SPEC.md`, `OPSEC.md`, continuity surfaces

## Hard Bans

- Do not isolate every plugin.
- Do not use `importlib.reload`.
- Do not pretend a thread timeout killed the function.
- Do not enable the marketplace network path.

## Validation

```bash
./.venv/bin/python validate_system.py
bash gate.sh
```

Expected: production path still PASS; new domain/capability checks PASS; denied
WRITE_MEMORY fails; isolated timeout kills the worker.

## Exit

Record checkpoint ids, domain assignments, and whether the isolated worker died
on timeout. Mark PACKET-005 landed.

## Handoff

Execute PACKET-006 next.
