# Project Context

> High-density traversal index for the repository's persistent memory.
>
> This file is **not** a single mutable "current state" snapshot and it is not a replacement for
> `MEMORY.md`. It remains chronological and continuously written, but entries are intentionally
> shorter than their memory counterparts.
>
> Its job is to let an agent rapidly answer:
> 1. What strata of project history/state are relevant?
> 2. What exact keys should I use to traverse `MEMORY.md`?
> 3. What files/symbols/artifacts should I open next?
> 4. What truth is current enough to act on without rereading the whole repo?
>
> Think of `CONTEXT.md` as the codebase's index/routing layer and `MEMORY.md` as the deep store.

## Context Operating Contract

- **Keep dated sections.** Do not collapse the file into one latest-state block.
- **Append after substantial turns.** Context evolves with the codebase.
- **Compress, do not amputate.** Preserve the nouns, symbols, filenames, status, and boundaries needed for retrieval.
- **Mirror MEMORY keys.** Use the same date/title vocabulary and stable search terms whenever possible.
- **Bias toward navigation.** A context entry should quickly route the agent toward the right memory entry and live repo surfaces.
- **Carry current truth explicitly.** If an older entry is superseded, add a newer dated entry saying so.
- **Keep details short here.** Deep rationale, logs, provenance, test output, alternatives, and forensic detail belong in `MEMORY.md`.
- **Preserve high-value negative state.** Active hazards, failed lanes, forbidden assumptions, and unresolved gaps belong here when they affect routing.
- **Never treat this as disposable handoff prose.** It is persistent codebase context.

## Traversal Model

Typical codebase reasoning loop:

`AGENTS.md`
→ scan newest/relevant `CONTEXT.md` entries
→ extract date/title/keys
→ jump into matching `MEMORY.md` strata
→ open named code/docs/artifacts
→ inspect/execute/validate live state
→ write `NOTEPAD.md` during work
→ persist new findings back into `MEMORY.md`
→ append/update compact routing entry here

Recommended lookup order:

1. Exact filename / symbol / artifact key
2. Subsystem / capability key
3. Date + title
4. Related canon/state doc
5. Live code verification

---

## <YYYY-MM-DD> — <HIGH-SIGNAL CONTEXT TITLE>

**Keys:** `<subsystem>` · `<file-or-symbol>` · `<capability>` · `<artifact>`

- **State:** <ONE OR TWO SENTENCES OF CURRENT TRUTH>
- **Authority:** `<PRIMARY FILE / DOC / SYMBOL>`
- **Changed:** <WHAT JUST LANDED / FAILED / WAS CORRECTED>
- **Boundary:** <WHAT MUST NOT BE ASSUMED / WHAT THIS DOES NOT PROVE>
- **Evidence:** `<TEST / COMMAND / REPORT / ARTIFACT>` — <PASS/FAIL/OBSERVED>
- **Next read:** `MEMORY.md` → `<YYYY-MM-DD — MATCHING MEMORY TITLE>`
- **Then inspect:** `<path>` · `<path>` · `<symbol>`
- **Open:** <UNRESOLVED THREAD OR `none`>

## <YYYY-MM-DD> — <SECOND CONTEXT TITLE>

**Keys:** `<key>` · `<key>` · `<key>`

- **State:** <...>
- **Authority:** `<...>`
- **Changed:** <...>
- **Boundary:** <...>
- **Evidence:** <...>
- **Next read:** `MEMORY.md` → `<MATCHING ENTRY>`
- **Then inspect:** `<...>`
- **Open:** <...>

---

## Current Canon / Authority Index

> Compact routing surface only. Detailed rationale and provenance belong in `MEMORY.md`.

- `<CANON FILE OR DOC>` — <ROLE / AUTHORITY>
- `<CANON FILE OR DOC>` — <ROLE / AUTHORITY>
- `<STATE SURFACE>` — <WHAT TRUTH IT OWNS>
- `<FILE TREE / MAP>` — <NAVIGATION AUTHORITY>
- `MEMORY.md` — deep persistent codebase memory
- `CONTEXT.md` — chronological memory index / traversal layer
- `NOTEPAD.md` — live scratch / working notebook; non-canon unless promoted

### Authority precedence

`<OPERATOR DIRECTIVE>` → `<LIVE CODE / STATE>` → `<CANON DOCS>` → `<GENERATED MAPS>` → `<HISTORICAL DOCS>`

Adjust to the repository; do not invent precedence the project does not actually use.

---

## Active Runtime / Architecture Keys

> This section is a compact jump table for concepts that recur across many dated entries.
> Keep it short. Its purpose is key traversal, not explanation.

| Key | Current meaning | Authority / next surface |
|---|---|---|
| `<KEY>` | <ONE-LINE CURRENT TRUTH> | `<path-or-symbol>` |
| `<KEY>` | <ONE-LINE CURRENT TRUTH> | `<path-or-symbol>` |
| `<KEY>` | <ONE-LINE CURRENT TRUTH> | `<path-or-symbol>` |

---

## Active Hazards / Drift Keys

- `<HAZARD KEY>` — <CURRENT DANGER OR FALSE ASSUMPTION> — memory: `<DATE / TITLE>`
- `<ENV KEY>` — <VERSION / MACHINE / DEPENDENCY DRIFT> — inspect: `<path>`
- `<FAILED LANE KEY>` — <DO NOT TREAT AS CURRENT SUCCESS> — memory: `<DATE / TITLE>`

---

## Open Threads / Resume Keys

- `<THREAD KEY>` — <WHAT REMAINS OPEN> — next: `<file/test/experiment>`
- `<THREAD KEY>` — <BLOCKER / QUESTION> — memory: `<DATE / TITLE>`
- `<THREAD KEY>` — <OPERATOR-OWNED OR DEFERRED LANE>

---

## Recent Verification Index

> Keep only compact routing facts here; full outputs belong in `MEMORY.md` or verification artifacts.

- `<YYYY-MM-DD>` — `<COMMAND / TEST>` — `<PASS | FAIL | PARTIAL>` — `<artifact>`
- `<YYYY-MM-DD>` — `<COMMAND / TEST>` — `<PASS | FAIL | PARTIAL>` — `<artifact>`

---

## Context Maintenance Notes

- A context entry can be only a handful of bullets if those bullets preserve the right traversal keys.
- Prefer exact repo nouns over generic summaries: filenames, classes, functions, configs, tests, artifacts, run IDs, model/checkpoint names.
- Do not erase old context solely because it is old; historical routing is useful when debugging regressions or provenance.
- When context gets large, improve headings, keys, and jump tables. Do not replace the chronological substrate with a tiny status dashboard.
- If an entry needs substantial explanation, put that explanation in `MEMORY.md` and point to it from here.
