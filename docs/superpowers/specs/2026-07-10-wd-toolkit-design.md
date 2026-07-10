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

The `.wd` archive and save file currently live only on that other machine and
are not available this session. `script/extracted_wd/` already holds 50
decompressed chunk `.bin` files (~80MB, gitignored) from a partial prior
extraction (the notes report 189 zlib blocks decompress successfully, so this
is incomplete).

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
  wd_extraction_notes.md   # kept, updated to reference the new toolkit
  extracted_wd/            # kept (gitignored), existing 50 chunks
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

`ArchiveEntry` and `Match` are simple `dataclasses`.

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

### Research workflow this enables

The concrete next investigative step (not solved by this toolkit itself, but
what it's built to support):

1. Re-run `extract.py` against the full `.wd` archive once it's accessible
   again, to get all 189 blocks instead of the current 50.
2. Run `search_text.py` against the extracted chunk directory with
   `--term Casbrim --term "Ekspercka przygoda poboczna"` (and other quest
   name variants) to find which chunk/offset actually carries that text,
   since it wasn't in the save file.
3. Cross-reference that offset against `list_entries.py` output for the same
   chunk to see whether any entry's `word1..word4` footer values correlate
   with a nearby offset — the open question from the notes.

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

The `.wd` archive and save file are not available on this machine this
session, so verification is necessarily limited to the existing 50 extracted
chunks:

- `list_entries.py` run against `script/extracted_wd/DLC3_PC_chunk_00000030.bin`
  reproduces the entries already documented in the notes (e.g. `DLC_3.eco`
  with `type_id=9952`, `flags=62`; `ActionSets\DRAGON_10_DEFAULT_TW2.act`).
- `search_text.py` run against the same chunk finds `TwoWorldsQuests.eco`
  (known to be present per `inspect_tw2_save_output.txt`'s findings).

Full-archive extraction (`extract.py` against the real `.wd` file) and the
actual Casbrim/Expert Side Adventure search cannot be verified until the
archive is copied onto this machine in a future session — this is a known
limitation, not a gap in the plan.
