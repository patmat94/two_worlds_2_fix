# `.eco` Bytecode Decoder — Design

## Background

`two_worlds_2_fix` is reverse-engineering how Two Worlds II tracks quest
progress in the save file, focused on the Polish quest "Ekspercka przygoda
poboczna: Bogowie i demony" (Expert Side Adventure) and NPC "Casbrim." A
prior time-boxed exploratory pass (design:
`docs/superpowers/specs/2026-07-13-eco-bytecode-exploration-design.md`,
outcome recorded in `script/wd_extraction_notes.md`) tried an
anchor-and-triangulate approach — searching for known `PCQ` values and
quest IDs near the `QUEST_GIVEN`/`QUEST_SOLVED` string anchors in
`TwoWorlds2Quests.eco` — and came up **negative/inconclusive**: the
closest correlation found was 354 bytes from any anchor, far outside the
32-byte window used throughout that investigation, with no supporting
quest-ID or cross-script evidence.

That pass deliberately stopped short of decoding the actual bytecode
instruction format, on the grounds that doing so is a fundamentally
larger project — writing a disassembler for a completely undocumented
VM — than string-anchor correlation. The user has now asked to take on
that larger project.

**Checked for prior art first (2026-07-13):** web search turned up no
documentation of the `.eco` compiled bytecode format. Existing Two
Worlds/Two Worlds II modding tools (an official SDK, and fan tools named
"WD Tool," "Paramreader," "Soundstore Editor," "LangEdit Tool") cover
archive extraction, parameters, sound, and translation — none touch
compiled quest-script internals. Decided to proceed as genuine
from-scratch reverse engineering rather than search further.

## What we already know (inputs to this project)

- `find_eco_files` / `extract_eco_files_from_wd_archive`
  (`tw2tools/wd_format.py`, tested) correctly locate and extract all 21
  real compiled `.eco` scripts from `DLC3_PC.wd`. `TwoWorlds2Quests.eco`
  is 179,340 bytes.
- `find_null_terminated_strings` (tested) correctly scans null-terminated
  ASCII string constants with their byte offsets.
- String constants in `TwoWorlds2Quests.eco` are **interleaved with
  bytecode**, not stored in a separate contiguous pool — confirmed: 3,122
  strings span 98.2% of the file's byte range.
- **The string table is not deduplicated.** The same literal (e.g.
  `translateQ_%d_QTD`, `PCQ`, `Lector`, `translateDQ_%d`,
  `translateGROUP_%d`) appears once per place the *source* code
  referenced it, not once per unique value. This means we have dozens to
  hundreds of exact byte offsets where we are certain the surrounding
  compiled code does something semantically identical — a load-bearing
  fact for the technique below.
- Confirmed literal engine constants: property-bag keys `PCQ`, `PSDN`,
  `PQUS`, `Lector`, `PUMN`, `PQTIMED`, `PQBS`; lifecycle state names
  `QUEST_GIVEN`, `QUEST_SOLVED`; printf-style templates
  `translateQ_%d_QTD`/`_QSD_C1`/`_QSD_C2`/`_QFD_C1`/`_QFD_C2`/`_QCD_C1`/`_QCD_C2`,
  `translateDQ_%d`, `translateGROUP_%d`, `translateName_%d`.
- `QUEST_GIVEN` and `QUEST_SOLVED` are **not** per-quest templates (no
  `%d`) — only 1 and 2 occurrences respectively exist in the entire
  179,340-byte file, meaning they're referenced generically by all
  quests through some other addressing mechanism, not inlined per quest.
- No dynamic analysis capability exists (no debugger, no live
  instrumentation) — this is static analysis of the compiled bytecode
  bytes only, same constraint as the prior pass.
- Known `PCQ` transition values for Casbrim: `20 → 3483 → 853`. Known
  quest IDs for Gods and Demons: `45` (`Q_45`), `2` (`GROUP_2`).

## Goal

Build a **general-purpose `.eco` bytecode disassembler** — real,
reusable tooling that can decode instructions across `.eco` scripts
generically (opcode identification, instruction boundaries, operand
types), not a one-off hack for this single quest. Apply it, once
working, to find what triggers `QUEST_SOLVED` for Gods and
Demons/Casbrim specifically.

This is explicitly **staged, with checkpoints** rather than committed to
end-to-end up front: each stage answers a specific question, and the
project pauses at each checkpoint for an explicit decision to continue,
change approach, or stop — rather than ratcheting forward automatically
once effort has been sunk into an earlier stage.

## Design

### Stage 1: Format discovery via repeated-literal alignment

**Method.** Pick the most-repeated literal strings in
`TwoWorlds2Quests.eco` (candidates: `translateQ_%d_QTD` and its
`_QSD`/`_QFD`/`_QCD` siblings, `translateDQ_%d`, `translateGROUP_%d`,
`translateName_%d`, the property-bag keys). For each literal, gather
every occurrence's byte offset, then align a fixed window of bytes
immediately before and after each occurrence across all its repeats.

- Bytes that are **identical across every repeat** of the same literal
  are strong candidates for opcode/instruction-framing bytes (the "load
  this string constant" instruction shape).
- Bytes that **vary** across repeats are candidates for operands —
  cross-check them against things already known: does a varying byte
  right before the string equal the string's own length? (The
  length-prefixed convention is already confirmed elsewhere in this
  engine's formats — property bags, named records — so this is a
  concrete, checkable hypothesis, not a guess.) Does a varying byte
  match a nearby quest ID or other already-known small integer?
- Cross-validate any candidate pattern against **multiple different
  literals** (not just one), and against a second script (e.g.
  `RPGCompute`, which has 1,045 strings — the most string-rich script
  after `TwoWorlds2Quests`) if it shares any of the same literals.

**Checkpoint 1 deliverable:** a report — either a confident, cross-validated
byte-level shape for at least one instruction (most likely "reference a
string constant"), with example bytes and the evidence for each claim, or
a documented account of what was tried and why it didn't converge. Continue
to Stage 2 only on explicit go-ahead after this report.

### Stage 2: Opcode-table expansion (scoped after Checkpoint 1)

Use whatever Stage 1 confirms as an anchor to identify neighboring
instruction types — most plausibly, whatever comes immediately before a
string-reference in a real call site (candidate: a "call native
function" instruction) and how results are used afterward. Also worth
pursuing: identifying branch/jump instructions by searching for byte
patterns that resolve to valid in-file offsets, and identifying
integer-push instructions by searching for the confirmed `PCQ`
values (`20`, `3483`, `853`) and quest IDs (`45`, `2`) as literal operands
near instructions we already understand.

The exact plan for this stage depends on what Stage 1 actually finds, so
it is deliberately not fully specified here — Checkpoint 1's report is
the input to scoping it.

**Checkpoint 2 deliverable:** a report on how much of the opcode space is
understood (which instruction types, with what confidence), and whether
that's enough to attempt Stage 3.

### Stage 3: Working disassembler tool

Once enough instructions are confirmed, build a real `tw2tools` module
(e.g. `eco_disasm.py`) with TDD, following the project's established
testing convention. It should walk a `.eco` script's bytecode linearly
and print known instructions as readable mnemonics, **defensively
marking unknown/unrecognized bytes rather than crashing** — a
best-effort disassembler design appropriate for a partially-understood
instruction set, not one that assumes full opcode coverage.

**Checkpoint 3 deliverable:** apply the disassembler to the
`QUEST_SOLVED` region(s) of `TwoWorlds2Quests.eco` specifically, and
report whether it resolves the original question (what triggers
`QUEST_SOLVED` for Gods and Demons/Casbrim) — positive or negative, with
the same rigor as the prior pass's write-up.

### Tooling boundary: scratch-first, same rule as the prior pass

Stage 1 (and likely Stage 2) are speculative pattern-finding against a
completely unknown format — they stay as ad-hoc Python scripts under
`script/wd_extract/` (gitignored), not `tw2tools`. Only Stage 3's
disassembler — and only for whatever subset of the opcode space has
actually been confirmed by then, not a guessed-at complete table —
becomes real, tested `tw2tools` code.

### Binary-output discipline (standing rule, restated)

Same as every prior investigation phase: never dump raw bytecode/binary
content directly into the conversation. All extraction and analysis
output goes to files under `script/wd_extract/`; only small, bounded
excerpts are read back for inspection.

### Cost/effort bounding

Given the wide, previously-discussed cost range for this kind of
open-ended reverse engineering (rough estimate: $15 to $60+ across
stages, with real risk of not fully succeeding even after heavy
investment), each stage is sized to answer its own checkpoint question,
not to guarantee the final outcome. No commitment beyond reaching the
next checkpoint is made up front.

## Explicitly not doing

- Committing to Stage 2 or 3 before Checkpoint 1's report is reviewed.
- Assuming full opcode-table coverage — the disassembler (Stage 3, if
  reached) is explicitly a best-effort, partial-coverage tool.
- Any dynamic analysis, debugger attachment, or game-process
  instrumentation — none is available; this is static bytecode analysis
  only, same constraint as every prior phase of this investigation.
