# Memory Log

> Persistent codebase memory substrate.
>
> This file is expected to become **large**. Do not prune it merely to keep it readable.
> Append durable, source-backed project knowledge continuously as the codebase evolves.
>
> `CONTEXT.md` is the traversal/index layer for this file. A context entry should carry enough
> matching date/title/keys that an agent can locate the corresponding memory stratum without
> rereading the entire repository.
>
> This is not only a decisions log. Preserve architecture discoveries, implementation truth,
> experiments, failures, verification results, provenance, boundaries, changed assumptions,
> file relationships, runtime behavior, operator doctrine, and unresolved questions whenever
> they will matter to future work.

## Memory Operating Contract

- **Append, do not flatten history.** Later entries may supersede earlier entries; preserve both and mark the newer truth clearly.
- **Write after substantial work.** Memory is part of the codebase runtime, not an end-of-project archive.
- **Prefer source-backed truth.** Name files, symbols, commands, artifacts, commits, reports, tests, and observed behavior.
- **Record negative knowledge.** Failed approaches, disproven assumptions, unsafe shortcuts, and “do not repeat” findings are valuable memory.
- **Preserve uncertainty.** Distinguish verified facts, operator directives, current interpretations, hypotheses, and open questions.
- **Keep chronology searchable.** Each substantial entry begins with a date and a high-signal title.
- **Emit traversal keys.** Reuse stable nouns, filenames, symbols, subsystem names, artifact names, and doctrine terms that can also appear in `CONTEXT.md`.
- **Do not over-compress.** If a future agent would need the details to avoid rediscovery, keep the details here.
- **Do not use MEMORY as scratch space.** Ephemeral reasoning belongs in `NOTEPAD.md`; promote only durable outcomes here.
- **Do not silently rewrite old entries.** Prefer a new dated correction/supersession entry unless fixing a factual typo.

## Retrieval Model

Typical traversal:

`AGENTS.md` → `CONTEXT.md` → matching date/title/keys → `MEMORY.md` → named code/docs/artifacts → live verification

A useful entry therefore answers:

- What changed or was learned?
- Where in the repo does that truth live?
- What evidence established it?
- What interpretation or boundary should persist?
- What should a future agent search/read next?
- What was ruled out, superseded, or left unresolved?

---

## <YYYY-MM-DD> — <HIGH-SIGNAL EVENT / DISCOVERY / CHANGE TITLE>

**Keys:** `<subsystem>` · `<file-or-symbol>` · `<capability>` · `<artifact>` · `<doctrine-term>`

**Status:** `<VERIFIED | LANDED | ACTIVE | PARTIAL | FAILED | SUPERSEDED | HYPOTHESIS | OPERATOR-DIRECTIVE>`

### Durable findings

- <DETAILED FINDING>
- <DETAILED FINDING>
- <DETAILED FINDING>

### Code / architecture truth

- `<path/to/file>`:
  - `<ClassOrFunction>` — <WHAT IT ACTUALLY DOES / RELATIONSHIP TO SYSTEM>
  - `<SYMBOL>` — <IMPORTANT CONTRACT / INVARIANT>
- `<path/to/related-file>`:
  - <RELATIONSHIP, DATA FLOW, AUTHORITY, OR DEPENDENCY>

### Evidence / verification

- Command or procedure:
  ```bash
  <COMMAND>
  ```
- Result:
  - <PASS/FAIL/OBSERVED BEHAVIOR>
  - <METRIC / COUNT / DIGEST / OUTPUT / ARTIFACT>
- Artifacts:
  - `<path/to/artifact>`
  - `<path/to/report>`

### Interpretation / boundary

- <WHAT THIS PROVES>
- <WHAT THIS DOES **NOT** PROVE>
- <CURRENT SAFE INTERPRETATION>
- <AUTHORITY OR CANON BOUNDARY IF RELEVANT>

### Provenance / lineage

- Previous state: <PRIOR IMPLEMENTATION / ASSUMPTION / ARTIFACT>
- New state: <CURRENT IMPLEMENTATION / ASSUMPTION / ARTIFACT>
- Trigger: <WHAT CAUSED THE CHANGE>
- Supersedes: `<DATE / ENTRY / FILE / CLAIM>` or `none`

### Failures / rejected paths

- <FAILED APPROACH> — <WHY IT FAILED OR WAS REJECTED>
- <BAD ASSUMPTION> — <CORRECTIVE TRUTH>
- <DO-NOT-REPEAT NOTE>

### Open threads

- <UNRESOLVED QUESTION>
- <NEXT EXPERIMENT OR VERIFICATION>
- <DEPENDENCY / BLOCKER>

### Retrieval anchors

Future agents should search/read:

- `<KEYWORD OR EXACT SYMBOL>`
- `<path/to/file-or-doc>`
- `<artifact/report/test>`
- Related memory: `<YYYY-MM-DD — TITLE>`
- Context index key: `<SAME KEY USED IN CONTEXT.md>`

---

## <YYYY-MM-DD> — <SECOND ENTRY TITLE>

**Keys:** `<key>` · `<key>` · `<key>`

**Status:** `<STATUS>`

### Durable findings

- <...>

### Evidence / verification

- <...>

### Interpretation / boundary

- <...>

### Retrieval anchors

- <...>

---

## Canon / Authority Lock

> Use this section only when the repository has stable authority relationships that future agents
> must know before interpreting code. Keep it concrete and repo-specific.

Canonical implementation surfaces:
- `<path>`
- `<path>`

Persistent authority / state surfaces:
- `<README_OR_SPEC>`
- `<STATE_OR_PLAN>`
- `MEMORY.md`
- `CONTEXT.md`

Historical / overlay / non-canon surfaces:
- `<path>` — <WHY / SCOPE>

Authority rule:
- <LIVE CODE VS DOCS VS GENERATED MAPS VS OPERATOR DIRECTIVE ORDERING>

---

## Long-Lived System Map

> Optional but useful for mature repositories. This is not a replacement for dated entries.
> Keep only relationships that remain broadly stable.

### `<SUBSYSTEM>`

- Authority: `<path>`
- Key symbols: `<symbols>`
- Inputs: `<inputs>`
- Outputs: `<outputs>`
- Depends on: `<dependencies>`
- Feeds: `<downstream>`
- Current invariant: <INVARIANT>
- Search keys: `<keys>`

### `<SUBSYSTEM>`

- <...>

---

## Durable Operator / Repository Doctrine

> Record only doctrine that materially affects how this codebase must be understood or changed.

- <DOCTRINE / INVARIANT>
- <DOCTRINE / INVARIANT>
- <WHAT AN AGENT MUST NOT ABSTRACT AWAY>

---

## Known Hazards / Anti-Rediscovery Index

- `<HAZARD KEY>` — <WHAT HAPPENED> — see `<YYYY-MM-DD — ENTRY>`
- `<FAILED PATH KEY>` — <WHY NOT TO REPEAT> — see `<YYYY-MM-DD — ENTRY>`
- `<ENVIRONMENT KEY>` — <DRIFT / VERSION / MACHINE CONSTRAINT> — see `<YYYY-MM-DD — ENTRY>`

---

## Memory Maintenance Notes

- The file may contain apparently conflicting historical entries. Resolve by date, status, provenance, and explicit supersession rather than deleting history.
- When a finding becomes important enough to guide near-term work, add or refresh its compact mirror in `CONTEXT.md`.
- When `CONTEXT.md` points here, preserve the same nouns and keys. Retrieval quality depends on lexical continuity.
- If memory grows beyond convenient direct reading, that is expected. Improve indexing and traversal; do not neuter the memory substrate.
