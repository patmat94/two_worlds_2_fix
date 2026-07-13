# `.eco` Bytecode Decoder — Stage 1 (Format Discovery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Find the byte-level shape of at least one `.eco` bytecode instruction — most likely "reference a string constant" — by aligning bytes immediately surrounding every occurrence of the same repeated literal string, then cross-validating the pattern against a second literal and (if possible) a second script. This is Stage 1 of a 3-stage, checkpointed disassembler project (see the design doc); this plan covers **only** Stage 1, through Checkpoint 1.

**Architecture:** One tested `tw2tools` re-extraction step (reusing the already-tested `extract_eco_files_from_wd_archive`), followed by four scratch analysis scripts under `script/wd_extract/` (gitignored, not committed) that progressively rank, align, and cross-check byte patterns, ending in one write-up commit to `script/wd_extraction_notes.md`.

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
    records = find_null_terminated_strings(data, min_length=1, max_length=256)
    print(f"Total strings found: {len(records)}")

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
Expected output: total string count (should be 3,122 per the prior investigation's Task 4 finding — if it differs, note the discrepancy but continue, since the extraction method is unchanged and this may just reflect noticing a detail missed before), the top-20 list with counts, and "Ground-truth sanity check passed."

No commit (scratch output, gitignored).

---

### Task 3: Align byte windows around the single most-repeated literal

**Files:**
- Create: `script/wd_extract/task3_align_top_literal.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task3_alignment.json` (gitignored)

**Interfaces:**
- Consumes: `task2_string_ranking.json` from Task 2 (reads entry `[0]`, the single most-repeated literal); `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 1.
- Produces: `task3_alignment.json` — for the top-ranked literal, a per-byte-position invariance report covering 16 bytes before and 8 bytes after every occurrence, plus a length-prefix hypothesis check. Consumed by Tasks 4 and 6.

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

### Task 4: Align the second-most-repeated literal and cross-check against Task 3

**Files:**
- Create: `script/wd_extract/task4_align_second_literal.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task4_alignment.json` (gitignored)

**Interfaces:**
- Consumes: `task2_string_ranking.json` from Task 2 (reads entry `[1]`, the second most-repeated literal); `task3_alignment.json` from Task 3; `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 1.
- Produces: `task4_alignment.json` (same shape as Task 3's output, for the second literal) plus a printed position-by-position comparison against Task 3's result. Consumed by Task 6. This is the key **within-file cross-validation** step: agreement between two independent, different literals is the strongest signal Stage 1 can produce without leaving this one file.

- [ ] **Step 1: Write the script**

```python
"""Repeat Task 3's byte-alignment analysis for the SECOND most-repeated
string literal in TwoWorlds2Quests.eco, then compare its invariant-byte
pattern against Task 3's result. Agreement across two different,
independent literals - not just one - is the key cross-validation signal
for Stage 1's format-discovery claim.

Run: python script/wd_extract/task4_align_second_literal.py
(depends on Task 2's task2_string_ranking.json and Task 3's
task3_alignment.json)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
RANKING_PATH = Path(__file__).resolve().parent / "task2_string_ranking.json"
TASK3_PATH = Path(__file__).resolve().parent / "task3_alignment.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "task4_alignment.json"

BEFORE_WINDOW = 16
AFTER_WINDOW = 8


def align(data: bytes, name: str, offsets: list[int]) -> dict:
    # Identical logic to Task 3's align() - duplicated deliberately since
    # these are independent scratch scripts, not a shared tw2tools module.
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

        after_start = offset + name_len + 1
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
    assert TASK3_PATH.exists(), f"run Task 3 first to produce {TASK3_PATH}"
    ranking = json.loads(RANKING_PATH.read_text())
    assert len(ranking) >= 2, "need at least 2 ranked literals to cross-validate"
    second = ranking[1]
    print(f"Analyzing second literal: {second['name']!r} ({second['count']} occurrences)")

    data = ECO_PATH.read_bytes()
    result = align(data, second["name"], second["offsets"])
    task3_result = json.loads(TASK3_PATH.read_text())

    print("Before-window invariance:")
    for entry in result["before_window"]:
        rel_pos = entry["position"] - BEFORE_WINDOW
        print(f"  pos {rel_pos:+3d}: invariant={entry['invariant']} "
              f"values={entry.get('values')}")

    print(f"Comparing invariant positions against Task 3's literal "
          f"({task3_result['name']!r}):")
    agreement_positions = []
    for i, (a, b) in enumerate(zip(task3_result["before_window"], result["before_window"])):
        rel_pos = i - BEFORE_WINDOW
        if a["invariant"] and b["invariant"]:
            same_value = a["values"] == b["values"]
            print(f"  before pos {rel_pos:+3d}: both invariant, "
                  f"same value={same_value} (task3={a['values']}, task4={b['values']})")
            if same_value:
                agreement_positions.append(rel_pos)
        elif a["invariant"] or b["invariant"]:
            print(f"  before pos {rel_pos:+3d}: invariant in only one of the two "
                  f"literals (task3_invariant={a['invariant']}, "
                  f"task4_invariant={b['invariant']})")

    print(f"Positions invariant with matching values in BOTH literals: {agreement_positions}")

    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    print(f"Wrote alignment analysis to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task4_align_second_literal.py`
Expected output: the second literal's analysis (same shape as Task 3's), the position-by-position comparison against Task 3, and a final line listing which positions (if any) are invariant with matching values in both literals — this list is the core evidence Task 6 will use to decide Stage 1's outcome.

No commit (scratch output, gitignored).

---

### Task 5: Cross-validate against `RPGCompute.eco` if a shared literal exists

**Files:**
- Create: `script/wd_extract/task5_cross_script_validate.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task5_cross_script.json` (gitignored)

**Interfaces:**
- Consumes: `find_null_terminated_strings` from `tw2tools.wd_format`; `eco_scripts/RPGCompute.eco.bin` from Task 1; `task3_alignment.json` and `task4_alignment.json` (for the two literal names to look for).
- Produces: `task5_cross_script.json` — if either of Tasks 3/4's literals also appears in `RPGCompute.eco`, its alignment analysis there (same shape as Task 3/4's). If neither literal is shared, an empty result with a clear printed explanation. Consumed by Task 6. **A shared literal not being found is a valid, reportable outcome, not a failure** — the design's Stage 1 success criterion rests on Tasks 3/4's within-file agreement; this task only adds corroborating evidence when possible.

- [ ] **Step 1: Write the script**

```python
"""Check whether RPGCompute.eco (the most string-rich script after
TwoWorlds2Quests, with 1,045 strings) shares either of the literals
analyzed in Tasks 3/4. If so, repeat the byte-alignment analysis there
and compare against the TwoWorlds2Quests pattern - agreement across two
independently compiled scripts is strong corroborating evidence of a
real, general instruction shape. If no shared literal exists, that is a
valid, reportable outcome, not a failure of this task.

Run: python script/wd_extract/task5_cross_script_validate.py
(depends on Task 1's eco_scripts/RPGCompute.eco.bin and Tasks 3/4's
alignment JSON files)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

from tw2tools.wd_format import find_null_terminated_strings

RPGCOMPUTE_PATH = Path(__file__).resolve().parent / "eco_scripts" / "RPGCompute.eco.bin"
TASK3_PATH = Path(__file__).resolve().parent / "task3_alignment.json"
TASK4_PATH = Path(__file__).resolve().parent / "task4_alignment.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "task5_cross_script.json"

BEFORE_WINDOW = 16
AFTER_WINDOW = 8


def align(data: bytes, name: str, offsets: list[int]) -> dict:
    # Identical logic to Task 3/4's align() - duplicated deliberately, see
    # those tasks for the rationale.
    name_len = len(name)
    before_columns: list[list[int]] = [[] for _ in range(BEFORE_WINDOW)]
    after_columns: list[list[int]] = [[] for _ in range(AFTER_WINDOW)]

    for offset in offsets:
        before_start = max(0, offset - BEFORE_WINDOW)
        before = data[before_start:offset]
        pad = BEFORE_WINDOW - len(before)
        for i, b in enumerate(before):
            before_columns[pad + i].append(b)

        after_start = offset + name_len + 1
        after = data[after_start:after_start + AFTER_WINDOW]
        for i, b in enumerate(after):
            after_columns[i].append(b)

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
    }


def main() -> None:
    assert RPGCOMPUTE_PATH.exists(), f"run Task 1 first to produce {RPGCOMPUTE_PATH}"
    assert TASK3_PATH.exists() and TASK4_PATH.exists(), "run Tasks 3 and 4 first"

    task3_result = json.loads(TASK3_PATH.read_text())
    task4_result = json.loads(TASK4_PATH.read_text())
    candidate_names = [task3_result["name"], task4_result["name"]]

    data = RPGCOMPUTE_PATH.read_bytes()
    records = find_null_terminated_strings(data, min_length=1, max_length=256)
    print(f"RPGCompute.eco: {len(records)} total strings")

    offsets_by_name: dict[str, list[int]] = {}
    for r in records:
        offsets_by_name.setdefault(r.name, []).append(r.offset)

    shared = [name for name in candidate_names if name in offsets_by_name]
    print(f"Literals shared with TwoWorlds2Quests analysis: {shared}")

    results = {}
    if not shared:
        print(
            "No shared literal found between RPGCompute and the two literals "
            "analyzed in Tasks 3/4 - cross-script validation not possible with "
            "these specific literals. This is a valid, reportable outcome, not "
            "a failure."
        )
    else:
        for name in shared:
            offsets = offsets_by_name[name]
            print(f"Aligning {len(offsets)} occurrences of {name!r} in RPGCompute...")
            result = align(data, name, offsets)
            results[name] = result
            for entry in result["before_window"]:
                rel_pos = entry["position"] - BEFORE_WINDOW
                print(f"  before pos {rel_pos:+3d}: invariant={entry['invariant']} "
                      f"values={entry.get('values')}")

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"Wrote cross-script validation to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task5_cross_script_validate.py`
Expected output: RPGCompute's total string count, which (if any) of Tasks 3/4's literals it shares, and either the alignment analysis for each shared literal or the explicit "no shared literal" explanation. Both outcomes are valid — report whichever actually happens.

No commit (scratch output, gitignored).

---

### Task 6: Write up Checkpoint 1 findings and commit

**Files:**
- Modify: `script/wd_extraction_notes.md` (append a new dated section at the end of the file)

**Interfaces:**
- Consumes: printed output and JSON files from Tasks 1-5 (`eco_scripts/`, `task2_string_ranking.json`, `task3_alignment.json`, `task4_alignment.json`, `task5_cross_script.json`).
- Produces: the durable, permanent record of Checkpoint 1's outcome.

- [ ] **Step 1: Decide the outcome bucket**

Read `task4_alignment.json`'s printed comparison output (or re-derive it from the JSON files) for the "positions invariant with matching values in BOTH literals" result from Task 4:

- **Positive finding (confident instruction shape found):** at least one byte position (in the before-window or after-window) is invariant with the *same* value across **both** literals analyzed in Tasks 3 and 4. This is genuine, non-coincidental evidence of a real instruction shape, independent of whether Task 5's cross-script check also confirms it.
- **Negative/inconclusive finding:** no position is invariant with matching values across both literals — even if one literal alone shows some invariant positions, that alone isn't enough (a single literal's invariant framing could just be a coincidence of that one string's usage pattern, not a general instruction shape).

- [ ] **Step 2: Append the appropriate section to `script/wd_extraction_notes.md`**

Append at the very end of the file (after the existing "Resumed: exploratory bytecode pass (2026-07-13)" section from the prior investigation), using this structure. Fill in every bracketed `[...]` placeholder with the actual data read from the JSON files in Step 1 — do not leave any bracket unresolved.

For a **positive finding**:

```markdown
## Bytecode decoder, Stage 1 (2026-07-13) — [one-line result summary]

Began the general-purpose `.eco` disassembler project (see
`docs/superpowers/specs/2026-07-13-eco-bytecode-decoder-design.md`),
staged with checkpoints. Stage 1 (format discovery) used
repeated-literal byte alignment: since `TwoWorlds2Quests.eco`'s string
constants are not deduplicated, the same literal appears many times at
known byte offsets, giving many known-identical-purpose landmarks to
align bytes around.

**Method:** ranked the most-repeated literals in `TwoWorlds2Quests.eco`
(top: `[insert Task 2's #1 literal name]` at `[insert count]` occurrences,
second: `[insert Task 2's #2 literal name]` at `[insert count]`
occurrences), then aligned a 16-byte-before/8-byte-after window around
every occurrence of each, checking which byte positions hold identical
values across all repeats.

**Finding:** byte position `[insert the agreed position, e.g. -1 or +0]`
relative to the string is invariant with the same value
(`[insert the actual byte value]`) across both literals analyzed
(`[insert Task 3's literal]` and `[insert Task 4's literal]`) —
`[insert occurrence counts for each]` combined data points. [State
whether the length-byte hypothesis from Task 3/4 also held:
insert the matches/total ratio and whether it corroborates or
contradicts the found invariant byte]. [If Task 5 found a shared
literal in `RPGCompute.eco`: state whether the same position/value held
there too, strengthening the finding into a cross-script-confirmed
result. If no shared literal was found, say so plainly.]

**Interpretation:** [one to two sentences on what this invariant byte
likely represents given its position and value - e.g. an opcode for
"load string constant," given it always precedes the string].

**Next step (Checkpoint 1 decision, pending):** this instruction shape
is a plausible anchor for Stage 2 (opcode-table expansion around known
call sites). Not proceeding automatically — this write-up is the
Checkpoint 1 deliverable for review before deciding whether/how to
continue.
```

For a **negative/inconclusive finding**:

```markdown
## Bytecode decoder, Stage 1 (2026-07-13) — inconclusive

Began the general-purpose `.eco` disassembler project (see
`docs/superpowers/specs/2026-07-13-eco-bytecode-decoder-design.md`),
staged with checkpoints. Stage 1 (format discovery) used
repeated-literal byte alignment: since `TwoWorlds2Quests.eco`'s string
constants are not deduplicated, the same literal appears many times at
known byte offsets, giving many known-identical-purpose landmarks to
align bytes around.

**Method:** ranked the most-repeated literals in `TwoWorlds2Quests.eco`
(top: `[insert Task 2's #1 literal name]` at `[insert count]` occurrences,
second: `[insert Task 2's #2 literal name]` at `[insert count]`
occurrences), then aligned a 16-byte-before/8-byte-after window around
every occurrence of each.

**What was tried:** [insert what invariant positions (if any) were found
for each literal individually from Tasks 3/4's output, and why they
didn't agree between the two - e.g. different positions were invariant
for each literal, or no position was invariant for either]. [Insert
the length-byte hypothesis result: matches/total for each literal].
[Insert Task 5's result: whether a shared literal with RPGCompute
existed and what its alignment showed, or that no shared literal was
found at all].

**Why this didn't converge:** [insert the concrete blocker, e.g. "the
bytes immediately surrounding string references vary too much even
between repeats of the identical literal, suggesting either variable-
width framing that the fixed 16/8-byte window doesn't capture correctly,
or that string references aren't encoded via a simple fixed-position
opcode+length pattern"].

**Stopping point for Stage 1 (2026-07-13).** This does not resolve to a
confident instruction shape via this technique. Continuing would need
either a different technique (e.g. statistical/entropy analysis across
the whole file, or aligning on a much larger sample of literals rather
than just the top 2) or accepting a wider/variable alignment window -
either is a new planning decision, not an automatic continuation.
Future starting point: `[insert the most promising partial lead, e.g.
a position that was invariant for one literal even if not both, or an
observation from the length-byte hypothesis worth revisiting]`.
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

**Spec coverage:** Task 1 re-establishes the extraction the prior investigation's now-deleted worktree left behind. Tasks 2-4 implement the design's "Stage 1 methodology" section (rank literals, align the top one, cross-validate against the second). Task 5 implements the design's "cross-validate ... against a second script ... if it shares any of the same literals" — explicitly optional/best-effort per the design's own wording, and the task is written to treat a negative result as valid rather than a failure. Task 6 implements the design's "Checkpoint 1 deliverable." The design's "no commitment beyond reaching the next checkpoint" is reflected in this plan covering Stage 1 only, with Stage 2/3 explicitly out of scope pending review of Task 6's write-up.

**Placeholder scan:** The only bracketed `[...]` placeholders are in Task 6's two write-up templates, which is inherent to reporting a genuinely unknown research outcome — not a deferred engineering decision. Every other task has complete, runnable code with concrete expected output.

**Type consistency:** `align()`'s signature (`data: bytes, name: str, offsets: list[int]) -> dict`) and its returned dict shape (`name`, `occurrence_count`, `before_window`, `after_window`, plus `length_byte_hypothesis_*` in Tasks 3/4 only) are used consistently everywhere they're read (Task 4 reads Task 3's JSON shape correctly; Task 6's decision criteria reference the exact fields Task 4 prints). `BEFORE_WINDOW`/`AFTER_WINDOW` (16/8) are consistent across Tasks 3, 4, and 5.
