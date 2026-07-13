# `.eco` Bytecode Exploratory Disassembly — Design

## Background

`two_worlds_2_fix` is reverse-engineering how Two Worlds II tracks quest
progress in the save file, focused on the Polish quest "Ekspercka przygoda
poboczna: Bogowie i demony" (Expert Side Adventure) and NPC "Casbrim". Prior
work (recorded in `script/wd_extraction_notes.md`) established:

- `find_eco_files` (`tw2tools/wd_format.py`) locates all 21 real compiled
  `.eco` scripts inside `DLC3_PC.wd` via a literal `"ECO\x00"` magic header
  and an embedded, self-identifying script name — including the main quest
  script `TwoWorlds2Quests.eco`.
- Every NPC has a property-bag record with keys `PCQ, PSDN, PQUS, Lector,
  PUMN, PQTIMED, PQBS`, all confirmed as literal engine constants inside the
  compiled scripts. `PCQ` is a generic per-NPC conversation-state counter,
  confirmed quest-relevant via a real before/after save pair (changed exactly
  at quest acceptance) and observed to cycle `20 → 3483 → 853` for Casbrim,
  settling at `853` for the rest of the available save history.
- Extracting all printable strings from a compiled `.eco` script (a raw
  "strings"-style scan, not a resolved string table) and reading them in
  their raw occurrence order — which is **not deduplicated** — reveals a
  readable quest-lifecycle pattern: `QTD → QSD_C1/C2 → QUEST_GIVEN → QSD_C1/C2
  → QUEST_SOLVED → QSD → QFD_C1/C2 → QFD → QCD_C1/C2 → QCD`. These are
  generic engine keywords (state/event names), not translatable text.
- Searching the compiled bytecode for entity-specific strings (`Casbrim`,
  `SP3`, `Q_45`, `Ekspercka`) found **nothing** — confirming that
  entity/quest-specific references are done via small integer IDs, while the
  generic lifecycle keywords above are embedded as literal ASCII.
- The bytecode's actual instruction format (opcode width, operand encoding)
  is completely unknown — no prior work has attempted to decode it. The
  project deliberately stopped here on 2026-07-11, treating full opcode
  decoding as a separately-scoped future project.

The user has now asked to pick that project up, scoped as a **time-boxed
exploratory pass**: go far enough to find (or conclusively rule out, within
this one pass) the specific mechanism that would drive `QUEST_SOLVED` for
Gods and Demons/Casbrim — not to build a general-purpose disassembler.

## Problem with the current state

- The only existing `.eco`-related scratch artifact for the quest script,
  `script/wd_extract/dlc3_eco_full.bin`, is **1468 bytes** — far too small to
  be the real `TwoWorlds2Quests.eco` payload (a different script,
  `RPGCompute`, was noted as the largest real script at 293,725 bytes). It
  appears to be a stale/partial extraction from earlier ad-hoc work and
  should not be relied on.
- `script/wd_extract/eco_strings.json` holds string-scan output for 19
  scripts, but it was produced before `find_eco_files` existed and its
  extraction method is not verified against the current, correct payload
  boundaries.
- No prior attempt exists to correlate `PCQ`'s observed values against raw
  bytecode content, or to identify byte-level structure around the
  `QUEST_GIVEN`/`QUEST_SOLVED` string anchors.

## Goal

Within one time-boxed pass: determine enough of the `.eco` instruction shape
to find the byte-level mechanism (if any is discoverable via static analysis
alone) that would set `QUEST_SOLVED` for the Gods and Demons quest tied to
Casbrim, and produce a clear written finding — positive or negative —
regardless of outcome. Do not commit beyond this pass; continuing further is
a separate decision after seeing the results.

**Explicitly out of scope:** a general-purpose `.eco` disassembler, a full
opcode table, decoding scripts other than what's needed for cross-validation,
and any dynamic/runtime analysis (no debugger or live-instrumentation
capability is available — this is static analysis of the compiled bytecode
bytes only).

## Design

### Method: anchor-and-triangulate

Rather than reverse-engineering the instruction format in general, start
from facts already established and search for them directly in the raw
bytecode:

1. **Extract clean payloads.** Re-run `find_eco_files` against the real
   `DLC3_PC.wd` to get a correct, complete dump of `TwoWorlds2Quests.eco`,
   plus 2–3 sibling `.eco` scripts (chosen for containing multiple
   recognizable lifecycle keywords, for cross-validation in step 3). Save
   raw bytes to `script/wd_extract/` (gitignored scratch, not committed).

2. **Locate and disambiguate lifecycle anchors.** Within
   `TwoWorlds2Quests.eco`, find every literal occurrence of `QUEST_GIVEN`,
   `QUEST_SOLVED`, `QTD`, `QSD`, `QFD`, `QCD` (ASCII, already confirmed
   present). For each occurrence, capture a bounded window of surrounding
   bytes (write to file, inspect only small excerpts — see Binary-output
   discipline below) and look for:
   - a nearby small integer that could be a per-quest ID, cross-checked
     against the known `Q_45` / `GROUP_2` numeric IDs for this quest
   - any byte pattern that recurs consistently across multiple occurrences
     of the *same* keyword (a candidate opcode/instruction framing)

   Since one script's bytecode contains many quests' lifecycles, correctly
   identifying *which* `QUEST_SOLVED` occurrence belongs to Gods and Demons
   is expected to be the hardest part of this stage.

3. **Cross-validate.** Check whether the byte pattern found in step 2 also
   appears around the equivalent keyword occurrences in the sibling scripts
   extracted in step 1. A pattern that holds across multiple independently
   compiled scripts is good evidence of a real instruction shape rather than
   coincidence. This is the only "generality" this pass aims for — enough to
   trust a finding, not a reusable disassembler.

4. **Correlate to `PCQ`.** Search the same `TwoWorlds2Quests.eco` payload for
   the already-observed `PCQ` values (`20`, `3483`, `853`) encoded as u8,
   u16, and u32 (little-endian, matching every other integer field found so
   far in this codebase), and check whether any hit sits near the
   disambiguated Gods-and-Demons anchor identified in step 2. A hit here,
   consistent with the byte pattern from steps 2–3, is the target finding.

### Tooling boundary: scratch-first

This is speculative correlation work against an unknown, possibly-wrong
structural guess. Analysis code lives as ad-hoc Python scripts under
`script/wd_extract/`, **not** as new `tw2tools` modules with TDD — writing
tests around a structural hypothesis that may not hold would waste effort
and calcify a guess prematurely.

If a finding resolves into something stable and reusable (the same way
`find_eco_files` was promoted into `tw2tools` after being discovered
organically through ad-hoc exploration), it gets added to `tw2tools` with
tests at that point, following the project's established TDD convention —
not before.

### Binary-output discipline (standing rule, restated for this work)

Per existing project convention: never dump raw bytecode or binary content
directly into the conversation. All extraction and analysis output goes to
files under `script/wd_extract/`; only small, bounded excerpts (hex dumps of
a few dozen bytes, short lists of offsets, etc.) are read back for
inspection.

### Stopping criteria and deliverable

This pass stops — regardless of outcome — once steps 1–4 have been run once
through. It does **not** escalate into open-ended opcode-table construction
if step 2/3 fails to converge on a stable pattern.

Deliverable: a new entry in `script/wd_extraction_notes.md`, matching the
document's existing rigor for recording both confirmed findings and
falsified hypotheses:

- **If successful:** the byte-level pattern found, with example byte
  sequences and offsets, showing how it correlates to the `QUEST_SOLVED`
  trigger and the observed `PCQ` values.
- **If unsuccessful:** what was tried at each of the four steps, what did
  and didn't hold up, and why — so a future attempt doesn't repeat the same
  dead ends.

### Testing

No new `tw2tools` unit tests are anticipated for this pass (see Tooling
boundary above). If step 1's extraction reveals a bug or gap in
`find_eco_files` itself (e.g. it mishandles a script boundary), that fix
would go through the project's normal TDD workflow like any other
`wd_format.py` change.

## Explicitly not doing

- Building a general-purpose `.eco` disassembler or opcode table.
- Any dynamic analysis, debugger attachment, or game-process instrumentation
  — none is available; this is static bytecode analysis only.
- Continuing past this one exploratory pass without a new, separate decision
  from the user to do so.
