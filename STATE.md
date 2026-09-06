# STATE — somnus-plugin-system

> **Charter:** single-screen current runtime truth. What is true *right now*.
>
> This file is deliberately narrow. It does not hold history (`NOTEPAD.md`), the dated index
> (`CONTEXT.md`), durable rulings (`MEMORY.md`), or the contract (`SPEC.md`). It answers four
> questions an arriving agent asks before anything else.
>
> **Refresh on every state change.** A stale `STATE.md` is worse than none.

**Last refreshed:** 2026-09-05
**HEAD:** `924594f` · **Extraction commit:** `5278e3c` (from the `somnus-os` donor codebase)

> **THE CONTROL PLANE IS UNCOMMITTED.** Everything described below — the router, this file,
> `SPEC.md`, `MEMORY.md`, the packets, `.claude/` — exists only as working-tree state. `HEAD`
> (`924594f`) still contains the pre-repair state: byte-identical `AGENTS.md`/`CLAUDE.md` twins,
> placeholder `CONTEXT.md`/`MEMORY.md`, and the 436-line foreign `NOTEPAD.md`. **A
> `git checkout`, `git stash`, or `git reset --hard` destroys all of it.** Commit before doing
> anything destructive with git. `gate.sh` warns about this on every run.

**Working tree:** control-plane documents added. **No tracked `.py` module was modified.** Two
untracked `.py` files (`tools/native/plugin/__init__.py`, `tools/native/plugin/identifiers.py`)
plus `test/plugin/smoke.py` were introduced by a subagent outside the approved plan — see §4 and
`TASK.md`.

---

## 1. Does it run?

**No.** Nothing in this repository imports today.

| Blocker | Detail | Status |
|---|---|---|
| Dependencies absent | No `.venv`. Required and missing: `pydantic`, `fastapi`, `aiofiles`, `aiohttp`, `watchdog`, `semver`, `importlib_metadata`. Present on host: `certifi`, `cryptography`. Host Python 3.12.3. | **OBSERVED** — `python3 -c "import plugin_base"` → `ModuleNotFoundError: No module named 'pydantic'` |
| Missing symbol | `security.py:34` imports `PluginPermission` from `plugin_base`, which does not define it (only `plugin_manager.py:75` does). Cascades to `marketplace.py:28`. | **PREDICTED, NOT YET OBSERVED** — blocked behind the dependency failure |
| Host boundary unresolved | `core.memory_core`, `schemas.session`, `core.security_layer` are supplied by the embedding system, absent here by design | **BY DESIGN** — see `HOST_BOUNDARY.md` |

## 2. What is the gate posture?

`bash gate.sh` → every dependency-gated check reports **`NOT RUN`**.

There is **no test suite** in this repository. No `tests/`, no pytest configuration, no CI.
Per operator doctrine, validation here is experimentation, not a pytest suite. Do not
manufacture a green check.

## 3. What is the active packet?

**`PACKET-001` — dependency and import truth.** See `TASK.md` and
`packets/PACKET-001-dependency-and-import-truth.md`.

It is the unblocking packet: every other packet is gated behind it, because every runtime claim
in this control plane is currently marked PREDICTED and needs to become OBSERVED.

| Packet | Status | Blocked on |
|---|---|---|
| `PACKET-001` dependency and import truth | **READY** | nothing |
| `PACKET-002` lineage convergence | BLOCKED | 001 |
| `PACKET-003` host boundary realization | BLOCKED | 001 |
| `PACKET-004` reference plugin implementation | BLOCKED | 002 |

## 4. What must not be assumed?

- **Do not assume the lineage convergence has happened.** `plugin_base.py` is *ruled* canonical;
  the merge has **not** been executed. All seven name collisions still exist in source.
- **Do not author a plugin against `plugin_base.PluginBase` and expect it to load.** The only
  working loader gates on its own local `PluginBase` at `plugin_manager.py:701` and will reject it.
- **Do not treat `installed/example_plugin/` as an example.** It is 14 files at 0 bytes.
- **Do not resolve a donor import** by vendoring a stub or deleting it. That is the host
  boundary. See `HOST_BOUNDARY.md`.
- **Do not trust `marketplace.py`'s signature verification.** `marketplace.py:346` compares a
  server-supplied hash to a locally computed SHA-256. See `OPSEC.md`.
- **Do not `pip install -r requirements.txt`.** That file was created by a subagent outside the
  approved plan and claims no third-party packages are required. `pyproject.toml` is the
  dependency contract, and it declares nine. See `TASK.md`.
- **Do not treat `tools/`, `test/`, `snapshots/`, `SCOPE.md`, or `SOTA_RUN.md` as this
  repository's structure.** Same origin, operator decision pending.

---

**Next surface:** `AGENTS.md` for routing · `TASK.md` for the board · `AUTHORITY_MAP.md` when a
claim is in doubt.
