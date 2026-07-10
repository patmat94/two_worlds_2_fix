# TW2 `.wd`/`.eco`/Save Research Toolkit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ~20 one-off, hardcoded-path exploration scripts with a small, portable, tested `tw2tools` package (extract/list-entries/search-text/diff-saves) for researching the Two Worlds II `.wd` archive format, `.eco` quest files, and save-game structure — and use it to run a real search for the Casbrim/Expert Side Adventure quest data.

**Architecture:** A `script/tw2tools/` Python package with one core module (`wd_format.py`) holding all parsing/search/diff logic as pure functions over `bytes`, and four thin CLI scripts (`extract.py`, `list_entries.py`, `search_text.py`, `diff_saves.py`) that each import from it and add argparse + I/O. Every script takes paths as CLI arguments — nothing is hardcoded.

**Tech Stack:** Python 3.14 (existing `.venv`), stdlib only for `tw2tools` itself (`zlib`, `struct`, `argparse`, `json`, `pathlib`, `dataclasses`), `pytest` added as a test-only dependency.

## Global Constraints

- No hardcoded absolute file paths anywhere in `tw2tools/*` — every archive/save/output path is a required or defaulted-but-overridable CLI argument.
- `tw2tools` core and CLI code use only the Python standard library; `pytest` is the only new dependency, and it's test-only.
- Preserve `script/wd_extraction_notes.md` as the running, authoritative notes file — update it, never replace it wholesale.
- Never print or dump full contents of `.wd`/chunk/save binary files to the terminal or into any tool output — bound all inspection output to counts, small samples, or files written to disk (see project memory `feedback-wd-file-handling`).
- Real data lives under `files/Two Worlds 2/` (gitignored): `DLC3_PC.wd` (~1.9GB), `DLC3_PC_POL.wd` (~1.3MB), `saves/remote/NNNNNN.TwoWorldsIISave(_header)` (572 snapshots). Treat these as read-only inputs; never modify them.
- CLI scripts are invoked as modules (`python -m tw2tools.<name> ...`) with cwd set to `script/`, not run as bare scripts, so package-relative imports resolve correctly.

---

### Task 1: Package scaffolding, test runner, gitignore

**Files:**
- Create: `script/tw2tools/__init__.py`
- Create: `script/tests/__init__.py` (empty, keeps test discovery simple)
- Create: `script/tests/test_package.py`
- Create: `script/pytest.ini`
- Modify: `.gitignore`

**Interfaces:**
- Produces: an importable `tw2tools` package and a working `pytest` invocation (`.venv/Scripts/python.exe -m pytest script/tests -v`) that later tasks build on.

- [ ] **Step 1: Write the failing test**

Create `script/tests/test_package.py`:

```python
import tw2tools


def test_tw2tools_package_is_importable():
    assert tw2tools is not None
```

- [ ] **Step 2: Install pytest, then run the test to verify it fails**

pytest isn't installed yet (test-only dependency), so install it first:

Run: `.venv/Scripts/python.exe -m pip install pytest`
Expected: pytest installs successfully.

Run: `.venv/Scripts/python.exe -m pytest script/tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tw2tools'` (the package doesn't exist yet).

- [ ] **Step 3: Create the package and pytest config**

Create `script/tw2tools/__init__.py` (empty file).

Create `script/tests/__init__.py` (empty file).

Create `script/pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

- [ ] **Step 4: Update `.gitignore`**

Current contents of `.gitignore`:

```
extracted_wd/
files/
```

Replace with:

```
extracted_wd/
files/
wd_extract/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest script/tests -v`
Expected: PASS — `test_tw2tools_package_is_importable` passes.

- [ ] **Step 6: Commit**

```bash
git add script/tw2tools/__init__.py script/tests/__init__.py script/tests/test_package.py script/pytest.ini .gitignore
git commit -m "Scaffold tw2tools package and pytest runner"
```

---

### Task 2: `wd_format.py` — zlib block scanning

**Files:**
- Create: `script/tw2tools/wd_format.py`
- Create: `script/tests/test_wd_format.py`

**Interfaces:**
- Produces: `find_zlib_offsets(data: bytes) -> list[int]`, `decompress_all_blocks(data: bytes) -> Iterator[tuple[int, bytes]]` — consumed by `extract.py` (Task 6).

- [ ] **Step 1: Write the failing tests**

Create `script/tests/test_wd_format.py`:

```python
import zlib

from tw2tools.wd_format import decompress_all_blocks, find_zlib_offsets


def test_find_zlib_offsets_finds_known_signature():
    payload = zlib.compress(b"hello world" * 10)
    data = b"\x00" * 5 + payload + b"\x00" * 5
    offsets = find_zlib_offsets(data)
    assert 5 in offsets


def test_decompress_all_blocks_recovers_original_data():
    original = b"hello world" * 10
    payload = zlib.compress(original)
    data = b"\x00" * 5 + payload + b"\x00" * 5
    blocks = list(decompress_all_blocks(data))
    assert (5, original) in blocks


def test_decompress_all_blocks_finds_multiple_concatenated_streams():
    first = zlib.compress(b"first block")
    second = zlib.compress(b"second block")
    data = first + second
    blocks = dict(decompress_all_blocks(data))
    assert blocks[0] == b"first block"
    assert blocks[len(first)] == b"second block"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tw2tools.wd_format'`

- [ ] **Step 3: Write the implementation**

Create `script/tw2tools/wd_format.py`:

```python
"""Core parsing logic for Two Worlds II .wd archives and save files."""
from __future__ import annotations

import zlib
from typing import Iterator

ZLIB_SIGNATURES = (b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")


def find_zlib_offsets(data: bytes) -> list[int]:
    offsets: set[int] = set()
    for sig in ZLIB_SIGNATURES:
        start = 0
        while True:
            idx = data.find(sig, start)
            if idx == -1:
                break
            offsets.add(idx)
            start = idx + 1
    return sorted(offsets)


def _decompress_at(data: bytes, offset: int) -> bytes | None:
    obj = zlib.decompressobj()
    result = bytearray()
    pos = offset
    try:
        while pos < len(data):
            chunk = data[pos:pos + 65536]
            result.extend(obj.decompress(chunk))
            pos += len(chunk)
            if obj.unused_data or obj.eof:
                return bytes(result)
        return bytes(result) if obj.eof else None
    except zlib.error:
        return None


def decompress_all_blocks(data: bytes) -> Iterator[tuple[int, bytes]]:
    for offset in find_zlib_offsets(data):
        decompressed = _decompress_at(data, offset)
        if decompressed:
            yield offset, decompressed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: PASS — all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/wd_format.py script/tests/test_wd_format.py
git commit -m "Add zlib block scanning/decompression to wd_format"
```

---

### Task 3: `wd_format.py` — archive entry parsing

**Files:**
- Modify: `script/tw2tools/wd_format.py`
- Modify: `script/tests/test_wd_format.py`

**Interfaces:**
- Consumes: nothing new from other modules.
- Produces: `ArchiveEntry` dataclass (fields: `path: str`, `type_id: int`, `flags: int`, `word1: int`, `word2: int`, `word3: int`, `word4: int`, `marker: str`, `marker_pos: int`, `data_pos: int`) and `parse_archive_entries(data: bytes) -> list[ArchiveEntry]` — consumed by `list_entries.py` (Task 7).

- [ ] **Step 1: Write the failing tests**

Append to `script/tests/test_wd_format.py`:

```python
import struct
from pathlib import Path

import pytest

from tw2tools.wd_format import parse_archive_entries


def _build_entry(path, type_id, flags, word1, word2, word3, word4, marker=b"$"):
    footer = struct.pack("<HHIIII", type_id, flags, word1, word2, word3, word4)
    return marker + path.encode("ascii") + b"\x01\x00" + footer


def test_parse_archive_entries_single_entry():
    blob = _build_entry("Scripts\\Foo.eco", 100, 1, 0x11, 0x22, 0x33, 0x44)
    entries = parse_archive_entries(blob)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.path == "Scripts\\Foo.eco"
    assert entry.type_id == 100
    assert entry.flags == 1
    assert (entry.word1, entry.word2, entry.word3, entry.word4) == (0x11, 0x22, 0x33, 0x44)
    assert entry.marker == "$"


def test_parse_archive_entries_multiple_entries():
    blob = _build_entry("A.eco", 1, 0, 1, 2, 3, 4) + _build_entry(
        "B.act", 2, 1, 5, 6, 7, 8, marker=b"*"
    )
    entries = parse_archive_entries(blob)
    assert [e.path for e in entries] == ["A.eco", "B.act"]
    assert entries[1].marker == "*"


CHUNK_PATH = (
    Path(__file__).resolve().parents[1] / "extracted_wd" / "DLC3_PC_chunk_00000030.bin"
)


def test_parse_archive_entries_matches_known_real_chunk():
    if not CHUNK_PATH.exists():
        pytest.skip("extracted_wd chunk not present locally")
    data = CHUNK_PATH.read_bytes()
    entries = {e.path: e for e in parse_archive_entries(data)}

    dragon = entries["ActionSets\\DRAGON_10_DEFAULT_TW2.act"]
    assert (dragon.type_id, dragon.flags) == (63944, 1)
    assert (dragon.word1, dragon.word2, dragon.word3, dragon.word4) == (
        100663296,
        335544325,
        56,
        503316480,
    )

    dlc3 = entries["Scripts\\Campaigns\\Missions\\DLC_3.eco"]
    assert (dlc3.type_id, dlc3.flags) == (9952, 62)
    assert (dlc3.word1, dlc3.word2, dlc3.word3, dlc3.word4) == (
        520093696,
        3154116609,
        5,
        704643072,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_archive_entries'`

- [ ] **Step 3: Write the implementation**

Add to `script/tw2tools/wd_format.py` (after the zlib section):

```python
import struct
from dataclasses import dataclass

ENTRY_MARKERS = (b"$", b"*")
ENTRY_TERMINATOR = b"\x01\x00"
ENTRY_FOOTER_STRUCT = "<HHIIII"
ENTRY_FOOTER_SIZE = struct.calcsize(ENTRY_FOOTER_STRUCT)


@dataclass
class ArchiveEntry:
    path: str
    type_id: int
    flags: int
    word1: int
    word2: int
    word3: int
    word4: int
    marker: str
    marker_pos: int
    data_pos: int


def parse_archive_entries(data: bytes) -> list[ArchiveEntry]:
    entries: list[ArchiveEntry] = []
    pos = 0
    while True:
        idx = data.find(ENTRY_TERMINATOR, pos)
        if idx == -1:
            break
        marker_pos = None
        marker_char = None
        for marker in ENTRY_MARKERS:
            candidate = data.rfind(marker, pos, idx)
            if candidate != -1 and (marker_pos is None or candidate > marker_pos):
                marker_pos = candidate
                marker_char = marker
        if marker_pos is None or idx - marker_pos < 4:
            pos = idx + 2
            continue
        name_bytes = data[marker_pos + 1 : idx]
        if len(name_bytes) < 3 or any(b < 32 or b > 126 for b in name_bytes):
            pos = idx + 2
            continue
        path_name = name_bytes.decode("ascii")
        data_pos = idx + 2
        if data_pos + ENTRY_FOOTER_SIZE > len(data):
            break
        type_id, flags, word1, word2, word3, word4 = struct.unpack_from(
            ENTRY_FOOTER_STRUCT, data, data_pos
        )
        entries.append(
            ArchiveEntry(
                path=path_name,
                type_id=type_id,
                flags=flags,
                word1=word1,
                word2=word2,
                word3=word3,
                word4=word4,
                marker=marker_char.decode("ascii"),
                marker_pos=marker_pos,
                data_pos=data_pos,
            )
        )
        pos = data_pos + ENTRY_FOOTER_SIZE
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: PASS — all tests pass, including the real-chunk integration test (confirms the 20-byte, 4-word footer model against real extracted data — note this test's expected `word1`/`word4` values are freshly verified against the real chunk, and differ from some earlier hand-transcribed values in `wd_extraction_notes.md`; Task 10 corrects the notes).

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/wd_format.py script/tests/test_wd_format.py
git commit -m "Add archive entry record parsing to wd_format"
```

---

### Task 4: `wd_format.py` — multi-encoding text search

**Files:**
- Modify: `script/tw2tools/wd_format.py`
- Modify: `script/tests/test_wd_format.py`

**Interfaces:**
- Produces: `Match` dataclass (fields: `term: str`, `encoding: str`, `offset: int`, `context: str`) and `search_text_multi(data: bytes, terms: list[str]) -> list[Match]` — consumed by `search_text.py` (Task 8).

- [ ] **Step 1: Write the failing tests**

Append to `script/tests/test_wd_format.py`:

```python
from tw2tools.wd_format import search_text_multi


def test_search_text_multi_finds_ascii():
    data = b"padding" + "Casbrim".encode("ascii") + b"padding"
    matches = search_text_multi(data, ["Casbrim"])
    assert any(m.encoding == "ascii" and m.offset == 7 for m in matches)


def test_search_text_multi_finds_utf16le_including_polish_diacritics():
    needle = "Ekspercka przygoda poboczna".encode("utf-16-le")
    data = b"\x00\x00" + needle + b"\x00\x00"
    matches = search_text_multi(data, ["Ekspercka przygoda poboczna"])
    assert any(m.encoding == "utf-16-le" and m.offset == 2 for m in matches)


def test_search_text_multi_no_match_returns_empty_list():
    data = b"nothing interesting here"
    assert search_text_multi(data, ["Casbrim"]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: FAIL — `ImportError: cannot import name 'search_text_multi'`

- [ ] **Step 3: Write the implementation**

Add to `script/tw2tools/wd_format.py`:

```python
SEARCH_ENCODINGS = ("ascii", "utf-16-le")


@dataclass
class Match:
    term: str
    encoding: str
    offset: int
    context: str


def _context(data: bytes, offset: int, length: int, radius: int = 16) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + length + radius)
    snippet = data[start:end]
    printable = "".join(chr(b) if 32 <= b < 127 else "." for b in snippet)
    return f"{snippet.hex(' ')} | {printable}"


def search_text_multi(data: bytes, terms: list[str]) -> list[Match]:
    matches: list[Match] = []
    for term in terms:
        for encoding in SEARCH_ENCODINGS:
            try:
                needle = term.encode(encoding)
            except UnicodeEncodeError:
                continue
            start = 0
            while True:
                idx = data.find(needle, start)
                if idx == -1:
                    break
                matches.append(
                    Match(
                        term=term,
                        encoding=encoding,
                        offset=idx,
                        context=_context(data, idx, len(needle)),
                    )
                )
                start = idx + 1
    return matches
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: PASS — all tests pass.

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/wd_format.py script/tests/test_wd_format.py
git commit -m "Add multi-encoding text search to wd_format"
```

---

### Task 5: `wd_format.py` — byte-region diff

**Files:**
- Modify: `script/tw2tools/wd_format.py`
- Modify: `script/tests/test_wd_format.py`

**Interfaces:**
- Produces: `DiffRegion` dataclass (fields: `op: str`, `a_start: int`, `a_end: int`, `b_start: int`, `b_end: int`, `a_bytes: bytes`, `b_bytes: bytes`) and `diff_byte_regions(a: bytes, b: bytes) -> list[DiffRegion]` — consumed by `diff_saves.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

Append to `script/tests/test_wd_format.py`:

```python
from tw2tools.wd_format import diff_byte_regions


def test_diff_byte_regions_identical_returns_empty_list():
    assert diff_byte_regions(b"abcdef", b"abcdef") == []


def test_diff_byte_regions_replace_middle():
    a = b"HEADER" + b"OLDVALUE" + b"FOOTER"
    b = b"HEADER" + b"NEWVAL!!" + b"FOOTER"
    regions = diff_byte_regions(a, b)
    assert len(regions) == 1
    region = regions[0]
    assert region.op == "replace"
    assert region.a_bytes == b"OLDVALUE"
    assert region.b_bytes == b"NEWVAL!!"


def test_diff_byte_regions_insert():
    a = b"HEADERFOOTER"
    b = b"HEADER" + b"EXTRA" + b"FOOTER"
    regions = diff_byte_regions(a, b)
    assert len(regions) == 1
    assert regions[0].op == "insert"
    assert regions[0].a_bytes == b""
    assert regions[0].b_bytes == b"EXTRA"


def test_diff_byte_regions_delete():
    a = b"HEADER" + b"EXTRA" + b"FOOTER"
    b = b"HEADERFOOTER"
    regions = diff_byte_regions(a, b)
    assert len(regions) == 1
    assert regions[0].op == "delete"
    assert regions[0].a_bytes == b"EXTRA"
    assert regions[0].b_bytes == b""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: FAIL — `ImportError: cannot import name 'diff_byte_regions'`

- [ ] **Step 3: Write the implementation**

Add to `script/tw2tools/wd_format.py`:

```python
@dataclass
class DiffRegion:
    op: str
    a_start: int
    a_end: int
    b_start: int
    b_end: int
    a_bytes: bytes
    b_bytes: bytes


def diff_byte_regions(a: bytes, b: bytes) -> list[DiffRegion]:
    max_prefix = min(len(a), len(b))
    prefix_len = 0
    while prefix_len < max_prefix and a[prefix_len] == b[prefix_len]:
        prefix_len += 1

    max_suffix = max_prefix - prefix_len
    suffix_len = 0
    while (
        suffix_len < max_suffix
        and a[len(a) - 1 - suffix_len] == b[len(b) - 1 - suffix_len]
    ):
        suffix_len += 1

    a_start, a_end = prefix_len, len(a) - suffix_len
    b_start, b_end = prefix_len, len(b) - suffix_len

    if a_start == a_end and b_start == b_end:
        return []

    if a_start == a_end:
        op = "insert"
    elif b_start == b_end:
        op = "delete"
    else:
        op = "replace"

    return [
        DiffRegion(
            op=op,
            a_start=a_start,
            a_end=a_end,
            b_start=b_start,
            b_end=b_end,
            a_bytes=a[a_start:a_end],
            b_bytes=b[b_start:b_end],
        )
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_wd_format.py -v`
Expected: PASS — all tests pass.

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/wd_format.py script/tests/test_wd_format.py
git commit -m "Add prefix/suffix byte-region diff to wd_format"
```

---

### Task 6: `extract.py` CLI

**Files:**
- Create: `script/tw2tools/extract.py`
- Create: `script/tests/test_extract.py`

**Interfaces:**
- Consumes: `tw2tools.wd_format.decompress_all_blocks(data: bytes) -> Iterator[tuple[int, bytes]]` (Task 2).
- Produces: `extract(archive_path: Path, output_dir: Path) -> int` (returns block count), and the `python -m tw2tools.extract <archive> [-o out_dir]` CLI.

- [ ] **Step 1: Write the failing test**

Create `script/tests/test_extract.py`:

```python
import subprocess
import sys
import zlib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.extract", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_extract_writes_chunk_files(tmp_path):
    archive = tmp_path / "sample.wd"
    first = zlib.compress(b"first block payload")
    second = zlib.compress(b"second block payload")
    archive.write_bytes(first + second)
    out_dir = tmp_path / "out"

    result = _run(str(archive), "-o", str(out_dir), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Extracted 2 block(s)" in result.stdout
    chunk_files = sorted(out_dir.glob("sample_chunk_*.bin"))
    assert len(chunk_files) == 2
    assert chunk_files[0].read_bytes() == b"first block payload"
    assert chunk_files[1].read_bytes() == b"second block payload"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_extract.py -v`
Expected: FAIL — non-zero return code, `No module named tw2tools.extract`.

- [ ] **Step 3: Write the implementation**

Create `script/tw2tools/extract.py`:

```python
"""CLI: extract all zlib-compressed blocks from a Two Worlds II .wd archive."""
from __future__ import annotations

import argparse
from pathlib import Path

from tw2tools.wd_format import decompress_all_blocks


def extract(archive_path: Path, output_dir: Path) -> int:
    data = archive_path.read_bytes()
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for offset, chunk in decompress_all_blocks(data):
        chunk_name = f"{archive_path.stem}_chunk_{offset:08x}.bin"
        (output_dir / chunk_name).write_bytes(chunk)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract zlib blocks from a Two Worlds II .wd archive"
    )
    parser.add_argument("archive", type=Path, help="Path to the .wd archive")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("wd_extract"),
        help="Destination folder for decompressed chunk files (default: ./wd_extract)",
    )
    args = parser.parse_args()

    count = extract(args.archive, args.output_dir)
    print(f"Extracted {count} block(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_extract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/extract.py script/tests/test_extract.py
git commit -m "Add extract.py CLI for full .wd zlib block extraction"
```

---

### Task 7: `list_entries.py` CLI

**Files:**
- Create: `script/tw2tools/list_entries.py`
- Create: `script/tests/test_list_entries.py`

**Interfaces:**
- Consumes: `tw2tools.wd_format.parse_archive_entries(data: bytes) -> list[ArchiveEntry]` (Task 3).
- Produces: `collect_entries(path: Path, suffix_filter: str | None) -> list[dict]`, and the `python -m tw2tools.list_entries <path> [--filter SUFFIX] [--json OUT]` CLI.

- [ ] **Step 1: Write the failing test**

Create `script/tests/test_list_entries.py`:

```python
import json
import struct
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.list_entries", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _build_entry(path, type_id, flags, word1, word2, word3, word4, marker=b"$"):
    footer = struct.pack("<HHIIII", type_id, flags, word1, word2, word3, word4)
    return marker + path.encode("ascii") + b"\x01\x00" + footer


def test_list_entries_filters_by_suffix(tmp_path):
    blob = _build_entry("Scripts\\Foo.eco", 1, 0, 1, 2, 3, 4) + _build_entry(
        "Textures\\Bar.dds", 2, 0, 5, 6, 7, 8
    )
    chunk_file = tmp_path / "chunk_00000000.bin"
    chunk_file.write_bytes(blob)
    json_out = tmp_path / "entries.json"

    result = _run(
        str(chunk_file), "--filter", ".eco", "--json", str(json_out), cwd=SCRIPT_DIR
    )

    assert result.returncode == 0, result.stderr
    assert "Found 1 entry" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["path"] == "Scripts\\Foo.eco"
    assert rows[0]["source_chunk"] == "chunk_00000000.bin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_list_entries.py -v`
Expected: FAIL — `No module named tw2tools.list_entries`.

- [ ] **Step 3: Write the implementation**

Create `script/tw2tools/list_entries.py`:

```python
"""CLI: parse archive entry records out of extracted .wd chunk files."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import parse_archive_entries


def collect_entries(path: Path, suffix_filter: str | None) -> list[dict]:
    chunk_files = sorted(path.glob("*.bin")) if path.is_dir() else [path]

    rows: list[dict] = []
    for chunk_file in chunk_files:
        data = chunk_file.read_bytes()
        for entry in parse_archive_entries(data):
            if suffix_filter and not entry.path.lower().endswith(suffix_filter.lower()):
                continue
            row = asdict(entry)
            row["source_chunk"] = chunk_file.name
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List archive entry records parsed from .wd chunk file(s)"
    )
    parser.add_argument("path", type=Path, help="A chunk .bin file or a directory of chunk files")
    parser.add_argument(
        "--filter",
        dest="suffix_filter",
        default=None,
        help="Only include entries whose path ends with this suffix, e.g. .eco",
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write the full entry table as JSON"
    )
    args = parser.parse_args()

    rows = collect_entries(args.path, args.suffix_filter)
    print(f"Found {len(rows)} entr{'y' if len(rows) == 1 else 'ies'}")
    for row in rows[:20]:
        print(f"  {row['source_chunk']}: {row['path']} type_id={row['type_id']} flags={row['flags']}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full table to {args.json_out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_list_entries.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/list_entries.py script/tests/test_list_entries.py
git commit -m "Add list_entries.py CLI for archive entry tables"
```

---

### Task 8: `search_text.py` CLI

**Files:**
- Create: `script/tw2tools/search_text.py`
- Create: `script/tests/test_search_text.py`

**Interfaces:**
- Consumes: `tw2tools.wd_format.search_text_multi(data: bytes, terms: list[str]) -> list[Match]` (Task 4).
- Produces: `collect_matches(path: Path, terms: list[str]) -> list[dict]`, and the `python -m tw2tools.search_text <path> --term TERM [...] [--json OUT]` CLI.

- [ ] **Step 1: Write the failing test**

Create `script/tests/test_search_text.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.search_text", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_search_text_finds_ascii_and_utf16(tmp_path):
    data = (
        b"padding"
        + "Casbrim".encode("ascii")
        + b"padding"
        + b"\x00\x00"
        + "Casbrim".encode("utf-16-le")
        + b"\x00\x00"
    )
    target = tmp_path / "sample.bin"
    target.write_bytes(data)
    json_out = tmp_path / "matches.json"

    result = _run(str(target), "--term", "Casbrim", "--json", str(json_out), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 2 match(es)" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    encodings = {row["encoding"] for row in rows}
    assert encodings == {"ascii", "utf-16-le"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_search_text.py -v`
Expected: FAIL — `No module named tw2tools.search_text`.

- [ ] **Step 3: Write the implementation**

Create `script/tw2tools/search_text.py`:

```python
"""CLI: search files for text under multiple encodings (ASCII, UTF-16LE)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import search_text_multi


def collect_matches(path: Path, terms: list[str]) -> list[dict]:
    files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]

    rows: list[dict] = []
    for file_path in files:
        data = file_path.read_bytes()
        for match in search_text_multi(data, terms):
            row = asdict(match)
            row["file"] = str(file_path)
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Search file(s) for text under multiple encodings")
    parser.add_argument("path", type=Path, help="A single file or a directory to search recursively")
    parser.add_argument(
        "--term", dest="terms", action="append", required=True, help="Search term (repeatable)"
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full match table as JSON"
    )
    args = parser.parse_args()

    rows = collect_matches(args.path, args.terms)
    print(f"Found {len(rows)} match(es)")
    for row in rows[:20]:
        print(f"  {row['file']} term={row['term']!r} encoding={row['encoding']} offset={row['offset']}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full match table to {args.json_out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_search_text.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/search_text.py script/tests/test_search_text.py
git commit -m "Add search_text.py CLI for multi-encoding text search"
```

---

### Task 9: `diff_saves.py` CLI

**Files:**
- Create: `script/tw2tools/diff_saves.py`
- Create: `script/tests/test_diff_saves.py`

**Interfaces:**
- Consumes: `tw2tools.wd_format.diff_byte_regions(a: bytes, b: bytes) -> list[DiffRegion]` (Task 5).
- Produces: the `python -m tw2tools.diff_saves <save_a> <save_b> [--min-size N] [--json OUT]` CLI.

- [ ] **Step 1: Write the failing test**

Create `script/tests/test_diff_saves.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.diff_saves", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_diff_saves_reports_changed_region(tmp_path):
    save_a = tmp_path / "a.save"
    save_b = tmp_path / "b.save"
    save_a.write_bytes(b"HEADER" + b"OLDVALUE" + b"FOOTER")
    save_b.write_bytes(b"HEADER" + b"NEWVAL!!" + b"FOOTER")
    json_out = tmp_path / "diff.json"

    result = _run(str(save_a), str(save_b), "--json", str(json_out), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 1 changed region(s)" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert rows[0]["op"] == "replace"
    assert bytes.fromhex(rows[0]["a_bytes"]) == b"OLDVALUE"
    assert bytes.fromhex(rows[0]["b_bytes"]) == b"NEWVAL!!"


def test_diff_saves_min_size_filters_small_regions(tmp_path):
    save_a = tmp_path / "a.save"
    save_b = tmp_path / "b.save"
    save_a.write_bytes(b"HEADER" + b"X" + b"FOOTER")
    save_b.write_bytes(b"HEADER" + b"Y" + b"FOOTER")

    result = _run(str(save_a), str(save_b), "--min-size", "4", cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 0 changed region(s)" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_diff_saves.py -v`
Expected: FAIL — `No module named tw2tools.diff_saves`.

- [ ] **Step 3: Write the implementation**

Create `script/tw2tools/diff_saves.py`:

```python
"""CLI: compare two save/header files and report the changed byte region."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import diff_byte_regions


def main() -> None:
    parser = argparse.ArgumentParser(description="Diff two Two Worlds II save (or header) files")
    parser.add_argument("save_a", type=Path, help="First save/header file")
    parser.add_argument("save_b", type=Path, help="Second save/header file")
    parser.add_argument(
        "--min-size", type=int, default=1, help="Skip regions smaller than this many bytes"
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full diff regions as JSON"
    )
    args = parser.parse_args()

    a_data = args.save_a.read_bytes()
    b_data = args.save_b.read_bytes()
    regions = diff_byte_regions(a_data, b_data)
    regions = [r for r in regions if max(len(r.a_bytes), len(r.b_bytes)) >= args.min_size]

    print(f"Found {len(regions)} changed region(s) (sizes: a={len(a_data)} b={len(b_data)})")
    for region in regions:
        print(
            f"  {region.op}: a[{region.a_start}:{region.a_end}] ({len(region.a_bytes)}B) -> "
            f"b[{region.b_start}:{region.b_end}] ({len(region.b_bytes)}B)"
        )

    if args.json_out:
        rows = [
            {**asdict(r), "a_bytes": r.a_bytes.hex(), "b_bytes": r.b_bytes.hex()} for r in regions
        ]
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full diff to {args.json_out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest script/tests/test_diff_saves.py -v`
Expected: PASS — both tests pass.

- [ ] **Step 5: Commit**

```bash
git add script/tw2tools/diff_saves.py script/tests/test_diff_saves.py
git commit -m "Add diff_saves.py CLI for byte-region save comparison"
```

---

### Task 10: Clean up legacy scripts and update notes

**Files:**
- Delete: all 21 legacy `script/*.py` files (not inside `tw2tools/` or `tests/`)
- Delete: all 7 legacy `script/*.txt` output files
- Delete: `script/+ $out +`
- Modify: `script/wd_extraction_notes.md`

**Interfaces:** none (no code interfaces; this is repo cleanup + documentation).

- [ ] **Step 1: Confirm the full legacy file list**

Run: `cd script && ls *.py *.txt && ls -la '+ $out +'`
Expected: lists exactly these `.py` files — `analyze_wd_entries.py`, `debug_entry_decode.py`, `decode_tw2_save.py`, `decode_tw2_save_structure.py`, `extract_analysis.py`, `extract_wd.py`, `inspect_chunk.py`, `inspect_tw2_quest_zlib.py`, `inspect_tw2_save.py`, `inspect_tw2_save_output.py`, `inspect_wd_block.py`, `inspect_wd_entry.py`, `inspect_wd_entry2.py`, `inspect_wd_structure.py`, `inspect_wdfiles.py`, `search_tw2_quest.py`, `search_tw2_quest_utf8.py`, `search_tw2_save.py`, `search_wdfiles_candidates.py`, `search_wdfiles_candidates2.py`, `search_wdfiles_raw.py` — these `.txt` files: `decoded_090001_TwoWorldsIISave.txt`, `inspect_tw2_save_output.txt`, `inspect_wdfiles_output.txt`, `search_tw2_quest_output.txt`, `search_tw2_quest_utf8_output.txt`, `search_wdfiles_candidates2_output.txt`, `search_wdfiles_raw_output.txt` — and the stray file `+ $out +`.

- [ ] **Step 2: Delete the legacy files**

```bash
cd script
git rm *.py *.txt
git rm '+ $out +'
cd ..
```

Expected: `git rm` reports 29 files removed (21 `.py` + 7 `.txt` + 1 stray file); `script/tw2tools/*.py` and `script/tests/*.py` are untouched since the glob only matches direct children of `script/`.

- [ ] **Step 3: Verify the new package still passes**

Run: `.venv/Scripts/python.exe -m pytest script/tests -v`
Expected: PASS — all tests from Tasks 1-9 still pass (the legacy scripts were never imported by the new package).

- [ ] **Step 4: Rewrite `script/wd_extraction_notes.md`**

Read the current file first, then replace its "Local files used for analysis" and "Next likely steps" sections, and correct the `word1`/`word4` example values, so the notes read:

```markdown
## Local files used for analysis

The legacy one-off scripts previously listed here were replaced by the
`tw2tools` package (see `docs/superpowers/specs/2026-07-10-wd-toolkit-design.md`
for the design, and `docs/superpowers/plans/2026-07-10-tw2-wd-toolkit.md` for
how it was built). Current tools, run from `script/`:

- `python -m tw2tools.extract <archive.wd> [-o out_dir]` — full zlib block extraction
- `python -m tw2tools.list_entries <chunk_file_or_dir> [--filter SUFFIX] [--json OUT]` — archive entry tables
- `python -m tw2tools.search_text <file_or_dir> --term TERM [...] [--json OUT]` — multi-encoding text search
- `python -m tw2tools.diff_saves <save_a> <save_b> [--min-size N] [--json OUT]` — byte-region diff between two saves

## Correction: real `word1`/`word4` values

Re-parsing `DLC3_PC_chunk_00000030.bin` with `tw2tools.wd_format.parse_archive_entries`
(a straightforward little-endian 4-word footer read) produced different
`word1`/`word4` values than originally hand-transcribed above for two
example entries. The corrected, code-verified values:

- `ActionSets\DRAGON_10_DEFAULT_TW2.act`: `word1=100663296` (0x06000000),
  `word2=335544325` (0x14000005, unchanged), `word3=56` (0x38, unchanged),
  `word4=503316480` (0x1e000000)
- `Scripts\Campaigns\Missions\DLC_3.eco`: `word1=520093696` (0x1f000000),
  `word2=3154116609` (0xbc000001), `word3=5` (unchanged in value, byte order
  differs from the original note), `word4=704643072` (0x2a000000)

The original values above were likely transcribed with inconsistent byte
ordering across fields. Treat the corrected values (and `tw2tools.wd_format`
as the source of truth) going forward — the `word1..word4` semantics are
still unresolved either way.

## File locations (as of 2026-07-10)

Real game data now lives under `files/Two Worlds 2/` (gitignored):

- `DLC3_PC.wd` — main DLC3 asset archive (~1.9GB)
- `DLC3_PC_POL.wd` — Polish localization archive (~1.3MB compressed), the
  most likely home for Polish quest-name strings like "Ekspercka przygoda
  poboczna: Bogowie i demony" (Expert Side Adventure) or "Casbrim"
- `saves/remote/NNNNNN.TwoWorldsIISave(_header)` — 572 sequential real save
  snapshots, usable with `diff_saves` to find quest-progress byte regions

## Next likely steps

- Run a full extraction of `DLC3_PC_POL.wd` and search it for the Casbrim /
  Expert Side Adventure strings (see the toolkit findings section below, if
  present, for results of this run).
- Determine whether `word1..word4` are offsets, checksums, or something else
  — the field is still unresolved even with corrected values.
- Use `diff_saves` across saves that bracket a specific quest state change
  to find candidate quest-progress byte regions independent of the `.wd`
  investigation.
```

Keep everything above `## Local files used for analysis` in the existing file unchanged (the archive format, decompressed chunk structure, and archive entry record structure sections are still accurate).

- [ ] **Step 5: Commit**

```bash
git add -A script/
git commit -m "Remove legacy scripts, correct notes, document tw2tools usage"
```

---

### Task 11: Real-data research run — Casbrim/Expert Side Adventure search

**Files:**
- Modify: `script/wd_extraction_notes.md` (append findings)

**Interfaces:** none — this task runs the finished toolkit against real data and records results; no new code.

- [ ] **Step 1: Full extraction of the Polish localization archive**

Run: `cd script && ../.venv/Scripts/python.exe -m tw2tools.extract "../files/Two Worlds 2/DLC3_PC_POL.wd" -o wd_extract`
Expected: exits 0, prints `Extracted N block(s) to wd_extract` where N should be close to the notes' previously-reported 189 successfully-decompressing blocks. Record the actual N.

- [ ] **Step 2: List all `.eco` entries across the full extraction**

Run: `../.venv/Scripts/python.exe -m tw2tools.list_entries wd_extract --filter .eco --json wd_extract/eco_entries.json`
Expected: exits 0, prints a count of `.eco` entries found. `wd_extract/eco_entries.json` is gitignored (lives under the already-ignored `wd_extract/`), so nothing needs to be added to `.gitignore`.

- [ ] **Step 3: Search for Casbrim and Expert Side Adventure strings**

Run: `../.venv/Scripts/python.exe -m tw2tools.search_text wd_extract --term Casbrim --term "Ekspercka przygoda poboczna" --json wd_extract/casbrim_search.json`
Expected: exits 0, prints a match count (may legitimately be 0 — record whichever it is; per the design spec, a confirmed absence in the fully-extracted archive is itself a useful finding, not a failure).

- [ ] **Step 4: Diff two adjacent real saves as a sanity check**

Run: `../.venv/Scripts/python.exe -m tw2tools.diff_saves "../files/Two Worlds 2/saves/remote/000000.TwoWorldsIISave" "../files/Two Worlds 2/saves/remote/000001.TwoWorldsIISave" --min-size 4 --json wd_extract/diff_0_1.json`
Expected: exits 0, prints one changed region (given the files differ in size, per the design spec's earlier size check) with sane byte ranges — not the entire file.

- [ ] **Step 5: Record findings in `script/wd_extraction_notes.md`**

Append a new section (fill in the actual N and match results from Steps 1-4 — do not leave placeholder text):

```markdown
## Toolkit findings (2026-07-10)

- Full extraction of `DLC3_PC_POL.wd` via `tw2tools.extract` produced N blocks
  (compare to the 189 previously reported).
- `.eco` entry count across the full extraction: <count from Step 2>.
- Casbrim / "Ekspercka przygoda poboczna" search across the full extraction:
  <found at file/offset/encoding, or "no matches found — the string is not
  present anywhere in DLC3_PC_POL.wd's decompressed data, so it likely lives
  in a different resource type not yet identified">.
- `diff_saves` between `saves/remote/000000` and `000001`: <op, byte range,
  and a short description of what changed, e.g. size/content of the region>.
```

- [ ] **Step 6: Commit**

```bash
git add script/wd_extraction_notes.md
git commit -m "Record full-extraction and Casbrim search findings"
```

---

## Self-Review Notes

- **Spec coverage:** directory layout (Task 1), `wd_format.py`'s four functions (Tasks 2-5), all four CLIs (Tasks 6-9), cleanup list (Task 10), and the research workflow / verification section (Task 11) are all covered.
- **Placeholder scan:** Task 11's Step 5 explicitly calls out not to leave placeholder text — the worker fills in real numbers from Steps 1-4.
- **Type consistency:** `ArchiveEntry`, `Match`, and `DiffRegion` field names are used identically across their defining task and every consuming CLI/test.
