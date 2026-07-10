# Two Worlds II `.wd`/`.eco` Research Toolkit — Design

## Background

`two_worlds_2_fix` is a reverse-engineering project targeting the Two Worlds II
`.wd` archive format and the `.eco` quest-definition files it contains, plus
the `.TwoWorldsIISave` save-game format. The goal is to understand how quest
progress is tracked, with a particular interest in the Polish-localized quest
"Ekspercka przygoda poboczna: Bogowie i demony" (Expert Side Adventure) and an
NPC named "Casbrim".

Findings so far are recorded in `script/wd_extraction_notes.md`:
archive entries are detected via a `$`/`*` marker, an ASCII path string, a
`0x01 0x00` terminator, and a 20-byte footer (`type_id`, `flags`,
`word1..word4`). The semantics of `word1..word4` are not yet resolved, and a
search for the Casbrim/Expert Side Adventure Polish strings against the save
file found no matches — that search was never run against the `.wd` chunk
data itself, which is the more likely location for quest name text.

## Problem with the current state

An initial round of exploration produced ~20 one-off Python scripts and
several `*_output.txt` dumps in `script/`. All of them:

- hardcode absolute paths from a *different* machine
  (`C:\Users\patry\OneDrive\...`, `C:\Program Files (x86)\Steam\...`), none of
  which exist on this machine
- some write output into an unrelated folder from another project
  (`C:\Users\patry\Repos\dbt-course\...`)
- duplicate the same zlib-scanning and entry-parsing logic across many files,
  so a fix to the still-evolving entry-record format understanding would need
  to be copied into several places

The `.wd` archive and save file previously only lived on another machine.
Since the initial design pass, the user has copied real data onto this
machine under `files/` (gitignored):

- `files/Two Worlds 2/DLC3_PC.wd` — the main DLC3 asset archive (~1.9GB)
- `files/Two Worlds 2/DLC3_PC_POL.wd` — the Polish localization archive
  (~1.3MB compressed), matching the size referenced in the existing notes —
  this is the more likely home for the Polish quest-name strings
- `files/Two Worlds 2/saves/remote/NNNNNN.TwoWorldsIISave` (+ matching
  `_header` files) — 572 sequential save snapshots from actual play sessions,
  spanning Nov 2019 (`000000`) through later saves. Both the save and header
  file sizes vary slightly between consecutive saves (e.g. `000000` is
  583786 bytes, `000001` is 581898), so exact-offset diffing won't work
  directly — a sequence-alignment based diff is needed.

`script/extracted_wd/` still holds 50 decompressed chunk `.bin` files (~80MB)
from a prior partial extraction against the (now available) `.wd` file; a
full extraction can now be run for real.

## Design

### Directory layout

```
script/
  tw2tools/
    __init__.py
    wd_format.py       # core parsing logic (shared)
    extract.py         # CLI: extract all zlib blocks from a .wd archive
    list_entries.py    # CLI: parse archive entry records from chunks -> table
    search_text.py     # CLI: multi-encoding text search across files/dirs
    diff_saves.py      # CLI: sequence-aligned byte diff between two saves
  wd_extraction_notes.md   # kept, updated to reference the new toolkit
  extracted_wd/            # kept (gitignored), existing 50 chunks
files/
  Two Worlds 2/
    DLC3_PC.wd               # gitignored, main asset archive
    DLC3_PC_POL.wd            # gitignored, Polish localization archive
    saves/remote/*.TwoWorldsIISave(_header)  # gitignored, 572 save snapshots
```

No script hardcodes an absolute path. Every input path is a required CLI
argument; output directories default to a relative path (e.g. `./wd_extract`)
but are always overridable via a flag.

### Core module: `tw2tools/wd_format.py`

Single-sourced logic that is fragile or likely to change as understanding of
the format improves:

- `find_zlib_offsets(data: bytes) -> list[int]` — scan for the four known
  zlib signature byte pairs (`78 01`, `78 5e`, `78 9c`, `78 da`)
- `decompress_all_blocks(data: bytes) -> Iterator[tuple[int, bytes]]` —
  attempt decompression at every candidate offset, yielding
  `(offset, decompressed_bytes)` for each block that succeeds, skipping
  failures (no cap on block count)
- `parse_archive_entries(chunk_bytes: bytes) -> list[ArchiveEntry]` — the
  marker + path + 20-byte-footer parser from the notes; returns a structured
  record (path, type_id, flags, word1, word2, word3, word4, marker_pos,
  data_pos) per entry
- `search_text_multi(data: bytes, terms: list[str]) -> list[Match]` — for
  each term, search the raw bytes under three encodings: ASCII, UTF-16LE, and
  UTF-16LE without a BOM (needed for Polish diacritics such as in "Ekspercka
  przygoda poboczna"); return term, encoding used, byte offset, and a
  hex+decoded context snippet per hit
- `diff_byte_regions(a: bytes, b: bytes) -> list[DiffRegion]` — use
  `difflib.SequenceMatcher` (opcodes over the raw bytes) to find contiguous
  `replace`/`insert`/`delete` regions between two save files, returning each
  region's byte range in both files and the old/new bytes — robust to the
  slight size shifts observed between consecutive saves

`ArchiveEntry`, `Match`, and `DiffRegion` are simple `dataclasses`.

### CLI scripts

- **`extract.py <archive.wd> [-o out_dir]`** — runs
  `decompress_all_blocks` over the whole archive (removing the old `--max 10`
  cap) and writes one `<stem>_chunk_<offset:08x>.bin` file per block to
  `out_dir` (default `./wd_extract`). Prints a summary count of blocks found
  vs. successfully decompressed.
- **`list_entries.py <chunk_file_or_dir> [--filter SUFFIX] [--json OUT]`** —
  runs `parse_archive_entries` across a single chunk file or every `.bin` file
  in a directory, optionally filtered by path suffix (e.g. `.eco`), and
  prints (or writes as JSON) a consolidated table including which source
  chunk each entry came from.
- **`search_text.py <file_or_dir> --term TERM [--term TERM ...] [--json OUT]`**
  — runs `search_text_multi` against a single file or every file in a
  directory (chunks or the save file alike), printing each match's file,
  term, encoding, offset, and context.
- **`diff_saves.py <save_a> <save_b> [--min-size N] [--json OUT]`** — runs
  `diff_byte_regions` between two save files (or two header files), filters
  out trivial/tiny regions below `--min-size`, and prints each changed
  region's offset range and old/new bytes (hex + best-effort decoded text).
  Designed to be run across consecutive saves in `saves/remote/` to narrow
  down which byte regions correlate with a specific quest's progress, by
  comparing saves taken right before/after that quest state changed.

### Research workflow this enables

The concrete next investigative steps (not solved by this toolkit itself, but
what it's built to support), now runnable against real data:

1. Run `extract.py` against `files/Two Worlds 2/DLC3_PC_POL.wd` to get all
   ~189 blocks (not just the 50 from the earlier partial run), and against
   `DLC3_PC.wd` if useful.
2. Run `search_text.py` against the extracted chunk directory with
   `--term Casbrim --term "Ekspercka przygoda poboczna"` (and other quest
   name variants) to find which chunk/offset actually carries that text,
   since it wasn't in the save file.
3. Cross-reference that offset against `list_entries.py` output for the same
   chunk to see whether any entry's `word1..word4` footer values correlate
   with a nearby offset — the open question from the notes.
4. Run `diff_saves.py` across pairs of consecutive saves in
   `saves/remote/` — particularly around whichever save numbers correspond
   to progressing the Casbrim/Expert Side Adventure quest — to find which
   byte regions change, independent of the `.wd`/`.eco` investigation.

### Cleanup

Delete:
- All 20 existing scripts directly under `script/*.py`
- All `script/*_output.txt` files
- `script/decoded_090001_TwoWorldsIISave.txt`
- The stray `script/+ $out +` file

Keep:
- `script/wd_extraction_notes.md` — update to reference the new toolkit
  location and record the file-location caveat (archive/save currently only
  on another machine)
- `script/extracted_wd/*.bin` — existing 50 chunks, still useful until a full
  re-extraction is possible

### Verification

Real data is now available on this machine, so verification can run
end-to-end:

- `extract.py` run against `files/Two Worlds 2/DLC3_PC_POL.wd` produces
  ~189 chunks (matching the notes' block count), including one whose entries
  match `list_entries.py`'s output for the previously-known
  `DLC3_PC_chunk_00000030.bin` (e.g. `DLC_3.eco` with `type_id=9952`,
  `flags=62`; `ActionSets\DRAGON_10_DEFAULT_TW2.act`).
- `search_text.py` run against the full extracted chunk set finds
  `TwoWorldsQuests.eco`, and is also run for real with
  `--term Casbrim --term "Ekspercka przygoda poboczna"` to see whether either
  string turns up anywhere in the archive data.
- `diff_saves.py` run against two adjacent files in `saves/remote/` (e.g.
  `000000` and `000001`) produces a non-empty, sane list of changed regions
  (not the entire file, given they're mostly-similar snapshots).

If the Casbrim/Expert Side Adventure strings still aren't found anywhere in
the `.wd` data even after a full extraction, that itself is a useful finding
to record in the notes (e.g. localized quest names may live in a different
archive/resource type not yet identified) rather than a plan failure.
