# PACKET-006 — Transactional Lifecycle

**Owner:** next executing agent
**Status:** QUEUED
**Depends on:** PACKET-005
**Size:** one session
**Priority:** high — install/reload/routing must share one generation model

## Mission

Make install, reload, routing, and rollback one lifecycle authority. Safe archive
extraction, staged boot-probe, atomic promotion, blue/green generations, and a
stable host-owned plugin route.

## Required Reads

- `marketplace.py` `PluginInstaller`
- `hot_reload.py` `_hot_reload`, `PluginFileHandler`
- `plugin_manager.py` `_register_plugin_api`, `unload_plugin`
- `OPSEC.md` SEC-02 through SEC-05
- `discovery.py` `DependencyResolver`

## Invariant

- Zip members with `..`, absolute paths, or links are rejected before extract.
- Live generation N is never deleted before N+1 boot-probes successfully.
- Watchdog callbacks do not call `asyncio.create_task` on the observer thread.
- FastAPI owns `/api/plugins/{plugin_id}/{path:path}` permanently.

## Surfaces

- `marketplace.py`, `hot_reload.py`, `plugin_manager.py`, `SPEC.md`, `OPSEC.md`

## Hard Bans

- Do not `rmtree` a live install before the probe.
- Do not mutate `route.endpoint` after construction.
- Do not enable the marketplace network path.

## Validation

```bash
./.venv/bin/python validate_system.py
bash gate.sh
```

## Exit

Record staged-install and failed-N+1 proofs. Mark PACKET-006 landed.

## Handoff

Execute PACKET-007 next.
