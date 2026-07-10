# Two Worlds II `.wd` Extraction Notes

## Overview

This document summarizes what has been learned about the `DLC3_PC_POL.wd` archive and the extracted decompressed blocks, with a focus on the `.eco` metadata and how the archive entry records are structured.

## Archive format

- The `.wd` file contains many zlib-compressed blocks.
- Zlib signatures seen: `78 01`, `78 5e`, `78 9c`, `78 da`.
- There are 231 candidate zlib signatures in the raw archive.
- 189 of those offsets decompress successfully using `zlib.decompressobj()`.
- The total concatenated decompressed stream length is approximately `4,439,848` bytes.

## Decompressed chunk structure

- Decompressed chunks are written as `DLC3_PC_chunk_<offset>.bin` files. **Note:** the examples in this section come from `DLC3_PC.wd` (main ~1.9GB asset archive); later sections document `DLC3_PC_POL_chunk_*` files from the separate `DLC3_PC_POL.wd` archive (~1.3MB Polish localization), which has zlib blocks at the same offsets but different content.
- Example chunk file containing `.eco` metadata: `DLC3_PC_chunk_00000030.bin`.
- Chunks appear to contain metadata records for archive entries, not necessarily the raw file payloads.
- The first bytes of `DLC3_PC_chunk_00000030.bin` look like a header followed by an entry list: `.W.. -LevelsCopies-\nowe\Level 1...`

## Archive entry record structure

Entries are detected by:

- marker byte `$` or `*`
- ASCII path string
- terminator `0x01 0x00`
- 20-byte footer after the terminator

The footer is parsed as:

- `type_id` = 2 bytes, little-endian
- `flags` = 2 bytes, little-endian
- `word1` = 4 bytes, little-endian
- `word2` = 4 bytes, little-endian
- `word3` = 4 bytes, little-endian
- `word4` = 4 bytes, little-endian

### Example entries

- `ActionSets\DRAGON_10_DEFAULT_TW2.act`
  - `type_id = 63944`
  - `flags = 1`
  - `word1 = 0x00000006`
  - `word2 = 0x14000005`
  - `word3 = 0x00000038`
  - `word4 = 0x0000001e`

- `-LevelsCopies-\Map_20_C02_NewAC2.bmp`
  - `type_id = 8440`
  - `flags = 1`
  - `word1 = 0x000000c1`
  - `word2 = 0x38000095`
  - `word3 = 0x00000400`
  - `word4 = 0x00000024`

- `Scripts\Campaigns\Missions\DLC_3.eco`
  - `type_id = 9952`
  - `flags = 62`
  - `word1 = 0x003e26e0`
  - `word2 = 0x010000bc`
  - `word3 = 0x05000000`
  - `word4 = 0x0000002a`

## Important observations

- The first 2-byte `type_id` field is very likely the file size for these entries.
  - For `DLC_3.eco`, `9952` matches expected payload size semantics.
- `flags` appears to be a file-type/attribute flag field.
- The remaining 4 words are not direct offsets/lengths within the same decompressed chunk.
- For `DLC_3.eco`, `word1 = 0x003e26e0` is too large for the individual chunk length, but it may point into a larger concatenated stream or a separate data area.
- Simple extraction using `out_data[offset:offset+length]` does not work for many entries because the metadata offset/length values exceed the chunk boundaries.
- Searching the concatenated decompressed stream for the path `Scripts\Campaigns\Missions\DLC_3.eco` returned `-1`.
- A raw `ECO` signature exists at position `4,402,305` in the concatenated stream.
- Plain UTF-16 text appears around offset `0x3e26e0` in the concatenated stream, suggesting the record may point into a broader data structure.

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
- The file *payload* location still cannot be derived from an entry's
  metadata using the current record fields — path metadata is present, but
  nothing in `type_id`/`flags`/`word1..word4` yet maps to where the actual
  file bytes live.
- Even once `word1..word4` are resolved, mapping metadata to the real file
  payload for an entry like `DLC_3.eco` is a separate, still-open problem:
  `tw2tools.extract` only pulls out whole zlib blocks and `tw2tools.list_entries`
  only parses/prints entry metadata — neither performs metadata-to-payload
  mapping or extracts an individual file's bytes.

## Notes for AI models

- The archive uses mixed metadata and file payload data across zlib-decompressed blocks.
- Do not assume archive `offset` is always inside the decompressed block that contains the path string.
- Treat `type_id` as likely file size and `flags` as a small attribute field.
- The presence of `ECO` and UTF-16 text in the larger stream suggests mixed encoding and data layout.
- The extraction logic must be based on metadata mapping, not just local chunk offsets.

## Toolkit findings (2026-07-10)

- Full extraction of `DLC3_PC_POL.wd` via `tw2tools.extract` produced 189 blocks
  (matches the previously reported 189 exactly).
- `.eco` entry count across the full extraction: 0 (POL archive only; the
  `.eco`-bearing chunk `DLC3_PC_chunk_00000030.bin` referenced earlier in this
  document is from the separate `DLC3_PC.wd`, not re-extracted here; `list_entries
  wd_extract --filter .eco` found no entries with a `.eco` extension anywhere in
  the extracted blocks; `wd_extract/eco_entries.json` is an empty `[]`).
- Casbrim / "Ekspercka przygoda poboczna" search across the full extraction:
  **found** — 72 total matches (`search_text wd_extract --term Casbrim --term
  "Ekspercka przygoda poboczna"`), 68 for `Casbrim` and 4 for `Ekspercka
  przygoda poboczna`. All matches are UTF-16-LE or ASCII text embedded inside
  decompressed block files, not inside any `.eco`-typed entry:
  - `Casbrim` first appears in `DLC3_PC_POL_chunk_00017000.bin` at offset
    76423 (UTF-16-LE) as part of a tip string: `"Tip_128" -> "Casbrim i
    Lagin"`. The bulk of the remaining 67 `Casbrim` matches (both ASCII and
    UTF-16-LE encodings) are clustered in
    `DLC3_PC_POL_chunk_00090800.bin`, including an item identifier
    `"DLC3_Casbrim_Ring"` at offset 123373 (ASCII).
  - All 4 `"Ekspercka przygoda poboczna"` matches are UTF-16-LE and all
    located in `DLC3_PC_POL_chunk_00090800.bin`, at offsets 856935, 874707,
    882146, and 911558. Each is preceded by a `GROUP_<n>` label (e.g.
    `GROUP_66`, `GROUP_86`, `GROUP_106`, `GROUP_2`), consistent with a quest
    dialogue/text group table. The match at offset 911558 continues past
    the search window into `"Ekspercka przygoda poboczna: Bogow..."`,
    i.e. the string is truncated mid-way through the full localized quest
    title `"Ekspercka przygoda poboczna: Bogowie i demony"` — the full title
    is present in the archive, split only by the 32-byte search context
    window used for the excerpt, not by any encoding boundary.
  - Both strings live in the same localization-text block
    (`DLC3_PC_POL_chunk_00090800.bin`), strongly suggesting Casbrim (an NPC)
    and the "Ekspercka przygoda poboczna: Bogowie i demony" quest are part
    of the same quest/dialogue text group in this block, but neither string
    was found associated with any `.eco` entry — quest *progress* state is
    therefore still not evidenced anywhere in this `.wd` archive; this
    archive appears to hold only display/localization text, not
    save-compatible quest-state markers.
- `diff_saves` between `saves/remote/000000` (583786 bytes) and `000001`
  (581898 bytes): exactly **one** changed region — a single `replace` op,
  `a[2088:583786]` (581698 bytes) -> `b[2088:581898]` (579810 bytes). The
  first 2088 bytes of both saves are byte-identical (a fixed-size
  header/preamble), and essentially the entire remainder of the file
  differs as one contiguous replaced block reflecting the size delta
  (-1888 bytes) between the two snapshots — consistent with a
  variable-length serialized game-state section (inventory/quest/world
  state) that grows or shrinks between saves, rather than a small,
  localized quest-flag toggle. Pinpointing a quest-specific byte range
  will require diffing saves that bracket a single, isolated quest-state
  change (see "Next likely steps" above), not just two sequential
  autosaves.
