# `.eco` Bytecode Decoder — Stage 1 (Format Discovery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Find the byte-level shape of at least one `.eco` bytecode instruction by aligning bytes around repeated literal strings and, once that showed strings carry no adjacent opcode, by mapping the file's string/bytecode structure and searching for integer references to known string offsets. This is Stage 1 of a 3-stage, checkpointed disassembler project (see the design doc); this plan covers **only** Stage 1, through Checkpoint 1. **Revised mid-execution (2026-07-13):** the original "align two literals and cross-check" approach (Tasks 4/5) was replaced after Task 3 found that string constants are packed back-to-back with no adjacent opcode — see Task 4's revision note for the full rationale.

**Architecture:** One tested `tw2tools` re-extraction step (reusing the already-tested `extract_eco_files_from_wd_archive`), followed by five scratch analysis scripts under `script/wd_extract/` (gitignored, not committed) that rank repeated literals, align bytes around the top one, map the whole file's string/gap structure, and search the largest gaps for offset references — ending in one write-up commit to `script/wd_extraction_notes.md`.

**Tech Stack:** Python 3 stdlib only (`struct`, `json`, `pathlib`, `collections.Counter`), pytest, the existing `tw2tools` package.

## Global Constraints

- **Binary-output discipline (standing project rule):** never dump raw bytecode or binary content directly into the conversation. Every task that inspects real bytes writes output to a file under `script/wd_extract/` and reads back only small, bounded excerpts.
- **`script/wd_extract/` is gitignored.** Scratch scripts and their output files placed there are intentionally **not** committed. Only the final `script/wd_extraction_notes.md` update gets committed (no new `tw2tools`/`tests` changes are anticipated for Stage 1 — the extraction re-run reuses the already-tested `extract_eco_files_from_wd_archive` from the prior investigation, unmodified).
- **This plan covers Stage 1 only, through Checkpoint 1.** Do not begin Stage 2 (opcode-table expansion) or Stage 3 (the disassembler tool) — those require a new, separate planning decision after this plan's Task 6 write-up is reviewed.
- **All existing tests must keep passing.** The suite was at 50 passing tests as of the prior investigation's merge to `main`; verify it's still green (no code changes are expected in this plan, but confirm anyway before the final commit).
- **Real data path:** `files/Two Worlds 2/DLC3_PC.wd` (~1.9GB, gitignored, read-only). Full-archive decompression takes roughly 20-30 seconds.
- **Prior scratch data no longer exists on disk.** The previous investigation's `script/wd_extract/eco_scripts/*.eco.bin` files were produced inside a now-deleted git worktree and were gitignored (never committed) — Task 1 of this plan must re-extract them from scratch. This is expected, not a regression.
- **Ground truth to verify against** (from `script/wd_extraction_notes.md`): exactly 21 real `.eco` files exist in `DLC3_PC.wd`; `TwoWorlds2Quests.eco` is exactly 179,340 bytes; `RPGCompute.eco` has 1,045 null-terminated strings (the most string-rich script after `TwoWorlds2Quests`); the property-bag key `PCQ` occurs exactly twice in `TwoWorlds2Quests.eco`.

---

### Task 1: Re-extract all 21 real `.eco` scripts to disk

**Files:**
- Create: `script/wd_extract/task1_extract_all_eco.py` (gitignored scratch — not committed)
- Creates on run: `script/wd_extract/eco_scripts/*.eco.bin` (21 files, gitignored)

**Interfaces:**
- Consumes: the already-tested `extract_eco_files_from_wd_archive(wd_data: bytes) -> list[EcoFile]` from `tw2tools.wd_format` (added and merged to `main` in the prior investigation — no changes needed, just re-run it).
- Produces: individual `.eco.bin` files under `script/wd_extract/eco_scripts/`, consumed by Tasks 2, 3, 4, and 5. Filenames are the sanitized script name plus `.eco.bin`, with a `_2`/`_3` numeric suffix on any name that repeats (two script names collide among the real 21: `JSTestCampaign` and `"Weather Script"` — this is a known, already-solved issue from the prior investigation, not something to re-discover).

- [ ] **Step 1: Write the script**

```python
"""Extract all real .eco scripts from DLC3_PC.wd using the already-tested
extract_eco_files_from_wd_archive. Scratch script (gitignored) - run once
from the repo root:

    python script/wd_extract/task1_extract_all_eco.py

Note: the previous investigation's extracted files no longer exist on
disk (they lived in a now-deleted git worktree's gitignored scratch
directory) - this re-extracts them from the real archive.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

from tw2tools.wd_format import extract_eco_files_from_wd_archive

WD_PATH = REPO_ROOT / "files" / "Two Worlds 2" / "DLC3_PC.wd"
OUTPUT_DIR = Path(__file__).resolve().parent / "eco_scripts"


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("*.eco.bin"):
        old.unlink()
    print(f"Reading {WD_PATH} ...")
    data = WD_PATH.read_bytes()
    print(
        f"Read {len(data)} bytes, scanning for .eco files "
        f"(decompresses the full archive - expect ~20-30 seconds)..."
    )
    eco_files = extract_eco_files_from_wd_archive(data)
    print(f"Found {len(eco_files)} .eco files")

    used_names: dict[str, int] = {}
    for eco in eco_files:
        base_name = sanitize(eco.name)
        count = used_names.get(base_name, 0) + 1
        used_names[base_name] = count
        suffix = f"_{count}" if count > 1 else ""
        out_path = OUTPUT_DIR / f"{base_name}{suffix}.eco.bin"
        out_path.write_bytes(eco.data)
        print(f"  {eco.name!r}: {len(eco.data)} bytes -> {out_path.name}")

    assert len(eco_files) == 21, (
        f"expected exactly 21 .eco files per prior findings, got {len(eco_files)}"
    )
    quests = [e for e in eco_files if e.name == "TwoWorlds2Quests"]
    assert len(quests) == 1, f"expected exactly one TwoWorlds2Quests, got {len(quests)}"
    assert len(quests[0].data) == 179340, (
        f"expected TwoWorlds2Quests.eco to be 179340 bytes, got {len(quests[0].data)}"
    )
    written_files = list(OUTPUT_DIR.glob("*.eco.bin"))
    assert len(written_files) == 21, (
        f"expected 21 files on disk after writing, found {len(written_files)}"
    )
    print("All ground-truth assertions passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task1_extract_all_eco.py`
Expected output: "Found 21 .eco files", 21 listed names/sizes, and finally "All ground-truth assertions passed." If any assertion fails, stop and investigate before continuing — every later task in this plan depends on these files being correct.

No commit for this step (scratch output, gitignored).

---

### Task 2: Rank the most-repeated string literals in `TwoWorlds2Quests.eco`

**Files:**
- Create: `script/wd_extract/task2_rank_repeated_strings.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task2_string_ranking.json` (gitignored)

**Interfaces:**
- Consumes: the already-tested `find_null_terminated_strings` from `tw2tools.wd_format`; `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 1.
- Produces: `task2_string_ranking.json` — a list of the top 20 most-repeated literal names, each with its occurrence count and full list of byte offsets, sorted descending by count. Consumed by Tasks 3 and 4 (which read entries `[0]` and `[1]` respectively).

- [ ] **Step 1: Write the script**

```python
"""Find and rank the most-repeated null-terminated strings in
TwoWorlds2Quests.eco, to identify candidate literals for byte-alignment
analysis in Tasks 3 and 4.

Uses min_length=4: a min_length=1 scan surfaces single printable bytes
followed by a zero byte (e.g. 'j', '=', '^') as the "most repeated"
strings - these are near-certainly incidental byte patterns in the
bytecode/operand stream, not real semantic string constants (no
compiled scripting engine emits single-character identifiers this
often). Every known real semantic literal in this file (PCQ, Lector,
QUEST_GIVEN, the translateX_%d_* templates, etc.) is 3+ characters, and
the only 3-character one (PCQ) repeats just twice - far below what's
needed to be a useful alignment anchor regardless - so min_length=4
excludes the noise without excluding anything relevant to this
specific ranking task.

Run: python script/wd_extract/task2_rank_repeated_strings.py
(depends on Task 1 having produced eco_scripts/TwoWorlds2Quests.eco.bin)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

from tw2tools.wd_format import find_null_terminated_strings

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
OUTPUT_PATH = Path(__file__).resolve().parent / "task2_string_ranking.json"


def main() -> None:
    assert ECO_PATH.exists(), f"run Task 1 first to produce {ECO_PATH}"
    data = ECO_PATH.read_bytes()
    records = find_null_terminated_strings(data, min_length=4, max_length=256)
    print(f"Total strings found (min_length=4): {len(records)}")

    counts = Counter(r.name for r in records)
    ranked = counts.most_common(20)
    print("Top 20 most-repeated strings:")
    for name, count in ranked:
        print(f"  {count:4d}x  {name!r}")

    offsets_by_name: dict[str, list[int]] = {}
    for r in records:
        offsets_by_name.setdefault(r.name, []).append(r.offset)

    output = [
        {"name": name, "count": count, "offsets": offsets_by_name[name]}
        for name, count in ranked
    ]
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Wrote top-20 ranking with offsets to {OUTPUT_PATH}")

    assert ranked[0][1] >= 2, (
        "expected at least one string to repeat 2+ times - alignment analysis "
        "needs repeats to work at all"
    )
    print("Ground-truth sanity check passed (top string repeats >= 2 times).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task2_rank_repeated_strings.py`
Expected output: a total string count noticeably lower than the prior investigation's 3,122 figure (that figure was from a `min_length=1` scan and includes single-character noise; this task deliberately uses `min_length=4` to exclude it — a lower count here is correct, not a regression), the top-20 list with counts (this time made of real multi-character identifiers, not single characters like `'j'`/`'='`/`'^'`), and "Ground-truth sanity check passed."

No commit (scratch output, gitignored).

---

### Task 3: Align byte windows around the single most-repeated literal

**Files:**
- Create: `script/wd_extract/task3_align_top_literal.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task3_alignment.json` (gitignored)

**Interfaces:**
- Consumes: `task2_string_ranking.json` from Task 2 (reads entry `[0]`, the single most-repeated literal); `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 1.
- Produces: `task3_alignment.json` — for the top-ranked literal, a per-byte-position invariance report covering 16 bytes before and 8 bytes after every occurrence, plus a length-prefix hypothesis check. Consumed by Task 6 for the write-up (the originally-planned Task 4 consumer was replaced — see Task 4's revision note).

- [ ] **Step 1: Write the script**

```python
"""Align byte windows immediately before/after every occurrence of the
single most-repeated string literal in TwoWorlds2Quests.eco, and report
which byte positions are invariant (candidate opcode/instruction framing)
vs variant (candidate operands) across all occurrences. Also checks
whether the byte immediately before the string equals the string's own
length - a concrete test of the length-prefixed-string hypothesis already
established elsewhere in this engine's file formats.

Run: python script/wd_extract/task3_align_top_literal.py
(depends on Task 2's task2_string_ranking.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
RANKING_PATH = Path(__file__).resolve().parent / "task2_string_ranking.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "task3_alignment.json"

BEFORE_WINDOW = 16
AFTER_WINDOW = 8


def align(data: bytes, name: str, offsets: list[int]) -> dict:
    name_len = len(name)
    before_columns: list[list[int]] = [[] for _ in range(BEFORE_WINDOW)]
    after_columns: list[list[int]] = [[] for _ in range(AFTER_WINDOW)]
    length_byte_matches = 0

    for offset in offsets:
        before_start = max(0, offset - BEFORE_WINDOW)
        before = data[before_start:offset]
        pad = BEFORE_WINDOW - len(before)
        for i, b in enumerate(before):
            before_columns[pad + i].append(b)

        after_start = offset + name_len + 1  # +1 for the null terminator
        after = data[after_start:after_start + AFTER_WINDOW]
        for i, b in enumerate(after):
            after_columns[i].append(b)

        if len(before) >= 1 and before[-1] == (name_len & 0xFF):
            length_byte_matches += 1

    def invariance_report(columns: list[list[int]]) -> list[dict]:
        report = []
        for i, col in enumerate(columns):
            if not col:
                report.append({"position": i, "samples": 0, "invariant": None})
                continue
            unique_values = sorted(set(col))
            report.append({
                "position": i,
                "samples": len(col),
                "invariant": len(unique_values) == 1,
                "values": unique_values if len(unique_values) <= 5 else
                          unique_values[:5] + ["...more"],
            })
        return report

    return {
        "name": name,
        "occurrence_count": len(offsets),
        "before_window": invariance_report(before_columns),
        "after_window": invariance_report(after_columns),
        "length_byte_hypothesis_matches": length_byte_matches,
        "length_byte_hypothesis_total": len(offsets),
    }


def main() -> None:
    assert RANKING_PATH.exists(), f"run Task 2 first to produce {RANKING_PATH}"
    ranking = json.loads(RANKING_PATH.read_text())
    top = ranking[0]
    print(f"Analyzing top literal: {top['name']!r} ({top['count']} occurrences)")

    data = ECO_PATH.read_bytes()
    result = align(data, top["name"], top["offsets"])

    print("Before-window invariance (negative position = bytes before string, "
          "-1 = byte immediately before):")
    for entry in result["before_window"]:
        rel_pos = entry["position"] - BEFORE_WINDOW
        print(f"  pos {rel_pos:+3d}: invariant={entry['invariant']} "
              f"samples={entry['samples']} values={entry.get('values')}")

    print("After-window invariance (0 = byte immediately after null terminator):")
    for entry in result["after_window"]:
        print(f"  pos {entry['position']:+3d}: invariant={entry['invariant']} "
              f"samples={entry['samples']} values={entry.get('values')}")

    print(f"Length-byte hypothesis: {result['length_byte_hypothesis_matches']}/"
          f"{result['length_byte_hypothesis_total']} occurrences have the byte "
          f"immediately before the string equal to len(name) & 0xFF")

    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"Wrote alignment analysis to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task3_align_top_literal.py`
Expected output: the analyzed literal's name and occurrence count, the before/after-window invariance report (one line per byte position), the length-byte hypothesis result, and the write-confirmation line. There is no pass/fail assertion here — report the real numbers whatever they are; whether any position turns out invariant is itself the finding.

No commit (scratch output, gitignored).

---

### Task 4: Map string-run/gap structure across the whole file

> **Revised mid-Stage-1 (2026-07-13), after Task 3's finding.** Task 3
> found that `MARKER_CHEST`'s "invariant byte before the string" is a
> trivial artifact: in all 12 occurrences, the string sits with zero gap
> immediately after a *different*, unrelated string's own NUL
> terminator. Strings are packed back-to-back with no adjacent
> opcode/framing byte at all — so continuing to align bytes immediately
> around string occurrences (the original Task 4/5 plan) would very
> likely reproduce the same trivial artifact for any literal, giving a
> false-positive "cross-validation" pass. This task replaces that
> approach: instead of aligning around individual occurrences, it maps
> the *whole file's* string-vs-non-string structure, to find where real
> bytecode (as opposed to tightly-packed string data) actually lives.

**Files:**
- Create: `script/wd_extract/task4_map_string_gaps.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task4_string_gaps.json` (gitignored)

**Interfaces:**
- Consumes: `find_null_terminated_strings` from `tw2tools.wd_format`; `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 1.
- Produces: `task4_string_gaps.json` — every consecutive pair of strings (by offset, `min_length=4`) with the byte gap between them, plus summary statistics (what fraction of pairs are back-to-back vs. separated) and the 10 largest gaps. Consumed by Task 5 (which searches the largest gaps for bytecode content) and Task 6.

- [ ] **Step 1: Write the script**

```python
"""Map string-run regions across TwoWorlds2Quests.eco: for every
null-terminated string (min_length=4) in the file, in offset order,
compute the gap (in bytes) to the next string. A gap of 0 means the
strings are packed back-to-back with no framing (as Task 3 found for
MARKER_CHEST); a gap > 0 means there's non-string content between them -
a candidate bytecode region. This determines whether the file is one
large tightly-packed string table with occasional bytecode holes, or
something else, and identifies the largest gaps for Task 5 to search.

Run: python script/wd_extract/task4_map_string_gaps.py
(depends on Task 1's eco_scripts/TwoWorlds2Quests.eco.bin)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

from tw2tools.wd_format import find_null_terminated_strings

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
OUTPUT_PATH = Path(__file__).resolve().parent / "task4_string_gaps.json"


def main() -> None:
    assert ECO_PATH.exists(), f"run Task 1 first to produce {ECO_PATH}"
    data = ECO_PATH.read_bytes()
    records = find_null_terminated_strings(data, min_length=4, max_length=256)
    records.sort(key=lambda r: r.offset)
    print(f"Total strings (min_length=4): {len(records)}")

    gaps = []
    zero_gap_count = 0
    for i in range(len(records) - 1):
        current = records[i]
        next_record = records[i + 1]
        current_end = current.offset + len(current.name) + 1  # +1 for null terminator
        gap = next_record.offset - current_end
        gaps.append({
            "index": i,
            "current_name": current.name,
            "current_offset": current.offset,
            "current_end": current_end,
            "next_name": next_record.name,
            "next_offset": next_record.offset,
            "gap": gap,
        })
        if gap == 0:
            zero_gap_count += 1

    total_pairs = len(gaps)
    print(f"Consecutive string pairs: {total_pairs}")
    print(f"Pairs with gap == 0 (back-to-back, no framing): {zero_gap_count} "
          f"({zero_gap_count / total_pairs:.1%})")

    nonzero_gaps = [g for g in gaps if g["gap"] > 0]
    print(f"Pairs with gap > 0 (candidate bytecode region): {len(nonzero_gaps)}")

    nonzero_gaps_sorted = sorted(nonzero_gaps, key=lambda g: g["gap"], reverse=True)
    print("Largest 10 gaps (candidate bytecode regions):")
    for g in nonzero_gaps_sorted[:10]:
        print(f"  gap={g['gap']:5d} bytes, between offset {g['current_end']} "
              f"(after {g['current_name']!r}) and offset {g['next_offset']} "
              f"(before {g['next_name']!r})")

    OUTPUT_PATH.write_text(json.dumps({
        "total_strings": len(records),
        "total_pairs": total_pairs,
        "zero_gap_count": zero_gap_count,
        "gaps": gaps,
    }, indent=2))
    print(f"Wrote {len(gaps)} gap records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task4_map_string_gaps.py`
Expected output: total string count, total consecutive pairs, the zero-gap count/percentage, the non-zero-gap count, and the 10 largest gaps with their offsets and neighboring string names. There is no pass/fail assertion — report the real structure, whatever it is. A high zero-gap percentage would corroborate Task 3's finding at the whole-file level (not just for `MARKER_CHEST`); the largest non-zero gaps are the most promising candidate bytecode regions for Task 5 to search.

No commit (scratch output, gitignored).

---

### Task 5: Search the largest gaps for integer references to known string offsets

**Files:**
- Create: `script/wd_extract/task5_search_gap_references.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task5_gap_references.json` (gitignored)

**Interfaces:**
- Consumes: `task2_string_ranking.json` from Task 2 (for the exact offsets of the top 2 ranked literals, `MARKER_CHEST` and `MARKER_GATE`); `task4_string_gaps.json` from Task 4 (for the 10 largest candidate-bytecode gaps); `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 1.
- Produces: `task5_gap_references.json` — for the top 5 largest gaps, every place a 4-byte little-endian integer inside that gap exactly matches one of `MARKER_CHEST`'s or `MARKER_GATE`'s known file offsets. Consumed by Task 6. Deliberately narrow (checks only two already-meaningful literals' exact offsets, as u32-LE only) rather than testing "could this byte plausibly be some index" against the full string list — a byte-range check against ~350 candidate values would match almost everything by chance and produce meaningless noise, the same class of mistake as the original min_length=1 ranking bug in Task 2.

- [ ] **Step 1: Write the script**

```python
"""Search the largest bytecode-candidate gaps (from Task 4) for u32-LE
integers that exactly match the known file offsets of the two
top-ranked repeated literals (MARKER_CHEST, MARKER_GATE from Task 2) -
testing whether bytecode elsewhere in the file references strings by
absolute offset, since Task 3 showed strings are NOT referenced by an
adjacent inline opcode.

Deliberately checks only these two literals' exact offsets (u32-LE),
not "could this byte be some plausible index into the ~350-entry string
list" - the latter would match almost any byte by chance and produce
meaningless noise.

Run: python script/wd_extract/task5_search_gap_references.py
(depends on Task 2's task2_string_ranking.json and Task 4's
task4_string_gaps.json)
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
RANKING_PATH = Path(__file__).resolve().parent / "task2_string_ranking.json"
GAPS_PATH = Path(__file__).resolve().parent / "task4_string_gaps.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "task5_gap_references.json"

TOP_N_GAPS = 5


def main() -> None:
    assert ECO_PATH.exists(), f"run Task 1 first to produce {ECO_PATH}"
    assert RANKING_PATH.exists(), f"run Task 2 first to produce {RANKING_PATH}"
    assert GAPS_PATH.exists(), f"run Task 4 first to produce {GAPS_PATH}"
    data = ECO_PATH.read_bytes()
    ranking = json.loads(RANKING_PATH.read_text())
    gap_data = json.loads(GAPS_PATH.read_text())

    target_offsets: dict[int, str] = {}
    for entry in ranking[:2]:  # MARKER_CHEST and MARKER_GATE
        for offset in entry["offsets"]:
            target_offsets[offset] = entry["name"]
    print(f"Searching for {len(target_offsets)} known offsets "
          f"(from {[e['name'] for e in ranking[:2]]})")

    nonzero_gaps = [g for g in gap_data["gaps"] if g["gap"] > 0]
    top_gaps = sorted(nonzero_gaps, key=lambda g: g["gap"], reverse=True)[:TOP_N_GAPS]

    results = []
    for gap in top_gaps:
        start = gap["current_end"]
        end = gap["next_offset"]
        gap_bytes = data[start:end]
        print(f"\nGap at {start}..{end} ({len(gap_bytes)} bytes), "
              f"between {gap['current_name']!r} and {gap['next_name']!r}:")

        hits = []
        for pos in range(max(0, len(gap_bytes) - 3)):
            (value,) = struct.unpack_from("<I", gap_bytes, pos)
            if value in target_offsets:
                hits.append({
                    "gap_relative_pos": pos,
                    "absolute_pos": start + pos,
                    "value": value,
                    "matches_string": target_offsets[value],
                })
        print(f"  Offset-reference hits (u32-LE matching a known string offset): "
              f"{len(hits)}")
        for hit in hits:
            print(f"    at {hit['absolute_pos']}: value={hit['value']} "
                  f"-> {hit['matches_string']!r}")

        results.append({
            "gap_start": start,
            "gap_end": end,
            "gap_size": len(gap_bytes),
            "before_string": gap["current_name"],
            "after_string": gap["next_name"],
            "hits": hits,
        })

    total_hits = sum(len(r["hits"]) for r in results)
    print(f"\nTotal offset-reference hits across top {TOP_N_GAPS} gaps: {total_hits}")

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"Wrote gap-reference search results to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task5_search_gap_references.py`
Expected output: the number of target offsets being searched for, each of the top 5 gaps with its size and location, the offset-reference hit count for each gap (with details for any hits found), and a total hit count across all 5 gaps. No pass/fail assertion — a hit count of 0 is a valid, reportable negative result, same as every other correlation search in this project's history.

No commit (scratch output, gitignored).

---

### Task 6: Write up Checkpoint 1 findings and commit

**Files:**
- Modify: `script/wd_extraction_notes.md` (append a new dated section at the end of the file)

**Interfaces:**
- Consumes: printed output and JSON files from Tasks 1-5 (`eco_scripts/`, `task2_string_ranking.json`, `task3_alignment.json`, `task4_string_gaps.json`, `task5_gap_references.json`), plus the corrected Task 3 report (`.superpowers/sdd/task-3-report.md`) for the exact hex/offset evidence behind the "trivial artifact" finding.
- Produces: the durable, permanent record of Checkpoint 1's outcome.

- [ ] **Step 1: Decide the outcome bucket**

- **Positive finding (confident offset-reference mechanism found):** Task 5 found at least one genuine u32-LE hit — a gap region containing an integer that exactly matches `MARKER_CHEST`'s or `MARKER_GATE`'s real file offset. This is concrete, non-coincidental evidence that bytecode references strings by absolute file offset.
- **Negative/inconclusive finding:** Task 5 found zero hits across the top 5 gaps. This does not mean the offset-reference hypothesis is false — only that this specific, narrow test (raw u32-LE absolute offsets, in the 5 largest gaps) didn't confirm it. Other encodings (relative offsets, a separate index table, hashed lookups) remain possible and are explicitly out of scope for this plan.

Either way, Task 3's real structural finding (strings packed back-to-back with no adjacent opcode — confirmed for all 12 `MARKER_CHEST` occurrences) and Task 4's whole-file gap statistics are durable, reportable results in their own right, independent of Task 5's outcome.

- [ ] **Step 2: Append the appropriate section to `script/wd_extraction_notes.md`**

Append at the very end of the file (after the existing "Resumed: exploratory bytecode pass (2026-07-13)" section from the prior investigation), using this structure. Fill in every bracketed `[...]` placeholder with the actual data read from the JSON files in Step 1 — do not leave any bracket unresolved.

For a **positive finding**:

```markdown
## Bytecode decoder, Stage 1 (2026-07-13) — [one-line result summary]

Began the general-purpose `.eco` disassembler project (see
`docs/superpowers/specs/2026-07-13-eco-bytecode-decoder-design.md`),
staged with checkpoints. Stage 1 (format discovery) originally planned
to align bytes immediately around repeated string occurrences, but
pivoted mid-stage after an unexpected finding (below) made that
approach unsound.

**Method and pivot:** ranked the most-repeated literals in
`TwoWorlds2Quests.eco` (top: `[insert Task 2's #1 literal name]` at
`[insert count]` occurrences, second: `[insert Task 2's #2 literal
name]` at `[insert count]` occurrences). Aligning bytes around every
occurrence of the top literal found one invariant byte (`0x00`
immediately before the string, all 12/12 occurrences) - but inspecting
the byte *before that* showed a printable ASCII character in all 12
cases, the tail of a different, unrelated preceding string each time
(examples: `translateGROUP_%d`, `translateQ_%d`, `QLINV`, `LLvl`,
`PrintContainers`). **This means the strings are packed back-to-back
with zero gap and no adjacent opcode/framing byte at all** - the
"invariant byte" was just the preceding string's own NUL terminator,
not an instruction. Continuing to align around individual occurrences
would not find a real instruction shape this way.

Pivoted to mapping the file's actual string-vs-bytecode structure
instead: of `[insert total_pairs]` consecutive string pairs across the
whole file, `[insert zero_gap_count]` (`[insert percentage]`) are
back-to-back with no gap, confirming the tight-packing finding holds
file-wide, not just for one literal. The `[insert nonzero gap count]`
gaps with actual content between strings are the candidate bytecode
regions; the largest was `[insert largest gap size]` bytes, between
`[insert neighboring string names/offsets]`.

**Finding:** searching the 5 largest gaps for u32-LE integers matching
`[insert Task 2's #1 literal]`'s or `[insert Task 2's #2 literal]`'s
exact file offsets found `[insert total hit count]` hit(s):
`[insert hit details - which gap, what offset, what value, which
string it matched]`.

**Interpretation:** [one to two sentences on what this confirms - e.g.
bytecode references strings by absolute file offset via a 4-byte
little-endian integer, found at `[location]`].

**Next step (Checkpoint 1 decision, pending):** this offset-reference
mechanism is a plausible anchor for Stage 2 (finding the instruction
that consumes this offset and what it does with it). Not proceeding
automatically - this write-up is the Checkpoint 1 deliverable for
review before deciding whether/how to continue.
```

For a **negative/inconclusive finding**:

```markdown
## Bytecode decoder, Stage 1 (2026-07-13) — inconclusive, but with a real structural finding

Began the general-purpose `.eco` disassembler project (see
`docs/superpowers/specs/2026-07-13-eco-bytecode-decoder-design.md`),
staged with checkpoints. Stage 1 (format discovery) originally planned
to align bytes immediately around repeated string occurrences, but
pivoted mid-stage after an unexpected finding made that approach
unsound - the pivot itself is a real, useful result even though the
follow-on search came up empty.

**Method and pivot:** ranked the most-repeated literals in
`TwoWorlds2Quests.eco` (top: `[insert Task 2's #1 literal name]` at
`[insert count]` occurrences, second: `[insert Task 2's #2 literal
name]` at `[insert count]` occurrences). Aligning bytes around every
occurrence of the top literal found one invariant byte (`0x00`
immediately before the string, all 12/12 occurrences) - but inspecting
the byte *before that* showed a printable ASCII character in all 12
cases, the tail of a different, unrelated preceding string each time
(examples: `translateGROUP_%d`, `translateQ_%d`, `QLINV`, `LLvl`,
`PrintContainers`). **This means the strings are packed back-to-back
with zero gap and no adjacent opcode/framing byte at all** - the
"invariant byte" was just the preceding string's own NUL terminator,
not an instruction.

Pivoted to mapping the file's actual string-vs-bytecode structure
instead: of `[insert total_pairs]` consecutive string pairs across the
whole file, `[insert zero_gap_count]` (`[insert percentage]`) are
back-to-back with no gap, confirming the tight-packing finding holds
file-wide, not just for one literal. The `[insert nonzero gap count]`
gaps with actual content between strings are the candidate bytecode
regions; the largest 10 ranged from `[insert smallest of the top 10]`
to `[insert largest]` bytes.

**What was tried:** searched the 5 largest gaps for u32-LE integers
matching `[insert Task 2's #1 literal]`'s or `[insert Task 2's #2
literal]`'s exact file offsets - `[insert total hit count, likely 0]`
hits found.

**Why this didn't resolve the question:** a raw absolute-offset u32-LE
scan of only the 5 largest gaps, for only 2 literals' offsets, is a
narrow test. It does not rule out: relative (rather than absolute)
offset encoding, a separate index/lookup table elsewhere in the file,
smaller gaps also containing real references, or a different integer
width/endianness.

**Stopping point for Stage 1 (2026-07-13).** The real, confirmed
finding from this stage is structural: `TwoWorlds2Quests.eco`'s string
constants are packed in a tight, framing-free run with no opcode
adjacent to them - any bytecode referencing a string must do so from
elsewhere in the file, not inline. The follow-on search for an absolute
offset reference in the largest gaps did not confirm a specific
mechanism. Continuing would need either widening the offset/index
search (more gaps, relative offsets, other integer widths) or a
different technique entirely (e.g. examining the *content* of a large
gap directly for recognizable structure, rather than searching it for
known offset values) - a new planning decision, not an automatic
continuation. Future starting point: `[insert the most promising
partial lead, e.g. the specific gap that looked most bytecode-like on
inspection, or any near-miss integer values noticed]`.
```

- [ ] **Step 3: Run the test suite to confirm nothing broke**

Run: `python -m pytest script/tests/ -v`
Expected: all 50 tests still pass (no `tw2tools`/`tests` changes are expected in this plan, so this should be unaffected — run it anyway as a final sanity check before committing).

- [ ] **Step 4: Commit**

```bash
git add script/wd_extraction_notes.md
git commit -m "Record Checkpoint 1 outcome of .eco bytecode decoder Stage 1"
```

---

## Self-Review

**Spec coverage:** Task 1 re-establishes the extraction the prior investigation's now-deleted worktree left behind. Task 2 (corrected to `min_length=4` mid-execution, after an initial run surfaced single-character bytecode noise as "most repeated") and Task 3 implement the design's "Stage 1 methodology" (rank literals, align the top one). **Tasks 4 and 5 were revised mid-execution** after Task 3's real finding — strings are packed back-to-back with no adjacent opcode, so the original "align a second literal and cross-check" plan would have produced a false-positive agreement on the same trivial artifact. The revised Task 4 maps the whole file's string/gap structure instead, and the revised Task 5 searches the largest gaps for absolute-offset references to already-known string offsets — a different but still design-faithful way of pursuing "find the byte-level shape of at least one instruction," now aimed at how bytecode *references* a string rather than what precedes it inline. Task 6 implements the design's "Checkpoint 1 deliverable," updated to report both the pivot and its outcome. The design's "no commitment beyond reaching the next checkpoint" is reflected in this plan covering Stage 1 only, with Stage 2/3 explicitly out of scope pending review of Task 6's write-up.

**Placeholder scan:** The only bracketed `[...]` placeholders are in Task 6's two write-up templates, which is inherent to reporting a genuinely unknown research outcome — not a deferred engineering decision. Every other task has complete, runnable code with concrete expected output.

**Type consistency:** Task 3's `align()` signature and return shape are self-contained to Task 3 (no longer consumed by Task 4, since Task 4 was redesigned around gap-mapping instead of a second alignment pass — Task 3's JSON is still read by Task 6 for the write-up). Task 4's gap records (`current_name`, `current_offset`, `current_end`, `next_name`, `next_offset`, `gap`) are consumed correctly by Task 5 (reads `gap_data["gaps"]`, filters `gap > 0`, sorts by `gap` descending). Task 5's `target_offsets` dict (built from Task 2's ranking entries `[0]` and `[1]`) and its output shape (`gap_start`, `gap_end`, `gap_size`, `before_string`, `after_string`, `hits`) are used consistently in Task 6's decision criteria.
