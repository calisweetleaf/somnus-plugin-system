# PACKET-004 — Reference Plugin Implementation

**Owner:** next executing agent
**Status:** QUEUED
**Depends on:** PACKET-002
**Size:** one session
**Priority:** medium — the contract has no worked example

## Mission

Populate `installed/example_plugin/` with a real, loadable reference plugin authored against
`SPEC.md`. The directory currently contains 14 files totalling 0 bytes, committed empty in the
extraction. Nothing in this repository demonstrates the contract it specifies, so every plugin
author must reconstruct it from `SPEC.md` prose and loader source. This packet produces the
worked example: a manifest that validates, a `Plugin` class that loads, and an API extension that
mounts — each exercising the canonical contract rather than the superseded one.

Additionally correct the extraction artifact at `installed/example_plugin/memory/extensions`,
which is a 0-byte regular file that was a directory in the donor codebase.

## Required Reads

- `SPEC.md` — the entire document. Sections 2, 6, 7, and 8 are the contract this plugin implements.
- `docs/IMPORT_TRUTH.md` and the PACKET-002 exit report — confirm the convergence actually landed
  before authoring against it
- `plugin_base.py` lines 79 to 137 — the manifest schema being instantiated
- `plugin_base.py` lines 230 to 260, and 548 to 566 — the base class and the four hooks
- `plugin_manager.py` lines 668 to 809 — the loader and API mount the plugin must satisfy
- `MEMORY.md` entry `2026-09-05 — NEGATIVE KNOWLEDGE` — why the previous "complete example" claim
  was false, so it is not repeated

## Invariant

- The reference plugin subclasses the **canonical** `plugin_base.PluginBase` and implements all
  four `_plugin_*` hooks. It must not use the superseded `on_*` convention.
- Its `manifest.json` validates against the canonical `PluginManifest` with no field invented and
  no required field omitted.
- It demonstrates the contract as specified, not a convenient subset. If a manifest field or
  extension point cannot be demonstrated because no loader reads it, that is stated in the
  plugin's own documentation rather than quietly skipped.
- It loads through the real loader path. A plugin that validates but does not load has not
  satisfied this packet.
- No host implementation is vendored to make it run. If the host boundary blocks a live load,
  record that honestly rather than stubbing around it.

## Surfaces

Implementation:
- `installed/example_plugin/manifest.json` — a complete, validating manifest
- `installed/example_plugin/plugin.py` — `class Plugin(PluginBase)` with all four hooks
- `installed/example_plugin/__init__.py`
- `installed/example_plugin/api/__init__.py` — must export `router`, per `SPEC.md` section 7
- `installed/example_plugin/api/routes.py`, `api/models.py`
- `installed/example_plugin/requirements.txt`
- `installed/example_plugin/memory/extensions` — the 0-byte file removed and recreated as a
  directory, matching the donor's intent
- `installed/example_plugin/agents/`, `workflows/`, `assets/` — populated or documented as
  reserved, per the `SPEC.md` section 7 finding that no loader reads them

Evidence:
- The load transcript, captured in the exit report

Continuity:
- `SPEC.md` — section 8 updated to point at a real example instead of describing an empty one
- `AUTHORITY_MAP.md` — the `installed/` classification changes from Noise to Evidence
- `MEMORY.md`, `CONTEXT.md`, `STATE.md`, `NOTEPAD.md`, `TASK.md`, `filetree.md`

## Hard Bans

- Do not author against `plugin_manager.PluginBase`. It is deleted by PACKET-002; if it still
  exists, PACKET-002 did not land and this packet must not start.
- Do not put `router` only in `api/routes.py`. The loader imports `api/__init__.py` and reads
  `router` from it. This is the single most likely authoring mistake.
- Do not name the plugin class anything but `Plugin`. The loader does `getattr(module, 'Plugin')`.
- Do not invent manifest fields. The schema has 32 fields and pydantic will reject extras.
- Do not vendor a `MemoryManager` to make the plugin run.
- Do not claim the plugin loads without pasting the transcript that proves it.
- Do not leave any file at 0 bytes. That is the exact defect this packet exists to correct.

## Validation

```bash
find installed/example_plugin -type f -size 0
./.venv/bin/python -c "
from plugin_base import PluginManifest
from pathlib import Path
m = PluginManifest.from_file(Path('installed/example_plugin/manifest.json'))
print('manifest OK:', m.name, m.version, m.plugin_type)
"
./.venv/bin/python -c "
import importlib.util, plugin_base
spec = importlib.util.spec_from_file_location('ex', 'installed/example_plugin/plugin.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
P = getattr(mod, 'Plugin', None)
print('Plugin class found:', P is not None)
print('subclasses canonical PluginBase:', issubclass(P, plugin_base.PluginBase))
"
./.venv/bin/python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('exapi', 'installed/example_plugin/api/__init__.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
print('router exported:', hasattr(mod, 'router'))
"
bash gate.sh
```

Expected:

- `find ... -size 0` returns **nothing**. Any 0-byte file fails this packet.
- Manifest loads and prints name, version, and plugin_type.
- `Plugin class found: True` and `subclasses canonical PluginBase: True`.
- `router exported: True`.
- `gate.sh` passes or reports honest `NOT RUN` for checks whose prerequisites are genuinely absent.

If the host boundary prevents a live end-to-end load, the manifest and class-structure checks
must still pass, and the blocked step is recorded as `NOT RUN` with the missing host module named.

## Exit

Record in `NOTEPAD.md`:

- Commit hash, files created
- Verbatim output of all four validation commands
- The `find -size 0` result proving no empty files remain
- Which manifest fields and extension points could not be demonstrated, and why
- Whether an end-to-end load through `PluginManager.load_plugin` was achieved or blocked on the
  host boundary
- `bash gate.sh` output verbatim

## Handoff

Write the marketplace hardening packet next. `OPSEC.md` SEC-02 through SEC-08 are unpacketized
and the marketplace network path must stay disabled until they are resolved. Alternatively write
the orchestration defect sweep packet for `docs/DEFECT_INDEX.md` D-001 through D-014.

Hazards: `SPEC.md` section 7 records that `agent_actions`, `workflow_nodes`, `memory_extensions`,
`ui_components`, and `api_endpoints` are manifest fields no loader reads. Do not build elaborate
`agents/` or `workflows/` content that nothing will ever execute — document them as reserved
surface instead, and say so in the exit report.
