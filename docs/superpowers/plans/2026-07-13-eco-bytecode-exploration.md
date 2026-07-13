# `.eco` Bytecode Exploratory Disassembly — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a single time-boxed exploratory pass over the compiled `.eco` bytecode to find (or conclusively rule out, within this pass) the byte-level mechanism that drives `QUEST_SOLVED` for the Gods and Demons quest tied to Casbrim, then stop and record the result — positive or negative.

**Architecture:** Two small, stable primitives get added to `tw2tools` with real TDD (a corrected two-stage `.eco` extraction routine, and a fixed null-terminated string scanner). Everything after that is a sequence of scratch analysis scripts under `script/wd_extract/` (gitignored, not committed) that progressively narrow from raw string anchors down to a specific byte-level correlation against the already-confirmed `PCQ` values, ending in one write-up commit to `script/wd_extraction_notes.md`.

**Tech Stack:** Python 3 stdlib only (`struct`, `zlib`, `json`, `pathlib`), pytest, the existing `tw2tools` package.

## Global Constraints

- **Binary-output discipline (standing project rule):** never dump raw bytecode or binary content directly into the conversation. Every task that inspects real bytes writes output to a file under `script/wd_extract/` and reads back only small, bounded excerpts (a hex window, an offset list, a JSON summary) — never the whole extracted file.
- **`script/wd_extract/` is gitignored.** Scratch scripts and their output files placed there are intentionally **not** committed. Only changes to `script/tw2tools/`, `script/tests/`, and `script/wd_extraction_notes.md` get committed.
- **This is one time-boxed pass.** Stop after Task 8 regardless of outcome. Do not escalate into general opcode-table construction or a full disassembler — that would require a new, separate planning decision.
- **All existing tests must keep passing.** The suite was at 43 passing tests as of 2026-07-11; verify it's still green after each `tw2tools` change.
- **Real data path:** `files/Two Worlds 2/DLC3_PC.wd` (~1.9GB, gitignored, read-only). Full-archive decompression takes roughly 20–30 seconds (confirmed in prior work: ~20s for 22,318 blocks).
- **Ground truth to verify against** (from `script/wd_extraction_notes.md`, already confirmed in prior sessions — use these as correctness checks, not things to re-derive): exactly 21 real `.eco` files exist in `DLC3_PC.wd`; `TwoWorlds2Quests.eco` is exactly 179,340 bytes; the literal string `PCQ` occurs exactly twice in `TwoWorlds2Quests.eco`; `QUEST_GIVEN` and `QUEST_SOLVED` are present as literal (non-template) strings; `Q_45` / `GROUP_2` are the confirmed localization IDs for the Gods and Demons quest.

---

### Task 1: Add `extract_eco_files_from_wd_archive` to `tw2tools` (TDD)

**Files:**
- Modify: `script/tw2tools/wd_format.py`
- Test: `script/tests/test_wd_format.py`

**Interfaces:**
- Consumes: existing `decompress_all_blocks(data: bytes) -> Iterator[tuple[int, bytes]]`, `find_eco_files(data: bytes) -> list[EcoFile]`, `ECO_MAGIC` constant, and the existing `_build_eco_file(name, body=b"") -> bytes` test helper — all already defined in the current files.
- Produces: `extract_eco_files_from_wd_archive(wd_data: bytes) -> list[EcoFile]` — this is what Task 2's script calls to get correctly-bounded real `.eco` files from the raw archive. (Fixes a real gap: `find_eco_files` alone cannot be safely called on a raw multi-GB archive, because its magic header only appears inside *decompressed* zlib blocks, and each `.eco` file is stored as its own independent zlib block — so the correct extraction is "decompress every block, then check which decompressed blocks start with the magic.")

- [ ] **Step 1: Write the failing test**

Add to `script/tests/test_wd_format.py` (near the other `find_eco_files` tests):

```python
def test_extract_eco_files_from_wd_archive_finds_compressed_eco_blocks():
    eco_a = _build_eco_file("ScriptA", b"bytecodeA")
    eco_b = _build_eco_file("ScriptB", b"bytecodeB" * 5)
    decoy = b"just some archive metadata, not an eco file"
    wd_data = zlib.compress(eco_a) + zlib.compress(decoy) + zlib.compress(eco_b)

    results = extract_eco_files_from_wd_archive(wd_data)

    assert {r.name for r in results} == {"ScriptA", "ScriptB"}
    by_name = {r.name: r for r in results}
    assert by_name["ScriptA"].data == eco_a
    assert by_name["ScriptB"].data == eco_b


def test_extract_eco_files_from_wd_archive_returns_empty_list_when_none_present():
    wd_data = zlib.compress(b"nothing eco-shaped here")
    assert extract_eco_files_from_wd_archive(wd_data) == []
```

Update the import line near the top of the test file to include the new
function:

```python
from tw2tools.wd_format import decompress_all_blocks, find_zlib_offsets, parse_archive_entries, search_text_multi, diff_byte_regions, parse_save_summary, find_named_records, parse_property_bags, patch_zlib_block, find_eco_files, extract_eco_files_from_wd_archive
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest script/tests/test_wd_format.py -v -k extract_eco_files_from_wd_archive`
Expected: FAIL — `ImportError: cannot import name 'extract_eco_files_from_wd_archive'`

- [ ] **Step 3: Write minimal implementation**

Add to `script/tw2tools/wd_format.py`, directly after the existing
`find_eco_files` function:

```python
def extract_eco_files_from_wd_archive(wd_data: bytes) -> list[EcoFile]:
    results: list[EcoFile] = []
    for _offset, block in decompress_all_blocks(wd_data):
        if block.startswith(ECO_MAGIC):
            found = find_eco_files(block)
            if found:
                results.append(found[0])
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest script/tests/test_wd_format.py -v -k extract_eco_files_from_wd_archive`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full test suite to confirm nothing broke**

Run: `python -m pytest script/tests/ -v`
Expected: all tests pass (45 passed — the 43 existing plus the 2 new ones)

- [ ] **Step 6: Commit**

```bash
git add script/tw2tools/wd_format.py script/tests/test_wd_format.py
git commit -m "Add extract_eco_files_from_wd_archive for correct two-stage .eco extraction"
```

---

### Task 2: Run the corrected extraction against the real archive

**Files:**
- Create: `script/wd_extract/task2_extract_all_eco.py` (gitignored scratch — not committed)
- Creates on run: `script/wd_extract/eco_scripts/*.eco.bin` (21 files, gitignored)

**Interfaces:**
- Consumes: `extract_eco_files_from_wd_archive` from Task 1.
- Produces: individual `.eco.bin` files under `script/wd_extract/eco_scripts/`, consumed by Tasks 4, 5, and 6. Filenames are the sanitized script name plus `.eco.bin` (e.g. `TwoWorlds2Quests.eco.bin`).

- [ ] **Step 1: Write the script**

```python
"""Extract all real .eco scripts from DLC3_PC.wd using the correct
decompress-then-detect method (see Task 1). Scratch script (gitignored) -
run once from the repo root:

    python script/wd_extract/task2_extract_all_eco.py
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
    print(f"Reading {WD_PATH} ...")
    data = WD_PATH.read_bytes()
    print(
        f"Read {len(data)} bytes, scanning for .eco files "
        f"(decompresses the full archive - expect ~20-30 seconds)..."
    )
    eco_files = extract_eco_files_from_wd_archive(data)
    print(f"Found {len(eco_files)} .eco files")

    for eco in eco_files:
        out_path = OUTPUT_DIR / f"{sanitize(eco.name)}.eco.bin"
        out_path.write_bytes(eco.data)
        print(f"  {eco.name!r}: {len(eco.data)} bytes -> {out_path.name}")

    assert len(eco_files) == 21, (
        f"expected exactly 21 .eco files per prior findings, got {len(eco_files)}"
    )
    quests = [e for e in eco_files if e.name == "TwoWorlds2Quests"]
    assert len(quests) == 1, (
        f"expected exactly one TwoWorlds2Quests, got {len(quests)}"
    )
    assert len(quests[0].data) == 179340, (
        f"expected TwoWorlds2Quests.eco to be 179340 bytes, got {len(quests[0].data)}"
    )
    print("All ground-truth assertions passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task2_extract_all_eco.py`
Expected output: a line "Found 21 .eco files", 21 listed names/sizes, and
finally "All ground-truth assertions passed." If any assertion fails, stop
and investigate before continuing to Task 3 — it means either the archive
changed or the extraction logic has a bug, and every later task depends on
these files being correct.

No commit for this step (scratch output, gitignored).

---

### Task 3: Add `find_null_terminated_strings` to `tw2tools` (TDD)

**Files:**
- Modify: `script/tw2tools/wd_format.py`
- Test: `script/tests/test_wd_format.py`

**Interfaces:**
- Consumes: existing `NamedRecord` dataclass (`offset: int`, `name: str`) — reused as-is, no changes needed to it.
- Produces: `find_null_terminated_strings(data: bytes, min_length: int = 1, max_length: int = 256) -> list[NamedRecord]`, used by Tasks 4, 5, and 6. This replaces the buggy ad-hoc `[ -~]{4,}\x00` regex documented in `wd_extraction_notes.md` (which silently dropped the 3-character string `"PCQ"` due to a hardcoded minimum length of 4) with a correct, tested, offset-preserving scanner defaulting to `min_length=1`.

- [ ] **Step 1: Write the failing tests**

Add to `script/tests/test_wd_format.py`:

```python
def test_find_null_terminated_strings_finds_basic_strings():
    blob = b"noise\x01" + b"PCQ\x00" + b"Lector\x00" + b"tail\x01\x02"
    records = find_null_terminated_strings(blob)
    names = [r.name for r in records]
    assert "PCQ" in names
    assert "Lector" in names


def test_find_null_terminated_strings_respects_min_length():
    # Regression test for the exact bug documented in wd_extraction_notes.md:
    # a min_length of 4 must exclude the 3-character "PCQ" while keeping
    # longer strings.
    blob = b"PCQ\x00Lector\x00"
    records = find_null_terminated_strings(blob, min_length=4)
    names = [r.name for r in records]
    assert "PCQ" not in names
    assert "Lector" in names


def test_find_null_terminated_strings_ignores_non_null_terminated_runs():
    blob = b"NoTerm\x01"
    assert find_null_terminated_strings(blob) == []


def test_find_null_terminated_strings_returns_offsets():
    blob = b"\x00\x00" + b"Hello\x00"
    records = find_null_terminated_strings(blob)
    assert records == [NamedRecord(offset=2, name="Hello")]


def test_find_null_terminated_strings_empty_data_returns_empty_list():
    assert find_null_terminated_strings(b"") == []
```

Update the import line to also bring in `NamedRecord` directly (needed for
the equality check in the offsets test):

```python
from tw2tools.wd_format import decompress_all_blocks, find_zlib_offsets, parse_archive_entries, search_text_multi, diff_byte_regions, parse_save_summary, find_named_records, parse_property_bags, patch_zlib_block, find_eco_files, extract_eco_files_from_wd_archive, find_null_terminated_strings, NamedRecord
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest script/tests/test_wd_format.py -v -k find_null_terminated_strings`
Expected: FAIL — `ImportError: cannot import name 'find_null_terminated_strings'`

- [ ] **Step 3: Write minimal implementation**

Add to `script/tw2tools/wd_format.py`, directly after
`extract_eco_files_from_wd_archive`:

```python
def find_null_terminated_strings(
    data: bytes, min_length: int = 1, max_length: int = 256
) -> list[NamedRecord]:
    records: list[NamedRecord] = []
    pos = 0
    n = len(data)
    while pos < n:
        if 32 <= data[pos] < 127:
            start = pos
            while pos < n and 32 <= data[pos] < 127:
                pos += 1
            if pos < n and data[pos] == 0:
                length = pos - start
                if min_length <= length <= max_length:
                    records.append(
                        NamedRecord(offset=start, name=data[start:pos].decode("ascii"))
                    )
        else:
            pos += 1
    return records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest script/tests/test_wd_format.py -v -k find_null_terminated_strings`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full test suite to confirm nothing broke**

Run: `python -m pytest script/tests/ -v`
Expected: all tests pass (50 passed — the 45 from Task 1 plus these 5 new
ones)

- [ ] **Step 6: Commit**

```bash
git add script/tw2tools/wd_format.py script/tests/test_wd_format.py
git commit -m "Add find_null_terminated_strings, fixing the min-length-4 PCQ bug"
```

---

### Task 4: Extract string offsets from `TwoWorlds2Quests.eco` and determine string layout

**Files:**
- Create: `script/wd_extract/task4_string_layout.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task4_strings.json` (gitignored)

**Interfaces:**
- Consumes: `find_null_terminated_strings` from Task 3; `script/wd_extract/eco_scripts/TwoWorlds2Quests.eco.bin` from Task 2.
- Produces: `task4_strings.json` — a list of `{"offset": int, "name": str}` records for every null-terminated string found, sorted by offset. Consumed by Task 5. Also produces a printed determination of whether strings cluster in a small contiguous region (separate string-constant pool) or spread across most of the file (interleaved with bytecode) — this determines which disambiguation strategy Task 5 should lean on.

- [ ] **Step 1: Write the script**

```python
"""Extract null-terminated strings (with offsets) from TwoWorlds2Quests.eco
and determine whether they cluster in one contiguous region (a separate
string-constant pool) or are scattered throughout the file (interleaved
with bytecode). This determines the disambiguation strategy for Task 5.

Run: python script/wd_extract/task4_string_layout.py
(depends on Task 2 having produced eco_scripts/TwoWorlds2Quests.eco.bin)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

from tw2tools.wd_format import find_null_terminated_strings

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
OUTPUT_PATH = Path(__file__).resolve().parent / "task4_strings.json"


def main() -> None:
    assert ECO_PATH.exists(), f"run Task 2 first to produce {ECO_PATH}"
    data = ECO_PATH.read_bytes()
    records = find_null_terminated_strings(data, min_length=1, max_length=256)
    records.sort(key=lambda r: r.offset)
    print(f"File size: {len(data)} bytes")
    print(f"Found {len(records)} null-terminated strings")

    offsets = [r.offset for r in records]
    span_start, span_end = min(offsets), max(offsets)
    span = span_end - span_start
    print(
        f"String offsets span bytes {span_start}..{span_end} "
        f"({span} bytes, {span / len(data):.1%} of file)"
    )

    # Ground-truth sanity checks from prior findings (wd_extraction_notes.md)
    names = [r.name for r in records]
    assert names.count("PCQ") == 2, f"expected PCQ twice, found {names.count('PCQ')}"
    assert "QUEST_SOLVED" in names, "expected QUEST_SOLVED to be present"
    assert "QUEST_GIVEN" in names, "expected QUEST_GIVEN to be present"
    assert any(n.startswith("translateQ_%d_QTD") for n in names), (
        "expected a translateQ_%d_QTD-style template string"
    )
    print("All ground-truth sanity checks passed.")

    OUTPUT_PATH.write_text(
        json.dumps([{"offset": r.offset, "name": r.name} for r in records], indent=2)
    )
    print(f"Wrote {len(records)} records to {OUTPUT_PATH}")

    if span / len(data) < 0.5:
        print(
            "=> Strings cluster in less than half the file: consistent with a "
            "SEPARATE STRING POOL. Task 5 should weight the pool-index signal "
            "over raw surrounding bytes."
        )
    else:
        print(
            "=> Strings are spread across most of the file: consistent with "
            "INTERLEAVED string constants. Task 5 should weight the raw "
            "byte-window signal over pool index."
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task4_string_layout.py`
Expected output: file size, string count, the span line, "All ground-truth
sanity checks passed.", the write-confirmation line, and one of the two
interpretation lines at the end. If any of the four `assert` sanity checks
fails, stop and investigate — it means the string scanner or the extracted
file doesn't match prior findings, and Task 5 would build on a wrong
foundation.

No commit (scratch output, gitignored).

---

### Task 5: Locate `QUEST_GIVEN`/`QUEST_SOLVED` anchors and compute disambiguation signals

**Files:**
- Create: `script/wd_extract/task5_lifecycle_anchors.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task5_anchors.json` (gitignored)

**Interfaces:**
- Consumes: `find_null_terminated_strings` from Task 3; `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 2.
- Produces: `task5_anchors.json` — a list of records, one per `QUEST_GIVEN`/`QUEST_SOLVED` occurrence, each with `keyword`, `offset`, `pool_index` (ordinal position among all strings in the file), `window_hex` (raw bytes surrounding the occurrence), and `candidate_quest_id_hits` (any place the confirmed quest IDs `45`/`2`, from `Q_45`/`GROUP_2`, appear in that window as u8/u16-LE/u32-LE). Consumed by Tasks 6 and 7.

- [ ] **Step 1: Write the script**

```python
"""Locate every QUEST_GIVEN / QUEST_SOLVED occurrence in TwoWorlds2Quests.eco
and compute two candidate disambiguation signals for each occurrence:
  1. a raw byte window immediately surrounding the string (for the
     interleaved-strings hypothesis: look for opcode framing or a nearby
     quest-ID integer)
  2. the string's ordinal position (pool_index) among ALL null-terminated
     strings in the file (for the separate-pool hypothesis: bytecode may
     reference strings by pool index rather than by raw offset)

Run: python script/wd_extract/task5_lifecycle_anchors.py
(depends on Task 2's eco_scripts/TwoWorlds2Quests.eco.bin)
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

from tw2tools.wd_format import find_null_terminated_strings

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
OUTPUT_PATH = Path(__file__).resolve().parent / "task5_anchors.json"

TARGET_KEYWORDS = ("QUEST_GIVEN", "QUEST_SOLVED")
WINDOW = 32  # bytes of raw context captured on each side of the string
CANDIDATE_QUEST_IDS = (45, 2)  # from Q_45 / GROUP_2, confirmed IDs for this quest


def find_candidate_ids_in_window(window: bytes) -> list[str]:
    hits: list[str] = []
    for quest_id in CANDIDATE_QUEST_IDS:
        u16 = struct.pack("<H", quest_id)
        u32 = struct.pack("<I", quest_id)
        if 0 <= quest_id < 256 and bytes([quest_id]) in window:
            hits.append(f"id={quest_id} as u8")
        if u16 in window:
            hits.append(f"id={quest_id} as u16-LE at window offset {window.find(u16)}")
        if u32 in window:
            hits.append(f"id={quest_id} as u32-LE at window offset {window.find(u32)}")
    return hits


def main() -> None:
    assert ECO_PATH.exists(), f"run Task 2 first to produce {ECO_PATH}"
    data = ECO_PATH.read_bytes()
    all_records = find_null_terminated_strings(data, min_length=1, max_length=256)
    all_records.sort(key=lambda r: r.offset)

    given_count = sum(1 for r in all_records if r.name == "QUEST_GIVEN")
    solved_count = sum(1 for r in all_records if r.name == "QUEST_SOLVED")
    assert given_count >= 1, "expected at least one QUEST_GIVEN per prior findings"
    assert solved_count >= 1, "expected at least one QUEST_SOLVED per prior findings"

    anchors = []
    for pool_index, record in enumerate(all_records):
        if record.name not in TARGET_KEYWORDS:
            continue
        start = max(0, record.offset - WINDOW)
        end = min(len(data), record.offset + len(record.name) + 1 + WINDOW)
        window = data[start:end]
        candidate_ids = find_candidate_ids_in_window(window)
        anchors.append(
            {
                "keyword": record.name,
                "offset": record.offset,
                "pool_index": pool_index,
                "window_hex": window.hex(" "),
                "candidate_quest_id_hits": candidate_ids,
            }
        )
        print(
            f"{record.name}: offset={record.offset} pool_index={pool_index} "
            f"candidate_id_hits={candidate_ids}"
        )

    print(f"QUEST_GIVEN occurrences: {given_count}, QUEST_SOLVED occurrences: {solved_count}")
    OUTPUT_PATH.write_text(json.dumps(anchors, indent=2))
    print(f"Wrote {len(anchors)} anchor records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task5_lifecycle_anchors.py`
Expected output: one printed line per `QUEST_GIVEN`/`QUEST_SOLVED`
occurrence showing its offset, pool index, and any candidate-ID hits, a
summary count line, and the write-confirmation line. Both counts must be
`>= 1` (asserted) or the script stops — that would mean the extracted file
doesn't match the already-confirmed prior findings.

No commit (scratch output, gitignored).

---

### Task 6: Cross-validate the byte-window pattern against other scripts

**Files:**
- Create: `script/wd_extract/task6_cross_validate.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task6_cross_validation.json` (gitignored)

**Interfaces:**
- Consumes: `find_null_terminated_strings` from Task 3; all `eco_scripts/*.eco.bin` files from Task 2.
- Produces: `task6_cross_validation.json` — a mapping of script filename to its list of `QUEST_GIVEN`/`QUEST_SOLVED` occurrences (offset + raw byte window), for every script that has at least one occurrence. Consumed by Task 8's write-up (to compare against Task 5's `TwoWorlds2Quests` windows).

- [ ] **Step 1: Write the script**

```python
"""Cross-validate the byte-window pattern found in TwoWorlds2Quests.eco
(Task 5) against the other 20 extracted .eco scripts: scan all of them for
QUEST_GIVEN/QUEST_SOLVED occurrences and extract the same raw byte window
around each, for manual/agent comparison against Task 5's findings.

Run: python script/wd_extract/task6_cross_validate.py
(depends on Task 2 having populated eco_scripts/)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

from tw2tools.wd_format import find_null_terminated_strings

ECO_DIR = Path(__file__).resolve().parent / "eco_scripts"
OUTPUT_PATH = Path(__file__).resolve().parent / "task6_cross_validation.json"

TARGET_KEYWORDS = ("QUEST_GIVEN", "QUEST_SOLVED")
WINDOW = 32


def windows_for_file(path: Path) -> list[dict]:
    data = path.read_bytes()
    records = find_null_terminated_strings(data, min_length=1, max_length=256)
    hits = []
    for record in records:
        if record.name not in TARGET_KEYWORDS:
            continue
        start = max(0, record.offset - WINDOW)
        end = min(len(data), record.offset + len(record.name) + 1 + WINDOW)
        hits.append(
            {
                "keyword": record.name,
                "offset": record.offset,
                "window_hex": data[start:end].hex(" "),
            }
        )
    return hits


def main() -> None:
    assert ECO_DIR.exists(), f"run Task 2 first to produce {ECO_DIR}"
    results: dict[str, list[dict]] = {}
    for path in sorted(ECO_DIR.glob("*.eco.bin")):
        hits = windows_for_file(path)
        if hits:
            results[path.stem] = hits
            print(f"{path.stem}: {len(hits)} occurrence(s)")

    other_scripts = [name for name in results if name != "TwoWorlds2Quests.eco"]
    print(
        f"Scripts other than TwoWorlds2Quests containing these keywords: "
        f"{other_scripts}"
    )

    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(
        f"Wrote cross-validation windows for {len(results)} script(s) to "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task6_cross_validate.py`
Expected output: a count line per script that contains either keyword
(`TwoWorlds2Quests.eco` must appear, since Task 5 already confirmed hits
there), a line listing which *other* scripts contain them (this list may
legitimately be empty — that is itself a valid finding to record in Task
8, not a failure), and the write-confirmation line.

No commit (scratch output, gitignored).

---

### Task 7: Correlate confirmed `PCQ` values against the lifecycle anchors

**Files:**
- Create: `script/wd_extract/task7_correlate_pcq.py` (gitignored scratch)
- Creates on run: `script/wd_extract/task7_pcq_correlation.json` (gitignored)

**Interfaces:**
- Consumes: `eco_scripts/TwoWorlds2Quests.eco.bin` from Task 2; `task5_anchors.json` from Task 5.
- Produces: `task7_pcq_correlation.json` — every place the confirmed `PCQ` transition values (`20`, `3483`, `853`) appear in the file as u8/u16-LE/u32-LE, each annotated with its distance to the nearest `QUEST_GIVEN`/`QUEST_SOLVED` anchor from Task 5. This is the key output Task 8's write-up decides success/failure from.

- [ ] **Step 1: Write the script**

```python
"""Search TwoWorlds2Quests.eco for the confirmed PCQ transition values
(20, 3483, 853) encoded as u8/u16-LE/u32-LE, and report each hit's distance
to the nearest QUEST_GIVEN/QUEST_SOLVED anchor found in Task 5. A small
distance for a hit near the Gods-and-Demons-disambiguated anchor is the
target finding for this whole exploratory pass.

Run: python script/wd_extract/task7_correlate_pcq.py
(depends on Task 5's task5_anchors.json existing)
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "script"))

ECO_PATH = Path(__file__).resolve().parent / "eco_scripts" / "TwoWorlds2Quests.eco.bin"
ANCHORS_PATH = Path(__file__).resolve().parent / "task5_anchors.json"
OUTPUT_PATH = Path(__file__).resolve().parent / "task7_pcq_correlation.json"

PCQ_VALUES = (20, 3483, 853)


def find_all(data: bytes, needle: bytes) -> list[int]:
    offsets = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx == -1:
            break
        offsets.append(idx)
        start = idx + 1
    return offsets


def main() -> None:
    assert ECO_PATH.exists(), f"run Task 2 first to produce {ECO_PATH}"
    assert ANCHORS_PATH.exists(), f"run Task 5 first to produce {ANCHORS_PATH}"
    data = ECO_PATH.read_bytes()
    anchors = json.loads(ANCHORS_PATH.read_text())
    anchor_offsets = [a["offset"] for a in anchors]
    assert anchor_offsets, "task5_anchors.json has no anchors - re-run Task 5"

    pcq_hits = []
    for value in PCQ_VALUES:
        encodings = {
            "u16_le": struct.pack("<H", value),
            "u32_le": struct.pack("<I", value),
        }
        if 0 <= value < 256:
            encodings["u8"] = bytes([value])
        for encoding_name, needle in encodings.items():
            for offset in find_all(data, needle):
                nearest = min(anchor_offsets, key=lambda a: abs(a - offset))
                distance = abs(nearest - offset)
                pcq_hits.append(
                    {
                        "value": value,
                        "encoding": encoding_name,
                        "offset": offset,
                        "nearest_anchor_offset": nearest,
                        "distance_to_nearest_anchor": distance,
                    }
                )

    pcq_hits.sort(key=lambda h: h["distance_to_nearest_anchor"])
    print(f"Found {len(pcq_hits)} total PCQ-value hits across all encodings")
    print("Closest 10 to any QUEST_GIVEN/QUEST_SOLVED anchor:")
    for hit in pcq_hits[:10]:
        print(
            f"  value={hit['value']} enc={hit['encoding']} offset={hit['offset']} "
            f"distance={hit['distance_to_nearest_anchor']}"
        )

    OUTPUT_PATH.write_text(json.dumps(pcq_hits, indent=2))
    print(f"Wrote {len(pcq_hits)} correlation records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python script/wd_extract/task7_correlate_pcq.py`
Expected output: total hit count, then the 10 closest hits with their
value/encoding/offset/distance. This is the decision point for Task 8: a
small distance (roughly within or near the `WINDOW = 32` size used in Tasks
5–6) on a hit whose nearest anchor also had `candidate_quest_id_hits` in
Task 5's output is a strong positive signal; consistently large distances
across all hits is the negative result.

No commit (scratch output, gitignored).

---

### Task 8: Write up findings and commit

**Files:**
- Modify: `script/wd_extraction_notes.md` (append a new dated section at the end of the file)

**Interfaces:**
- Consumes: printed output and JSON files from Tasks 2, 4, 5, 6, and 7 (`eco_scripts/`, `task4_strings.json`, `task5_anchors.json`, `task6_cross_validation.json`, `task7_pcq_correlation.json`).
- Produces: the durable, permanent record of this pass's outcome — the only committed artifact besides the two `tw2tools` additions from Tasks 1 and 3.

- [ ] **Step 1: Decide the outcome bucket**

Read `task7_pcq_correlation.json`'s closest hit(s):

- **Positive finding:** the closest hit has a small `distance_to_nearest_anchor` (roughly ≤ 40–50 bytes, i.e. within or just past the 32-byte window used in Tasks 5/6) AND the corresponding anchor in `task5_anchors.json` (matched by `nearest_anchor_offset`) has a non-empty `candidate_quest_id_hits`, OR Task 6 confirmed the same raw byte framing recurs in another script at the equivalent position.
- **Negative/inconclusive finding:** none of the above hold — distances are all large, or a small distance exists but with no supporting quest-ID or cross-script confirmation.

- [ ] **Step 2: Append the appropriate section to `script/wd_extraction_notes.md`**

Append at the very end of the file (after the existing "## Stopping point
(2026-07-11)" section), using this structure. Fill in every bracketed
`[...]` placeholder with the actual data read from the JSON files in Step
1 — do not leave any bracket unresolved.

For a **positive finding**:

```markdown
## Resumed: exploratory bytecode pass (2026-07-13) — [one-line result summary]

Resumed the bytecode-decoding project as a single time-boxed exploratory
pass (see
`docs/superpowers/specs/2026-07-13-eco-bytecode-exploration-design.md`),
using an anchor-and-triangulate method rather than building a general
disassembler.

**Corrected extraction method.** The previous `dlc3_eco_full.bin` scratch
fragment (1468 bytes) was stale/incorrect. The correct method decompresses
every zlib block in the archive first, then checks which decompressed
blocks start with the `"ECO"` magic (each `.eco` file is its own complete
zlib block). Added `tw2tools.wd_format.extract_eco_files_from_wd_archive`
(tested) for this. Re-confirmed all 21 real `.eco` files, with
`TwoWorlds2Quests.eco` at the documented 179,340 bytes. Also added
`find_null_terminated_strings` (tested), replacing the earlier buggy
ad-hoc `min_length=4` regex that had silently dropped `PCQ`.

**String layout:** [state whether strings clustered in a contiguous region
or spread throughout the file, and the percentage from Task 4's output].

**Finding:** [insert the specific offset(s), PCQ value(s), and encoding
from `task7_pcq_correlation.json` that showed a small distance to a
`QUEST_GIVEN`/`QUEST_SOLVED` anchor; state the anchor's offset and
`candidate_quest_id_hits` from `task5_anchors.json`; state whether Task 6
cross-validation confirmed the same byte framing in another script, and
name it]. Example bytes: `[insert the relevant window_hex value]`.
```

For a **negative/inconclusive finding**:

```markdown
## Resumed: exploratory bytecode pass (2026-07-13) — inconclusive

Resumed the bytecode-decoding project as a single time-boxed exploratory
pass (see
`docs/superpowers/specs/2026-07-13-eco-bytecode-exploration-design.md`),
using an anchor-and-triangulate method rather than building a general
disassembler.

**Corrected extraction method.** The previous `dlc3_eco_full.bin` scratch
fragment (1468 bytes) was stale/incorrect. The correct method decompresses
every zlib block in the archive first, then checks which decompressed
blocks start with the `"ECO"` magic (each `.eco` file is its own complete
zlib block). Added `tw2tools.wd_format.extract_eco_files_from_wd_archive`
(tested) for this. Re-confirmed all 21 real `.eco` files, with
`TwoWorlds2Quests.eco` at the documented 179,340 bytes. Also added
`find_null_terminated_strings` (tested), replacing the earlier buggy
ad-hoc `min_length=4` regex that had silently dropped `PCQ`.

**What was tried:**
- [insert QUEST_GIVEN/QUEST_SOLVED occurrence counts from Task 5's
  output, and whether the string layout was pool-like or interleaved
  from Task 4's determination]
- [insert the cross-validation result from Task 6: which other scripts,
  if any, contained the same keywords, and whether any consistent byte
  pattern held across them]
- [insert the closest PCQ-value-to-anchor distance found in Task 7's
  output, and why it doesn't constitute a confident match]

**Why this didn't resolve the question:** [insert the concrete blocker,
e.g. "string constants and any integer references to them could not be
distinguished from other incidental integers in the file without decoding
actual instruction opcodes, which this pass deliberately did not
attempt"].

**Stopping point (2026-07-13).** Consistent with the original stopping
point, decoding further would require building an actual opcode
interpreter rather than anchor-based correlation. Not pursued further in
this pass by design (see the exploration spec). Future starting point:
[insert the most promising partial lead found, e.g. a specific offset
range, pool-index pattern, or script worth resuming from].
```

- [ ] **Step 3: Commit**

```bash
git add script/wd_extraction_notes.md
git commit -m "Record outcome of 2026-07-13 .eco bytecode exploratory pass"
```

---

## Self-Review

**Spec coverage:** Task 1–2 implement the design's "extract clean payloads"
stage (and fix the extraction-bounds gap discovered while planning). Tasks
3–5 implement "locate and disambiguate lifecycle anchors." Task 6
implements "cross-validate." Task 7 implements "correlate to PCQ." Task 8
implements the design's "stopping criteria and deliverable" section. The
design's "tooling boundary" (scratch-first, promote only if stable) is
reflected in Tasks 1 and 3 going into `tw2tools` with tests while Tasks
2 and 4–7 stay as gitignored scratch scripts. The design's "binary-output
discipline" is reflected in every scratch task writing to a file and only
printing bounded summaries. The design's explicit stopping condition (do
not escalate past one pass) is Task 8's exit point.

**Placeholder scan:** The only bracketed `[...]` placeholders are in Task
8's write-up templates, which is inherent to reporting a genuinely unknown
research outcome — not a deferred engineering decision. Every other task
has complete, runnable code with concrete expected output.

**Type consistency:** `EcoFile` (offset, name, data) and `NamedRecord`
(offset, name) are used consistently with their existing definitions in
`wd_format.py` across all tasks. `extract_eco_files_from_wd_archive` and
`find_null_terminated_strings` signatures match between their Task 1/3
definitions and every later task that imports them.
