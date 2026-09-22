# PACKET-002 — Lineage Convergence

**Owner:** next executing agent, or `.claude/agents/lineage-convergence-surgeon`
**Status:** LANDED
**Depends on:** PACKET-001
**Size:** one session
**Priority:** high — this is the repository's defining defect

## Mission

Make `plugin_base.py` canonical in source, not only in ruling. This repository contains two rival
plugin lineages. `plugin_base.py` has four inbound consumers; `plugin_manager.py` has zero, yet
holds the only working loader and the only FastAPI mount. Absorb the mechanisms that only exist
in `plugin_manager.py` into the canonical lineage, delete the duplicate types, and resolve all
seven cross-module name collisions. When this lands, a plugin authored against `SPEC.md` must
actually load — today it is rejected by the loader's own `issubclass` gate.

## Required Reads

- `SPEC.md` — the whole document, especially section 1 (canonical authority) and section 7 (the
  loader hazard). This packet turns every PENDING-002 clause into LIVE.
- `MEMORY.md` entry `2026-09-05 — LINEAGE RULING: plugin_base.py IS CANONICAL` — the ruling, the
  evidence, and the rejected alternatives
- `MEMORY.md` entry `2026-09-05 — SEVEN NAME COLLISIONS ACROSS MODULES` — the collision table
- `AUTHORITY_MAP.md` sections 1 and 4
- `docs/IMPORT_TRUTH.md` — produced by PACKET-001. Do not start without it.
- `docs/ARCHITECTURE.md` — the class ownership map and both lifecycle diagrams
- `plugin_base.py` lines 26 to 137, and 230 to 566
- `plugin_manager.py` lines 52 to 145, and 668 to 809
- `security.py` lines 210 to 235, and 415 to 440, and 700 to 710 — the `PluginPermission` consumers
- `HOST_BOUNDARY.md` section 1, `core.security_layer` — the open question about `SecurityEnforcer`

## Invariant

- `plugin_base.py` is canonical. Every behavior that survives must be reachable from it.
- The four consumers keep working: `discovery.py:24`, `orchestration.py:20`, `security.py:34`,
  `marketplace.py:27`. Their imported symbol names must still resolve after the merge.
- No behavior is silently dropped. Anything deleted from `plugin_manager.py` is either
  reimplemented in the canonical lineage or explicitly recorded as removed, with the reason, in
  `MEMORY.md`.
- The host boundary is unchanged. This packet does not add, remove, or resolve a donor import.
- `PluginState` and `ResourceMonitor` are NOT resolved by deletion. Each names two genuinely
  different concepts and both must survive under distinct names.
- The plugin authoring contract in `SPEC.md` is the target. If the merge forces a contract change,
  `SPEC.md` changes in the same turn and the change is justified in `MEMORY.md`.

## Surfaces

Implementation:
- `plugin_base.py` — receives `PluginPermission`, `PluginType`, and narrows the `plugin_type` and
  `permissions` manifest fields to those enums
- `plugin_manager.py` — loses `PluginManifest` (88), `PluginBase` (147), `PluginDiscovery` (498),
  `PluginFileWatcher` (446), `PluginStatus` (52), and the always-true signature stub (426 to 430);
  its loader and FastAPI mount are re-based onto the canonical base class
- `hot_reload.py` — its `PluginState` (56) is renamed; suggested `PluginRuntimeSnapshot`
- `marketplace.py` — its `PluginStatus` (40) is renamed to reflect listing status, not lifecycle
- `orchestration.py` — its `ResourceMonitor` (105) is renamed to reflect workflow scope
- `security.py` — its `PluginPermission` import at line 34 now resolves; no other change expected

Evidence:
- `docs/DEFECT_INDEX.md` — D-022 (manifest schema drift) closed; note which other entries the
  merge incidentally closes
- `docs/ARCHITECTURE.md` — collision map and dependency graph regenerated

Continuity:
- `SPEC.md` — every PENDING-002 marker becomes LIVE with a real line number
- `AUTHORITY_MAP.md` — CONTRADICTION-01, 02, 03 marked resolved
- `OPSEC.md` — SEC-01 and SEC-10 marked resolved
- `MEMORY.md`, `CONTEXT.md`, `STATE.md`, `NOTEPAD.md`, `TASK.md`, `filetree.md`

## Hard Bans

- Do not keep both `PluginManifest` definitions "for compatibility". The duplication is the defect.
- Do not resolve the `PluginState` collision by deleting `hot_reload.py`'s version. It is a
  runtime snapshot dataclass, not a lifecycle enum. Rename it.
- Do not resolve the `ResourceMonitor` collision by deleting either. They are different scopes.
- Do not migrate to `src/`. The flat layout is intentional per operator ruling.
- Do not add a `try/except ImportError`, a stub, a shim, or a fallback anywhere.
- Do not vendor or stub `core.memory_core`, `schemas.session`, or `core.security_layer`.
- Do not delete `plugin_manager.py` wholesale. It holds the only loader. Absorb, then trim.
- Do not carry forward the signature verification stub at `plugin_manager.py:426-430` that always
  returns `True`. Delete it. See `OPSEC.md` SEC-10.
- Do not change the plugin authoring contract to make the merge easier without recording why.

## Validation

```bash
for m in plugin_base plugin_manager security discovery orchestration hot_reload marketplace; do
  echo "=== import $m ==="
  ./.venv/bin/python -c "import $m" 2>&1 | tail -20
done
grep -rn 'class PluginManifest\|class PluginBase\|class PluginDiscovery\|class PluginFileWatcher' *.py
grep -rn '^from \(core\|schemas\|backend\)\.' *.py
codegraph sync && codegraph callers PluginBase
bash gate.sh
```

Expected:

- `security.py` no longer fails on `PluginPermission`. It may still fail on the host boundary —
  that is correct and expected.
- `class PluginManifest`, `class PluginBase`, `class PluginDiscovery`, and `class PluginFileWatcher`
  each appear **exactly once** repository-wide.
- The host-boundary grep returns **exactly six lines**, unchanged from `HOST_BOUNDARY.md` section 3.
- `codegraph callers PluginBase` resolves to a single definition site.
- A plugin class subclassing `plugin_base.PluginBase` passes the loader's `issubclass` gate. Prove
  this with a scratch plugin outside `installed/`, then delete the scratch file — the real
  reference implementation is PACKET-004.

## Exit

Record in `NOTEPAD.md`:

- Commit hash, files changed
- Verbatim output of all five validation commands
- For each of the 7 collisions: the resolution taken and the surviving name
- For each symbol removed from `plugin_manager.py`: reimplemented where, or removed why
- The ruling on `core.security_layer` / `SecurityEnforcer` — kept or dropped, and why
- The ruling on `PluginSecurityManager` (`plugin_manager.py:334`) versus `security.py`'s
  `SecurityManager` (609)
- Which `docs/DEFECT_INDEX.md` entries closed

## Handoff

Execute PACKET-003 next if the host boundary strategy is still unchosen, otherwise PACKET-004 to
build the reference plugin against the now-live contract.

Hazards: the loader `issubclass` gate at `plugin_manager.py:701` is the load-bearing edge. If it
is re-based incorrectly, every plugin silently fails to load with only a log line. Prove the gate
works before closing this packet.
