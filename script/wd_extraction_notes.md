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

- ~~Run a full extraction of `DLC3_PC_POL.wd` and search it for the Casbrim /
  Expert Side Adventure strings~~ — done, see "Toolkit findings" below.
- ~~Use `diff_saves` across saves that bracket a specific quest state
  change~~ — tried exhaustively (all 285 consecutive pairs in
  `saves/remote/`, plus decompressed-content diffing); see "Batch save-diff
  scan" above. **Blocked**: no available save pair, however close in time,
  isolates a small enough region.
- ~~Parse the decompressed blob's actual record structure instead of
  diffing it as opaque bytes~~ — done for one field: see "Save summary
  block decoded" above. Decoded the currently-tracked-quest field, but not
  yet the full quest journal (all accepted/completed quests).
- ~~Find the full quest journal / per-quest completion-state structure~~ —
  found the generic named-flag record system and a `find_named_records`
  scanner + `flag_timeline` CLI for it (see "Named flag/record system
  found" above), and pinpointed exactly when Casbrim-related content loads
  (save `000181`).
- ~~Decode the generic record's trailing value fields / try more candidate
  names~~ — done, see "Naming-convention dead end" above. **Genuinely
  blocked** via name-based searching: no `Completed`/`Done`/`Accepted`
  -style name exists anywhere in the ~3199 names scanned, and the two
  `*Triggered` flags found have per-trigger-type-constant (not
  per-progress) values. This path is exhausted without new information —
  continuing to guess candidate names has hit diminishing returns.
- ~~Get a purpose-made save pair and diff it~~ — **done, and it worked.**
  See "Breakthrough: quest-progress found via a purpose-made save pair"
  above. The user provided `files/quest_saves/000281.TwoWorldsIISave`
  (before accepting) / `000282.TwoWorldsIISave` (after accepting).
  Whole-file diffing still failed the same way, but diffing the *sets of
  named records* between the two saves found both a new marker
  (`SE_Garden_D_GAP`) and, more importantly, the per-entity property-bag
  structure (`PCQ`/`PSDN`/`PQUS`/`Lector`/`PUMN`) — confirmed `PCQ` is the
  quest-relevant field by observing only 2 of 16 `PCQ` records change
  between the saves, one next to Casbrim, the other next to the
  independently-changing NPC (Queen Arbellen) the user mentioned. Added
  `tw2tools.wd_format.parse_property_bags` +
  `tw2tools.entity_property` CLI for this.
- ~~Find the value `PCQ` takes on completion~~ — attempted via ID-matching
  against `.wd` dialogue content; see "Quest-ID matching approach:
  confirmed dead end" above. **Genuinely blocked**: `PCQ`'s value doesn't
  reference this quest's own dialogue-ID namespace (checked exhaustively,
  zero matches across all 286 saves). Would still need another
  purpose-made save pair bracketing the quest's turn-in/completion moment
  to observe the real completion value directly (the ID-matching shortcut
  doesn't work, but direct before/after observation — the technique that
  *did* work for acceptance — still would).
- ~~Try editing the save to make Casbrim appear/progress the quest~~ —
  done; see "Save-editing experiment: patched Casbrim's position" above.
  **Position/rotation editing works mechanically** (`patch_zlib_block`,
  confirmed by the user loading the patched save) but **does not progress
  quest logic** — presence alone isn't causally linked to script-side
  quest state, which still requires `.eco` decoding to control directly.
- ~~Check whether more than one Casbrim-related spot exists~~ — yes: found
  5 distinct named Casbrim position markers in `DLC3_PC.wd`'s level data
  (see "Multiple named Casbrim positions" above). This reframes the
  original "broken" position as a different *legitimate* named spot
  (`casbrim here`), not corrupted data — the real bug is in whatever
  script logic selects which named spot to use for a given story stage,
  which we can't see from the save file alone.
- ~~The `.wd`/`.eco` payload-location problem~~ — **solved**, though not via
  `word1..word4` (see "Major breakthrough: `.eco` payload location solved"
  above): `.eco` files are independent zlib blocks with their own `"ECO"`
  magic header and embedded name. `find_eco_files` locates and identifies
  all 21 real compiled scripts in `DLC3_PC.wd`, including the main
  `TwoWorlds2Quests` script. Confirmed the complete property-bag key
  vocabulary (`PCQ`, `PSDN`, `PQUS`, `Lector`, `PUMN`, `PQTIMED`, `PQBS`) as
  literal engine strings there too.
- **Deliberately stopped here** (user decision, see "Stopping point"
  above) before decoding the actual bytecode/opcode format — that's a
  fundamentally bigger, separately-scoped undertaking (closer to writing a
  disassembler for an unknown VM) than the find-and-correlate work in this
  document. The numeric-ID-indexed quest table and the level/quest script
  logic that selects between named position markers remain open, and would
  be the natural next things to attack if/when that larger project is
  picked up — starting point: `find_eco_files`, the confirmed property-key
  vocabulary, and the ordered (non-deduplicated) string table's revealed
  `QTD → QSD → QUEST_GIVEN → QFD → QCD → QUEST_SOLVED` lifecycle pattern.
- ~~Determine whether `word1..word4` are offsets, checksums, or something
  else~~ / ~~find the file payload location from entry metadata~~ — pursued
  with a real 7,057-entry statistical sample from the full `DLC3_PC.wd`
  archive; see "`word1..word4` / payload-location investigation with a
  real large sample" above. **Genuinely blocked** via static analysis:
  local-offset, global-concatenated-stream-offset (multiple field
  interpretations), CRC32-of-path-hash, and raw-archive-file-offset were
  all tested against a real anchor entry and none produced a valid file
  signature. Refined understanding: `type_id` plausibly = size, `flags` =
  small attribute bitfield, but the "word1/word4 only carry their high
  byte" pattern seen on one entry does **not** generalize (only ~18% of
  entries have this). Next step here would need dynamic analysis (a
  debugger attached to the running game while it loads a known asset) —
  not more static-guessing, which has now covered every cheap-to-test
  interpretation without success.

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

## Batch save-diff scan (2026-07-10) — no small regions found anywhere

Added `tw2tools.scan_saves` (runs `diff_byte_regions` across every consecutive
pair in a save-history directory and reports only regions at or below a size
threshold) and ran it against all 286 real saves in `saves/remote/`
(285 consecutive pairs):

- With `--max-region-size 256`: **0 pairs** anywhere in the full 285-pair
  history produced a small region. Every single pair's one changed region
  spans from a fixed offset (2088 bytes into the raw file) all the way to
  EOF, exactly like the 000000→000001 example above.
- The raw save file itself contains one zlib-compressed block (offset
  `341692` in `000000.TwoWorldsIISave`, decompressing to ~2.4MB) — the bulk
  game-state payload. The ~341KB before it is plaintext and (per the earlier
  `090001.TwoWorldsIISave` legacy exploration) appears to be a resource/mod
  manifest, not quest state.
- **Decompressing that blob and diffing the decompressed content doesn't
  help either.** Sampled across the full save range (indices 5, 20, 50, 100,
  150, 200, 250) and also across the *closest-in-real-time* pairs (by file
  mtime — e.g. `000119`→`000120` only 12 seconds apart, `000096`→`000097`
  30 seconds apart): every single pair, including the 12-second one, still
  shows a single changed region covering essentially the entire decompressed
  blob (>99% of its bytes), not a small isolated diff.
- Decompressed blob sizes also swing wildly between adjacent save numbers
  (e.g. 4.47MB → 2.86MB → 3.96MB across saves 5/6/20/21), which combined with
  the always-100%-changed result suggests the save's state section is either
  itself internally re-compressed/re-encoded per save in a way that
  scrambles byte offsets on any change, or contains a large volume of
  continuously-changing simulation data (NPC/creature positions, timers,
  weather/RNG state, etc.) unrelated to quest progress, which is enough by
  itself to defeat a byte-level LCP/LCS diff even between saves seconds
  apart.

**Conclusion:** simple byte-diffing (even after decompression) cannot
isolate a quest-progress flag from these particular saves — the available
`saves/remote/*` snapshots are not close enough together in a *content*
sense (even when close in *time*) for the signal to stand out from
unrelated per-save noise. This blocks further progress via this specific
technique without either (a) two saves that are known to bracket *only* a
single quest-state change with everything else frozen (e.g., quicksave,
interact with exactly one quest NPC, quicksave again, ideally without
walking anywhere in between), or (b) actually parsing the decompressed
blob's internal record structure rather than diffing it as an opaque byte
stream.

## Save summary block decoded (2026-07-10) — first working quest-tracking field

Pursued option (b) above: instead of diffing the decompressed blob as opaque
bytes, looked for actual internal structure. Found a small, human-readable
save-summary block used for the save-browser UI, present in **both** the
main save file's decompressed blob **and**, unencoded, in the small
`_header` file (no decompression needed for the header — much faster).

**Format:** a single length-prefixed UTF-16LE string: `[uint32 LE char
count][UTF-16LE text]`, anchored by the literal text `"Miejsce:"` (Polish
for "Location:"). The string contains 5 newline-separated `Key: Value`
lines:

```
Miejsce: <location>
Czas gry: <play time, HH:MM>
Aktywna misja: <currently tracked quest name, or "brak" ("none")>
Poziom: <character level>
PD: <experience>/<experience to next level>
```

Added `tw2tools.wd_format.parse_save_summary(data) -> SaveSummary | None`
(finds the anchor, reads the length prefix 4 bytes before it, decodes and
splits the fields) and a `tw2tools.save_summary` CLI
(`python -m tw2tools.save_summary <path> [--json OUT]`) that prefers the
fast `_header` file and only decompresses the main save file as a fallback.

**Ran it across all 286 saves** (`save_summaries.json`): got a full
"currently tracked quest" timeline (151 distinct mission-name transitions,
from the base-game Polish campaign through what appear to be Pirates-DLC
missions in English mid-history, and later DLC3/Sharyjska-forest content).

**Casbrim / "Ekspercka przygoda poboczna" result:** still **not found** as
the tracked `Aktywna misja` value in any of the 286 saves — but save
`000203`'s location IS `"Puszcza Sharyjska"` (Sharyjska Forest, exactly the
DLC3 zone this quest belongs to), with the tracked mission there being
`"Las driad"` (the main DLC3 story quest), not the Casbrim side quest.
Saves 202-208 trace the player moving through that zone tracking only the
main story chain. This means either the side quest was never accepted in
this playthrough, or it was accepted but never selected as the active/HUD
quest at the moment of any of these particular saves — this field only
records the single *currently tracked* quest, not the full quest journal
(all accepted/in-progress/completed quests), so a passively-accepted side
quest that's never manually tracked would not appear here even if "active"
in the game's internal sense.

**What this does answer for the main goal:** we now have a real, decoded,
working field for *a* quest-progress signal (which quest the player has
selected as active, per save) — a genuine first success, just not the
specific Casbrim/Expert-Side-Adventure signal originally sought. The full
per-quest completion/acceptance state (which would show Casbrim regardless
of tracking) is still inside the decompressed blob somewhere, unlocated.

## Named flag/record system found (2026-07-10) — pinpointed save 181, but it's zone-load, not quest-completion

Directly searched every save's decompressed blob (not just the tracked-quest
field) for the literal strings `Casbrim` / `Ekspercka przygoda poboczna` /
`Bogowie i demony`. Result: `Casbrim` (ASCII) **is** present, in 105 of the
286 saves (`000181`-`000280`, plus separate save slots `020001`, `090000`-
`090003`) — but the two Polish quest-title phrases are still never found as
raw strings inside any save.

Inspecting the bytes around each `Casbrim` hit revealed a generic named
key-value record format used throughout the decompressed blob for
script/world state: `[uint32 LE name length][ASCII name][value bytes...]`.
Added `tw2tools.wd_format.find_named_records(data, min_length=3,
max_length=64) -> list[NamedRecord]` (generic scanner for this format,
~0.4s for a 2.4MB save blob) and used it to enumerate all ~3200 candidate
names in save `000181`. Casbrim-related names found:

- `CasbrimTriggered` — a named flag record; trailing value is constant
  `(0, 9999, 0, 0, 0)` (as `uint32` words) everywhere it appears — looks
  like a fixed "fired" sentinel, not an incrementing counter.
- `DLC3_CHANCELLOR_CASBRIM` — confirms Casbrim's in-game title is
  "Chancellor Casbrim".
- `ShadinarGardenCasbrim`, `ShadinarCasbrimOffice` — named locations (his
  garden/office in Shadinar, the DLC3 hub city).
- `PortraitUpCasbrim` — a dialogue-portrait UI state name.
- `DLC3_Casbrim_Ring` — an item identifier (matches the `.wd` archive
  localization finding from the earlier toolkit run).
- Also found (not Casbrim-specific but relevant): `Quests\TWII_DLC_SP3.dat`
  /`.lan`/`.qtx` — likely the internal codename for this DLC's quest data
  file ("SP3" plausibly "Side Plot/Adventure 3"), but only as a
  file-manifest reference, not a distinct per-player completion flag.

Added `tw2tools.flag_timeline` CLI (`python -m tw2tools.flag_timeline
<saves_dir> --name NAME [...] [--json OUT]`) to track named-flag
presence/absence across a save history using the exact names above, and ran
it against all 286 saves. **All six Casbrim-related flags transition from
absent to present at the exact same save: `000180` (absent) → `000181`
(present)**, and stay present through every later save. Because *all* of
them — including the unrelated-seeming item (`DLC3_Casbrim_Ring`) and
location names — flip together at one single save, this is almost
certainly a **one-time zone/NPC-content load event** (entering Shadinar,
where Chancellor Casbrim resides, for the first time), not a per-quest-step
completion marker. No distinct flag using an "SP3"/"SideAdventure"/"Expert"
naming convention was found to represent quest acceptance or completion
specifically.

**Where this leaves the main goal:** we now have three real, decoded,
working signals — the tracked-quest field, the zone-load flag batch, and a
generic named-record scanner for finding more — but none of them yet
distinguish "Casbrim's side quest was accepted/completed" from "the player
entered the zone where Casbrim lives." The specific per-quest
accept/complete state is either (a) tracked under a numeric quest ID rather
than a name string (would need parsing an ID-indexed table, not
name-search), or (b) tracked under a completion-flag name we haven't
guessed yet — `find_named_records` makes guessing-and-checking new
candidate names fast, but the next real target is understanding the
generic record's value-field layout (the `(0, 9999, 0, 0, 0)` trailing
words) well enough to tell a "not yet true" record from a "true" one,
rather than only detecting a record's mere presence.

## Naming-convention dead end (2026-07-10) — value fields are static constants, not progress

Followed up on both open items above:

- **Naming-convention sweep:** enumerated all ~3199 distinct names in save
  `000181` and grepped for common completion-style suffixes/keywords —
  `Completed`, `Complete`, `Done`, `Finished`, `Accepted`, `Started`:
  **zero matches for any of them, anywhere in the save.** `Triggered` only
  matches two names in the whole save: `AbeTriggered` and
  `CasbrimTriggered` (`Abe` being a different NPC). `Active`/`Quest`
  substring matches are all item/file-manifest names
  (`DLC3_QUESTWAND_1..3`, `Quests\TWII_DLC_SP3.dat/.lan/.qtx`,
  `INV_PLACEHOLDER_QUESTLOG`, `DLC3_Active_telestone`, etc.), not
  player-progress flags. This strongly suggests quest accept/complete state
  is **not** tracked via named string flags at all in this record system —
  the `*Triggered` records look like a narrow one-off convention for a
  couple of specific story/dialogue beats, not a general quest tracker.
- **Value-field check across save slots:** compared `CasbrimTriggered`'s
  and `AbeTriggered`'s trailing 5 `uint32` words across saves `000181`,
  `000200`, `000250`, `000280`, and the other save slots `020001`,
  `090000`-`090003` (different characters/campaigns). Every single
  occurrence of `CasbrimTriggered` has the identical value
  `(0, 9999, 0, 0, 0)`; every occurrence of `AbeTriggered` has
  `(0, 16666, 0, 0, 0)` — different from Casbrim's, but *also* constant
  everywhere it appears. This means `9999`/`16666` are almost certainly
  static per-trigger-type constants baked into the game's script/trigger
  definition (e.g. a trigger or dialogue-line ID), not a save-specific
  progress counter — the record's mere *presence* really does appear to be
  the only meaningful signal for these two flags, and that signal reads as
  "one-time story beat fired," not "side quest completed."

**Honest conclusion:** name-based searching for a Casbrim-quest-completion
flag has hit a real dead end with the current save data and this record
system. We have not found any evidence — positive or negative — that the
"Ekspercka przygoda poboczna: Bogowie i demony" side quest was ever
specifically accepted or completed in this playthrough; we've only shown
that the player loaded the NPC/zone content Casbrim belongs to. Also worth
being explicit: nothing found so far *proves* `CasbrimTriggered` is even
related to this specific side quest rather than some other Casbrim
interaction (e.g. a generic first-meeting dialogue) — the link is
NPC-name-based, not quest-ID-based.

## `word1..word4` / payload-location investigation with a real large sample (2026-07-10)

Switched to the `.wd`/`.eco` side per user direction. Previous analysis of
`word1..word4` was based on just 2-3 hand-picked entries from one 1.4MB
chunk. This time, decompressed the **entire** 1.9GB `DLC3_PC.wd` archive
in memory (no chunk files written to disk — ~20s to decompress 22,318
blocks totaling ~4.9GB, using `decompress_all_blocks` + `parse_archive_entries`
directly), yielding **7,057 real archive entries** — a genuine statistical
sample instead of a handful of examples.

**Refined/validated the earlier word-order correction.** The
`-LevelsCopies-\Map_20_C02_NewAC2.bmp` entry (the exact example from the
original hand-transcribed notes) now has a fully-explained discrepancy:
- `word2` and `word3` match the original notes **exactly**, no correction
  needed: `word2 = 0x38000095`, `word3 = 0x00000400` (1024).
- `word1` and `word4` match the original notes only in their **high byte**:
  `word1 = 0xc1000000` (high byte `0xc1` = the original note's
  `word1 = 0x000000c1`), `word4 = 0x24000000` (high byte `0x24` = the
  original note's `word4 = 0x00000024`).
- Checked this "low 3 bytes are padding/unused, only the high byte of
  word1/word4 carries a small meaningful value" idea against the full
  7,057-entry sample: **it does not hold universally** — only ~18% of
  entries have `word1`'s or `word4`'s low 3 bytes equal to zero (word2: 1.6%,
  word3: 0.4%). So the "high byte only" pattern seen for this one BMP entry
  is not a fixed rule for the whole footer format; `word1`/`word4` do carry
  real information in their low bytes for most entries. `type_id` varies
  plausibly with per-file size across a `.dds`/`.bmp` sample (spanning
  ~6.8KB-60KB, consistent with small game textures), supporting the
  existing "likely a size field" hypothesis. `flags` takes small
  repeating values (0, 1, 3, 56, 57, 62, ...), consistent with a small
  bitfield/attribute set.

**Tested and falsified several payload-location hypotheses** for the
`Map_20_C02_NewAC2.bmp` anchor entry (`type_id=8440, word1=3238002688,
word2=939524245, word3=1024, word4=603979776`), checking each candidate
byte position for a recognizable file signature (`BM` for BMP, `DDS ` for
DDS) or otherwise plausible content:
- **Local offset within the entry's own decompressed chunk** (`word3=1024`
  as a byte offset into the 1.4MB metadata chunk): bytes at that position
  are more metadata-shaped, not a BMP header.
- **Global offset into the full ~4.9GB concatenated decompressed stream**
  (built the actual cumulative offset table across all 22,318 blocks and
  checked): tried `word1`, `word2`, `word4` both raw and with only the low
  3 bytes — none land on a `BM`/`DDS ` signature. One (`word2` low-3-bytes
  interpreted locally) happened to land back inside the *same metadata
  chunk* near a `.bmp` extension fragment — a coincidental hit on
  manifest text, not a payload.
- **CRC32 of the path string** (as a hash-table-lookup key, several
  case/slash variants tried): no match against any of `word1..word4` or
  `type_id`.
- **Raw offset into the original compressed archive file** (not the
  decompressed stream — `word1` exceeds the 1.9GB file size so is ruled out
  immediately; `word2`/`word4` are in-range but the bytes there are neither
  a zlib signature nor a recognizable file header).

**Honest conclusion:** the payload-location mechanism is still unresolved,
now having ruled out every direct-offset/hash interpretation that's cheap
to test from static analysis alone. Likely explanations for what's left:
the footer fields may reference an indirect lookup structure (an index
table elsewhere in the archive, keyed by something not yet identified) that
static field-guessing can't find by inspection; or correctly decoding this
would need dynamic analysis (attaching a debugger to the actual game
process while it loads a known asset, to see which field is used and how)
rather than further static guessing, which has now covered every
"obvious" interpretation without success.

## Breakthrough: quest-progress found via a purpose-made save pair (2026-07-10)

The user provided exactly what earlier notes called for: `files/quest_saves/000281.TwoWorldsIISave`
(right before accepting the Expert Side Adventure quest from Casbrim) and
`000282.TwoWorldsIISave` (right after accepting it), noting that an
unavoidable second questline also updated at the same moment (talking to
Casbrim triggers updates in both).

**Whole-file/decompressed-blob diffing still doesn't help** — even this
tightly-bracketed pair (file sizes differ by only ~200 bytes) produces the
same single "changes from offset 2088 to EOF" region as every other pair
tried. The trailing-noise problem is real regardless of how minimal the
actual change is.

**But comparing the *set of named records* between the two saves worked.**
Ran `find_named_records` on both saves' decompressed blobs and diffed the
resulting name sets: one genuinely new record appeared in save `000282`
that wasn't in `000281`: `SE_Garden_D_GAP` (immediately followed by what
look like 3D position floats in the same value range as Casbrim's own
position — almost certainly a new marker/trigger spawned in Casbrim's
garden as part of the quest's next stage). ("SE" plausibly "Side
Event"/"Side Encounter".)

**Found and decoded the save's per-entity property-bag structure.**
Comparing all occurrences of the literal 3-character tag `PCQ` between the
two saves (found by locating each `PCQ`'s own length-prefix, since `PCQ` is
itself a length-prefixed ASCII string) turned up 16 `PCQ` records in each
save. **Exactly two changed value; the other 14 were byte-identical.** The
two that changed were both found sitting inside the same structure,
immediately preceded (within ~130-400 bytes) by a recognizable entity name:

```
[entity ID/hash header, ~16 bytes]
[len][entity_name]                  e.g. "DLC3_CHANCELLOR_CASBRIM"
[transform data: position/rotation/scale floats, ~150 bytes]
[sentinel fields: runs of 0xFFFFFFFF]
[count: uint32]                     e.g. 5
[count x ([len][key][len][value])]  e.g. PCQ=3483, PSDN=0, PQUS=2, Lector=3231, PUMN=23
```

- The `PCQ` record next to `DLC3_CHANCELLOR_CASBRIM` changed `3484` (save
  `000281`, before accepting) → `3483` (save `000282`, after accepting).
- The *other* changed `PCQ` record sits next to `DLC3_QUEEN_ARBELLEN` —
  confirming this is exactly the "unavoidable second questline" the user
  described — and changed `878` → `2694` (a much bigger jump, consistent
  with that questline having advanced by more than one atomic step, unlike
  the clean single-decrement for Casbrim).
- All other 14 `PCQ` records (for 14 other NPCs) are identical in both
  saves — strong evidence `PCQ` really is a per-NPC quest/dialogue-state
  value, not incidental noise.

Added `tw2tools.wd_format.parse_property_bags(data, min_props=1,
max_props=10) -> list[PropertyBag]` (the generic `[count][key][value]...`
scanner) and `tw2tools.entity_property` CLI (`python -m
tw2tools.entity_property <saves_dir> --entity NAME --prop KEY [--json
OUT]`) — tries every occurrence of the entity name in turn (an entity's
name can appear multiple times; not all are immediately followed by a
property bag) and reports the property value per save.

**Ran it across the full 286-save history for `DLC3_CHANCELLOR_CASBRIM`'s
`PCQ`.** Result: absent through save `000185`; then a repeating cycle each
time the player (re-)visits Casbrim: `20` → `3483` → `853`, with the value
reverting to `None` when the player leaves the zone (saves `000221`-`225`)
and the same `20`→`3483`→`853` cycle repeating on the next visit
(saves `000226`-`240`). From save `000240` onward through the end of
available data (`000280`), `PCQ` stays constant at `853` — i.e. this
playthrough accepted the quest (the `3483` step, confirmed by the user's
pair) and reached the settled post-conversation state (`853`), but does not
show any further progression (no third value appears) within the covered
saves — consistent with the "Aktywna misja" field never showing this quest
as tracked (from the earlier save-summary work): the quest was accepted but
this playthrough's available saves don't capture it being completed.

**What this means for the main goal:** we now have a concrete, validated,
reusable way to read *quest-relevant NPC state* per save — not a guess, but
directly confirmed against a real known "before/after accepting a specific
quest" pair. `PCQ` most likely encodes a dialogue/conversation-node index
rather than a strict boolean, so distinguishing "accepted" from "completed"
for a given quest would mean identifying what value corresponds to
completion (not yet known for this quest, since it isn't reached in the
available saves) — but the technique (property-bag diff between a tightly
bracketed save pair, then read the specific property across a full
history) is now proven and reusable for any NPC/quest, given a similar
purpose-made save pair.

## Save-editing experiment: patched Casbrim's position (2026-07-11)

Added `tw2tools.wd_format.patch_zlib_block(data, offset, new_decompressed)`
(decompresses at `offset`, tracks exactly how many original compressed
bytes to replace via a new `_decompress_at_ex` helper, recompresses caller-
supplied replacement bytes, and splices them back in) to test a real
hypothesis on the user's actual save `saves/remote/000280.TwoWorldsIISave`
(Casbrim's NPC model doesn't render in-game for this save, despite all
quest/zone-load flags looking "correct").

Comparing Casbrim's full transform (rotation + position, 20 floats read
right after his name) between save `000280` and the confirmed-visually-
working `quest_saves/000282` found a real difference: identity rotation
and position `(3326, 3313, 401)` in `000280` vs. a real rotation and
position `(2202, 1356, 308)` in `000282`. Patched `000280`'s copy of those
7 float values (2x2 rotation submatrix + XYZ) to the `000282` values,
recompressed via `patch_zlib_block`, and wrote the result to a **new** file
(`files/quest_saves/000280_casbrim_repositioned.TwoWorldsIISave`; the
user's original save was never modified). **Result: the user loaded the
patched file and Casbrim's NPC model did appear at the new position** —
confirming position/rotation is a real, editable lever, and that our
transform-field identification was correct. **However, the quest itself did
not progress** — his presence alone doesn't drive quest/dialogue logic
(unsurprising in hindsight: that's presumably handled by the `.eco` script
layer, which is still unparsed).

## Multiple named Casbrim positions found in `DLC3_PC.wd` level data (2026-07-11)

Checked whether `DLC3_PC.wd` (not just `DLC3_PC_POL.wd`) contains
Casbrim/quest-related content — it does, far more extensively: searching
the fully-decompressed archive (~22,318 blocks) for `Casbrim` found **257
hits across 65 different chunks** (vs. 72 hits in one chunk for
`DLC3_PC_POL.wd`). Two chunks (`1039431680`, `1041543168`) hold ~67 hits
each and appear to be full localization-text dumps (including the same
`GROUP_66/86/106/2` + "Ekspercka przygoda poboczna" text found earlier in
the POL archive) — likely a multi-language bundle. The other ~63 chunks
have small, consistent hit counts (mostly 3) and turned out to be **level
design / scene data**, not text: named object markers like `MARKER`,
`MARKER_CHEST` (e.g. "chest for books 1"), and — critically — multiple
**distinct named Casbrim position markers**, each preceded by its own XYZ
float triplet:

| Marker | Position (X, Y, Z) | Matches |
|---|---|---|
| `casbrim mid-game` | (2202.7, 1355.3, 308.2) | the confirmed-working `quest_saves/282` position used for the patch above |
| `casbrim here` | (3324.3, 3298.1, 401.6) | save `000280`'s *original* (pre-patch) position |
| `Casbrim's Spot` | (554.0, 1349.2, 308.5) | a third distinct position |
| `Casbrim CQ` | (3217.3, 2280.7, 305.6) | a fourth distinct position |
| `tele Casbrim BeforeAD` | (2841.5, 2724.0, 310.9) | a teleport point |

**This changes the interpretation of the earlier patch.** Save `000280`'s
"broken" position isn't corrupted/garbage data — it's the real, named
`casbrim here` marker, a legitimate level-design position. So the actual
mechanism controlling which of these named spots gets written into a given
save must live in level/quest script logic (which marker to teleport him to
for which story stage), not in the save's position field being simply
right-or-wrong. The save file just records whichever position the (still
unparsed) script logic last set — explaining why the patch worked
mechanically (any valid named position renders him) without progressing
the quest (rendering ≠ triggering script-side quest state).

## Cross-checked the technique on a second NPC (Queen Arbellen) (2026-07-11)

To test generality rather than relying on Casbrim alone:

- **`Lector` self-reference confirmed again:** Arbellen's property bag is
  `PCQ=2694, PSDN=0, PQUS=2, Lector=3247, PUMN=22`; `Name_3247` in the POL
  localization archive decodes to `"Królowa Arbellen"` (Queen Arbellen) —
  an exact match, same pattern as Casbrim's `Lector=3231` → `Name_3231` →
  `"Kanclerz Casbrim"`. `Lector` reliably self-identifies any NPC.
- **Also has multiple named identity variants** in `DLC3_PC.wd`:
  `DLC3_QUEEN_ARBELLEN`, `DLC3_QUEEN_ARBELLEN_YOUNG` (plus `#`-wrapped
  template-looking versions of each) — a young/present duality, presumably
  for a flashback or time-skip story beat. Didn't find the same
  multi-named-position pattern as Casbrim in the quick pass done, but this
  wasn't exhaustively searched.
- Confirms the `Lector`/property-bag structure is a general per-NPC
  convention, not something specific to Casbrim.

## Quest-ID matching approach: confirmed dead end (2026-07-11)

Directly tested whether `PCQ`'s observed numeric values (`20`, `3483`,
`3484`, `853`, `149`, `878`, `2694`) correspond to real dialogue-content IDs
in the POL localization archive:

- Found a real `Q_<id>`/`DQ_<id>_<n>.FT_<n>` dialogue-line ID system (449
  `Q_` entries in one chunk alone) and confirmed several `PCQ` values DO
  exist as `Q_`/`DQ_` IDs somewhere in the file (e.g. `Q_853`, `Q_3483`) —
  but reading the actual dialogue text at those IDs revealed they belong to
  **entirely unrelated storylines** (`DQ_3483` is about recovering a "Kula"
  orb; `DQ_853` is about the "Dar Pha" princess questline, a different
  DLC). This is because character names, dialogue lines, and quest IDs all
  appear to share **one global auto-incrementing ID pool** across the
  entire game — any specific number will coincidentally match *something*
  unrelated.
- To get *real* signal instead of coincidence, located the genuinely
  Casbrim/Ekspercka-linked dialogue IDs by anchoring on the actual quest
  title text's `GROUP_66/86/106/2` locations: `DQ_434`, `Q_855`, `DQ_755`,
  `Q_1291`, `Q_244`, `Q_1292`, `Q_45`.
  **Checked exhaustively whether any of these ever appear as a `PCQ` (or
  any other) property value for Casbrim or the Elven Gardener, across all
  286 saves in `saves/remote/` — zero matches, anywhere.**

**Conclusion:** `PCQ`'s value does not reference this quest's own
dialogue-ID namespace. It's likely a generic per-NPC conversation-state
counter whose *change* correlates with an interaction happening (which is
why the before/after pair worked as a detection signal), not a value that
itself encodes which quest or dialogue line was involved. The ID-matching
approach, applied to `PCQ` specifically, is exhausted — further progress
here would need actual `.eco` script decoding (still unresolved) rather
than more numeric guessing.

## Correction + stronger confirmation: cross-language ID validation (2026-07-11)

Follow-up per user request: checked `DLC3_PC.wd` (not just the POL archive)
for the English/German terms "Expert"/"Adventure"/"Gods"/"demons", since the
game bundles multiple languages together (confirmed: chunk `1039431680`
holds a full **German** localization dump, alongside the Polish one at
`1041543168`).

**Important correction to the previous section's methodology:** assumed
`GROUP_<n>` numbers might correspond 1:1 across language files (e.g. POL's
`GROUP_66` ≈ German's `GROUP_6`) — checked this directly and it's **false**.
German's `GROUP_6`/`GROUP_8`/`GROUP_10` are a completely different quest
("Experten Side Quest: Sehende Steine" / "Expert Side Quest: Seeing
Stones", parts 1-3) — an unrelated quest that happens to share the generic
English-loanword phrasing "Expert Side Quest" (apparently used as a title
template across *many* different quests, not just Casbrim's). This means
the earlier list of "genuinely linked" IDs (`DQ_434`, `Q_855`, `DQ_755`,
`Q_1291`, `Q_244`, `Q_1292`) was derived from a flawed cross-language
assumption for everything except `GROUP_2`/`Q_45`.

**`GROUP_2`/`Q_45` specifically is now independently double-confirmed**,
not assumed: German's `GROUP_2` is directly followed by the title
`"Expert Side Quest: Götter und Dämonen"` (German for "Gods and Demons") —
an exact semantic match to the Polish quest, at the same `GROUP_2` number,
in a completely different language file. This makes `Q_45` the single most
reliably-confirmed real quest ID found so far (cross-validated in Polish
*and* German, not just proximity in one file).

**Re-ran the property-value check with this stronger confirmation, and
fixed a gap in the earlier check** (`45` had been excluded from the
original exhaustive scan for being too common as a raw substring — but an
*exact property value* match is precise regardless of how common the raw
digits are elsewhere). Checked:
- `45` as an exact property value for Casbrim/Elven Gardener across all
  286 `saves/remote/` saves plus both `quest_saves` saves: **zero
  matches**.
- `45` as a value in *any* property bag at all (not entity-scoped) across
  all 969 property bags found in `quest_saves/000282.TwoWorldsIISave`:
  **zero matches**.

**Strengthened conclusion:** even the single most rigorously
cross-language-confirmed quest ID for "Gods and Demons" does not appear
anywhere in the save's property-bag system — not attached to Casbrim, not
attached to any other entity, not anywhere in a full save's ~969 bags. This
rules out (with much higher confidence than before) the idea that quest
acceptance/completion is tracked via a `Q_<id>`-referencing property
bag anywhere in this system. The actual quest-journal/completion state, if
it exists as an explicit save-file structure at all, must use a completely
different mechanism than named property bags — most likely a raw
numeric-ID table this investigation hasn't located, or logic embedded in
the (still unparsed) `.eco` scripts that isn't persisted as an explicit
"quest state" record the way one might expect.

## Major breakthrough: `.eco` payload location solved (2026-07-11)

Pursued `.eco` decoding directly, per user request. **Solved the
long-standing payload-location problem** — not via the entry-footer
`word1..word4` fields (still unresolved), but by finding that `.eco` files
are stored completely independently of the metadata/entry-list system:
each compiled `.eco` file is its own separate zlib block, and its
decompressed content starts with a literal magic header:

```
"ECO" + 0x00 + uint16(0) + uint16(6)    (8 bytes: 45 43 4f 00 00 00 06 00)
+ uint32(3)                              (purpose unknown, constant so far)
+ uint32(name_length) + name              (self-identifying filename, no extension)
+ ...compiled bytecode...
```

Added `tw2tools.wd_format.find_eco_files(data) -> list[EcoFile]` (tested)
to detect this magic and extract the embedded name. Scanning the full
`DLC3_PC.wd` archive (~22,318 blocks) for chunks starting with this magic
found **exactly 21 real `.eco` files** (far fewer than the ~1203 `.eco`
path references in the entry-list metadata, confirming most of those were
just path-string noise from the metadata scanner, not real distinct
payloads). Identified by name: `DLC_2`, `DLC_3`, `DLC_PIRATES`,
`TwoWorlds2Containers`, `Default Events Script`, `TwoWorlds2Music`,
`TwoWorlds2Shops`, `TwoWorlds2Trainers`, `Achievements Script`,
`heroControl`, **`TwoWorlds2Quests`** (179,340 bytes — the main quest
script), `Sounds Script`, `Weather Script`, `ConfigCampaign`,
`JSTestCampaign` (×2), `Generic Adventure Script`, `MagicControl`,
`RPGCompute` (293,725 bytes, the largest), `Test maps`.

**The bytecode itself is opaque** — searching `TwoWorlds2Quests` and
`DLC_3` for `Casbrim`/`SP3`/`Q_45`/`Ekspercka` found nothing. This confirms
(rather than contradicts) everything learned so far: compiled scripts
reference entities/dialogue purely by numeric ID, with display names/text
living only in the separate localization tables already decoded.

**But extracting the scripts' embedded string tables was very
informative.** These use a *different* encoding than the length-prefixed
format used elsewhere — plain null-terminated C-strings. Extracting all
such strings (`[ -~]{4,}\x00` pattern) from all 21 files (`DLC_2`/`DLC_3`
have only 2 each; `TwoWorlds2Quests` has 352; `RPGCompute` has 1045) reveals
the **generic quest-engine's own vocabulary** — not Casbrim-specific, but
the shared templating system used for *every* quest:
- `translateQ_%d_QTD` / `_QSD` / `_QFD` / `_QCD` (each with `_C1`/`_C2`
  variants) — almost certainly Quest Title/Start/Failed/Complete
  Description templates, confirming a real title/start/fail/complete
  lifecycle exists generically for all quests.
- Literal state constants `QUEST_GIVEN` and `QUEST_SOLVED` sitting right
  alongside those templates — real enum-like state names.
- `translateDQ_%d` and `translateGROUP_%d` — confirms the `DQ_`/`GROUP_`
  localization key conventions found earlier are exactly this generic
  templating system, not something hand-authored per quest.
- `translateName_%d` — confirms the `Name_<ID>` self-reference convention.
- Property-bag keys **`PSDN`, `PQUS`, `Lector`, `PUMN`** appear as literal
  engine strings here too, cross-validating the property-bag decoding from
  earlier sessions (these are genuine, engine-recognized keys, not
  something invented by the byte-scanning approach). Two more previously
  unseen keys appear alongside them: `PQTIMED`, `PQBS`.
- Level-marker vocabulary also appears here: `MARKER_CHEST`, `MARKER_GATE`,
  `MARKER_TELEPORT_LOCKED_DOOR_START`, `TELE_OUT_EFFECT`, `QLINV`, `LLvl` —
  consistent with the level-marker data found in the earlier `.wd`
  investigation.

**Correction — `PCQ` gap resolved, it was a tooling bug, not a real
mystery.** The "notable gap" above was wrong: `PCQ` *is* a literal string
in `TwoWorlds2Quests` — the ad-hoc string-extraction script used to survey
all 21 files required a minimum length of 4 characters, silently filtering
out the exact 3-character string `"PCQ"`. Re-searching with
`search_text_multi` (no length minimum) found it immediately, twice, right
in the middle of the same property-key cluster:
`PSDN\0 PQUS\0 PQUS\0 PCQ\0 Lector\0 PCQ\0 PQTIMED\0 PQBS\0 PQBS\0` — i.e.
`PCQ` is defined in the exact same place as its siblings, appearing twice
(once each for what are very likely a getter and a setter reference in the
compiled code, matching the doubled `PQUS`/`PQBS` too). This gives the
**complete, confirmed property-bag key vocabulary**: `PCQ`, `PSDN`,
`PQUS`, `Lector`, `PUMN`, `PQTIMED`, `PQBS` — all genuine engine constants,
none invented by the byte-scanning approach.

**Further structural insight: the string table isn't deduplicated, so its
order reflects real execution sequence.** The same template strings
(`translateQ_%d_QTD`, `_QSD_C1/C2`, `_QFD_C1/C2`, `_QCD_C1/C2`) appear
multiple times in a row rather than being interned once — meaning each
occurrence in this list corresponds to one place in the *source* code that
referenced that string, in original order. Reading through the sequence
around `PCQ`/`Lector` reveals a readable lifecycle without needing any
opcode decoding: `...QTD (title) → QSD_C1/C2 (start description
variants) → QUEST_GIVEN → QSD_C1/C2 (repeated) → QUEST_SOLVED →
QSD → QFD_C1/C2 (failed variants) → QFD → QCD_C1/C2 (complete variants)
→ QCD → (the QSD/QUEST_SOLVED block repeats) → ...`. This confirms a real,
generic `QUEST_GIVEN`/`QUEST_SOLVED` state pair exists in the engine's
quest-handling logic, consistent with (though not yet directly wired to)
the property-bag state we've been tracking via `PCQ`.

## Stopping point (2026-07-11)

Decoding further (mapping specific opcodes to specific behavior, e.g.
finding exactly what numeric comparison against `PCQ` triggers
`QUEST_SOLVED`) would require decoding the actual bytecode instruction
format — a fundamentally larger undertaking than everything done so far
(closer to writing a disassembler for an unknown VM than to the
find-and-correlate work in this document). Deliberately stopping here by
user decision rather than continuing into that scope. The toolkit
(`tw2tools`) and all findings in this document are the durable output of
this investigation; resuming bytecode decoding later is a legitimate,
separately-scoped future project, not a dead end — `find_eco_files` and
the confirmed property-key vocabulary would be the starting point.

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
- Task 4 (`task4_strings.json`) found 3,122 null-terminated strings in
  `TwoWorlds2Quests.eco`, with offsets spanning bytes 0..176,043 — 98.2%
  of the 179,340-byte file — determined to be INTERLEAVED with bytecode
  throughout the file, not clustered in a separate contiguous string
  pool. Task 5 (`task5_anchors.json`) found only 1 `QUEST_GIVEN`
  occurrence (offset 395) and 2 `QUEST_SOLVED` occurrences (offsets 491
  and 810) in the entire file. All three anchors' `candidate_quest_id_hits`
  are empty — none of the three 32-byte windows around these offsets
  contained the confirmed quest IDs `45` (`Q_45`) or `2` (`GROUP_2`) in
  any encoding (u8/u16-LE/u32-LE).
- Task 6 (`task6_cross_validation.json`) cross-validated all 21 extracted
  `.eco` scripts for the same keywords: `QUEST_GIVEN`/`QUEST_SOLVED`
  appear in only `TwoWorlds2Quests.eco`, at the identical 3 offsets found
  in Task 5. None of the other 20 scripts contain either keyword at all,
  so no cross-script confirmation of any byte-window pattern was
  possible — there was nothing to cross-validate against.
- Task 7 (`task7_pcq_correlation.json`) searched the confirmed `PCQ`
  transition values (`20`, `3483`, `853`) as u8/u16-LE/u32-LE across the
  whole 179,340-byte file, finding 483 total hits. The closest hits to
  any anchor are a tie between `value=20`, `encoding=u16_le`, `offset=41`
  and `value=20`, `encoding=u8`, `offset=41` (both encodings start at the
  same byte), nearest anchor at `offset=395` (the `QUEST_GIVEN`
  occurrence) — `distance_to_nearest_anchor=354` bytes, far outside the
  32-byte window used in Tasks 5/6. This does not constitute a confident
  match: 354 bytes is roughly 11x the window size used elsewhere in this
  investigation, and no other hit came closer.

**Why this didn't resolve the question:** string constants and any
integer references to them could not be distinguished from other
incidental integers in the file without decoding actual instruction
opcodes, which this pass deliberately did not attempt.

**Stopping point (2026-07-13).** Consistent with the original stopping
point, decoding further would require building an actual opcode
interpreter rather than anchor-based correlation. Not pursued further in
this pass by design (see the exploration spec). Future starting point:
the `value=20`/`offset=41` hits (tied between the `u16_le` and `u8`
encodings) near the `QUEST_GIVEN` anchor at offset 395 are, despite the
354-byte distance, still the closest PCQ-value occurrences to any
lifecycle anchor found across the whole file — worth revisiting first
if resuming, though confirming any link
would require actual opcode decoding rather than further anchor-distance
triangulation.

## Bytecode decoder, Stage 1 (2026-07-13) — inconclusive, but with a real structural finding

Began the general-purpose `.eco` disassembler project (see
`docs/superpowers/specs/2026-07-13-eco-bytecode-decoder-design.md`),
staged with checkpoints. Stage 1 (format discovery) originally planned
to align bytes immediately around repeated string occurrences, but
pivoted mid-stage after an unexpected finding made that approach
unsound - the pivot itself is a real, useful result even though the
follow-on search came up empty.

**Method and pivot:** ranked the most-repeated literals in
`TwoWorlds2Quests.eco` (top: `MARKER_CHEST` at `12` occurrences,
second: `MARKER_GATE` at `10` occurrences, out of 352 total strings
found with `min_length=4`). Aligning bytes around every occurrence of
the top literal found one invariant byte (`0x00` immediately before
the string, all 12/12 occurrences) - but inspecting the byte *before
that* showed a printable ASCII character in all 12 cases, the tail of
a different, unrelated preceding string each time (examples:
`translateGROUP_%d`, `translateQ_%d`, `translateName_%d`, `LLvl`,
`QLINV`, `PrintContainers`). **This means the strings are packed
back-to-back with zero gap and no adjacent opcode/framing byte at
all** - the "invariant byte" was just the preceding string's own NUL
terminator, not an instruction. The length-byte hypothesis (byte
before = string length) was also rejected: 0/12 occurrences matched
(the actual byte is always `0x00`, not `12`/`0x0C`).

Pivoted to mapping the file's actual string-vs-bytecode structure
instead: of `351` consecutive string pairs across the whole file,
`323` (`92.0%`) are back-to-back with no gap, confirming the
tight-packing finding holds file-wide, not just for one literal. The
`28` gaps with actual content between strings are the candidate
bytecode regions; the largest 10 ranged from `4` bytes up to a
standout `172` bytes.

**What was tried:** searched the 5 largest gaps (sizes `172`, `35`,
`34`, `24`, `8` bytes) for u32-LE integers matching `MARKER_CHEST`'s
or `MARKER_GATE`'s exact file offsets (22 known offsets total: 12 for
`MARKER_CHEST`, 10 for `MARKER_GATE`) - `0` hits found across all 5
gaps.

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
continuation. Future starting point: the `172`-byte gap between
`RESURRECT_EFFECT` (ending at file offset 4121) and `QuestsOn`
(starting at file offset 4293) is by far the largest and most distinct
candidate bytecode region found (the next-largest gap drops to 35
bytes) - worth a direct content inspection (rather than another
offset-value search) in any future pass, since Task 5's offset-reference
search there came up empty but didn't examine what the 172 bytes
actually contain.

## Gap-content inspection (2026-07-15) — a real record shape found, semantics unresolved

Followed up on Stage 1's "future starting point": directly inspected the
byte content of the largest gaps instead of searching them for offset
values. Re-extracted `TwoWorlds2Quests.eco` fresh (same
`extract_eco_files_from_wd_archive`, 179,340 bytes, unchanged) and hex-
dumped the top 5 non-zero string-gaps.

**Two of the five "gaps" turned out to be an artifact of the Stage 1
`min_length=4` filter, not bytecode.** The 24-byte gap (between
`AGGRESSIVE` and `SMALL`) is six 3-character strings
(`GLD`/`REP`/`EXP`/`SKL`/`ITM`/`RND`) excluded by the length-4 cutoff; the
8-byte gap (between `RUN_VERY_FAST` and `BACK_TO_GIVER`) is three
short template strings (`%d`, `0`, `%d`). Both are ordinary string data,
not a bytecode region - worth remembering if this line of investigation
resumes, since any future gap analysis should first rule out
short-string exclusion before treating a gap as "real" bytecode.

**The other three gaps contain a genuine, repeated, fixed-shape
record - found in three independent file locations.** The 172-byte gap
(between `RESURRECT_EFFECT` and `QuestsOn`) is five consecutive
repeats of the same 34-byte structure (plus a little stray padding
between some repeats, which is why the gap totals 172 rather than an
exact multiple of 34); the 35-byte gap (between
`translateAddedSkillPoints` and `DQ_%d`, near the start of the file at
offset 182) and the 34-byte gap (between `Summons` and `test1`, offset
5135) are one repeat each - 7 occurrences total, confirmed by an
exhaustive whole-file search (100 raw `0xFFFFFFFF` 4-byte sequences
exist in the file; exactly 7 of them are followed by this full record
shape, and all 7 are these three locations - no occurrences anywhere
else in the file's 179,340 bytes).

**The record shape is a constant 34 bytes, not a range** (corrected
after independent verification measured the exact zero-run lengths per
occurrence rather than eyeballing them - the earlier draft of this note
said "10-11" / "6-7" / "34-35 bytes", which was wrong: all 7 occurrences
have identically-sized fields, with zero variation):
- 4 bytes: `0xFFFFFFFF` sentinel
- 10 zero bytes (exactly, all 7 occurrences)
- 1 byte: `0x80` flag (always exactly this value, all 7 occurrences)
- 7 zero bytes (exactly, all 7 occurrences)
- 3 consecutive u32-LE integers `V`, `V+4`, `V+5` (the "+4, then +1"
  step is identical in all 7 occurrences)

Total: 4+10+1+7+12 = 34 bytes, every time. The apparent "34 or 35 byte"
gap sizes reported earlier come from a stray extra `0x00` padding byte
sitting *between* some records (inter-record padding), not from any
variation in the record's own internal layout.

**The mechanically verified relationship:** in every one of the 7
occurrences, `V` exactly equals *this record's own sentinel's absolute
file offset, minus 44* - zero exceptions (sentinel/value pairs:
183/139, 4121/4077, 4155/4111, 4190/4146, 4225/4181, 4259/4215,
5135/5091 - each pair's difference is exactly 44). This was checked
computationally, not eyeballed.

**What `V` does NOT mean:** checked and ruled out - `V` does not match
any of the file's 352 known string offsets (exhaustive byte-by-byte
u16-LE/u32-LE scan, zero matches, broader than Task 5's original
22-offset check). Inspecting the actual file content sitting at each
`V` position shows no consistent target: one lands on a string's last
character before its own null terminator, one lands mid-word inside an
unrelated string, and three land inside a *preceding occurrence's own
triplet field* (an artifact of records sitting close together in the
172-byte gap, not evidence of an intentional cross-reference). This
inconsistency, combined with the perfectly constant "-44" arithmetic
holding regardless of what's actually at the target location, is why
`V` reads as a **position-derived value computed from the record's own
file offset** (most likely a fixed-size back-pointer/header-relative
field emitted mechanically by the compiler) rather than an
author-chosen reference to specific string or quest data.

**Interpretation:** this is a confident, cross-validated instruction/
record *shape* - the first one found in this entire investigation with
byte-exact, repeatable framing (sentinel + fixed-position flag +
arithmetic-consistent integer triplet) - but it does not, by itself,
explain how bytecode references a string constant, since `V` is
demonstrably self-referential rather than content-referential. It is
also rare: only 7 instances in the whole file, all clustered in 3
places, so it may be a narrow special-case structure (e.g. tied
specifically to whatever `RESURRECT_EFFECT`, `translateAddedSkillPoints`,
and `Summons` have in common) rather than the general "reference a
string" instruction Stage 1 originally went looking for.

**Stopping point (2026-07-15).** This is a positive structural finding
(a real, mechanically-verified byte-level shape, unlike Stage 1's
inconclusive result) but an open semantic question (why `-44`, and why
only these 3 locations). Continuing would mean: checking whether this
exact shape (sentinel + `0x80` + arithmetic triplet) appears in any of
the other 20 real `.eco` scripts (not just `TwoWorlds2Quests`), and
examining what precedes/follows each of the 3 occurrence sites
semantically (are `RESURRECT_EFFECT`, `translateAddedSkillPoints`, and
`Summons` related in the game's logic?) - both are new, unstarted
threads, not a continuation of this pass.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/extract_quests_eco.py`,
`script/wd_extract/inspect_gap_content.py`,
`script/wd_extract/decode_gap1_structure.py`,
`script/wd_extract/scan_gap1_all_offsets.py`,
`script/wd_extract/decode_gap1_all_alignments.py`,
`script/wd_extract/search_whole_file_for_record.py`.

## Cross-script record search — the full .eco file header format decoded (2026-07-16)

Followed up on this investigation's own "unstarted future thread": checked
whether the 34-byte record shape found in `TwoWorlds2Quests.eco` (sentinel +
`0x80` flag + arithmetic triplet) appears in the other 20 real `.eco`
scripts. It does - **in all 21**, 196 occurrences total (re-extracted fresh
via `extract_eco_files_from_wd_archive`, all sizes match prior findings,
e.g. `TwoWorlds2Quests.eco` still 179,340 bytes). This is far more general
than the "rare, 3-location" framing of the prior section - it's a
genuine, universal element of the `.eco` bytecode format.

**The "V = self-offset - 44" arithmetic from the prior section is not a
fixed constant - it's `V = sentinel_offset - header_length`, and
`header_length` varies per script.** Checked the per-file constant
against every script's own real embedded name and found an exact
formula, holding for all 21 files with zero exceptions:
`header_length = len(script_name) + 28`. (`TwoWorlds2Quests`'s constant
of 44 was really `16 + 28`, not a special-cased 44 - the prior section's
finding was correct arithmetic, just an incomplete generalization since
only one file had been examined.)

**This exposed the actual `.eco` file header layout**, previously known
only as "`ECO\0` magic + an embedded name." Decoded and verified against
all 21 files (byte-for-byte, via `struct.unpack`, not eyeballing):

```
offset  size  field                    notes
0       4     magic "ECO\0"
4       4     u32-LE constant          0x00060000 (393216) - identical in all 21 files
8       4     u32-LE field B           varies: 2/3/4/30 - small integer, meaning unconfirmed
12      4     u32-LE name_length       always == len(the script's own real name)
16      N     name bytes               N = name_length, no null terminator (length-prefixed)
16+N    4     u32-LE constant          0x33662909 (862333193) - identical in all 21 files
20+N    4     u32-LE field C           varies per file (8 to 644), meaning unconfirmed
24+N    4     u32-LE field D           varies per file (53 to 30453), meaning unconfirmed
28+N    -     real bytecode/string-table content begins here
```

Total header length = `28 + len(name)`, confirmed exactly against all 21
files with no exceptions (cross-checked two independent ways: computed
directly from the header bytes, and confirmed it equals `sentinel_offset
- V` for every one of the 196 record-shape matches - both methods agree
on the same number for every file). For the two shortest scripts
(`DLC_2.eco`, `DLC_3.eco`, header length 33), the very first byte after
the header *is* this record's sentinel - the record sits immediately at
the start of the bytecode section, not buried in it.

**This resolves the open question from the prior section: `V` is not a
mysterious cross-reference.** `V = sentinel_offset - header_length` is
simply this record's own file position, re-expressed relative to the
start of the bytecode section instead of relative to the start of the
whole file - i.e. a **bytecode-section-relative self-offset**, not a
pointer to some other piece of data. That is why it never matched a
string offset and why the byte content "at" `V` (measured as an
absolute file position) was inconsistent - `V` was never meant to be
read as an absolute file offset in the first place.

**Still open / not claimed:** the meaning of field B, field C, and
field D (three per-file integers whose values don't obviously correlate
with file size alone - e.g. `RPGCompute.eco` has the largest field D,
30453, but is not the largest file; `TwoWorlds2Quests.eco`'s field C,
644, doesn't match any quantity already confirmed in this investigation).
Also open: what the record shape itself (sentinel + flag + self-offset
triplet) actually *does* at the VM level - a self-referential offset is
consistent with a jump target, an exception/handler table entry, or
self-describing metadata, but none of those has been confirmed.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/extract_all_eco.py`,
`script/wd_extract/search_all_scripts_for_record.py`,
`script/wd_extract/inspect_eco_header.py`,
`script/wd_extract/decode_all_headers.py`.

## Header fields B, C, D — inconclusive (2026-07-16)

Followed up on the "still open" question from the header-decode section:
what do the three per-file variable header integers (field B at offset 8,
field C and field D at offset 16+name_length+4 and +8) actually mean?
Gathered, per file, several independently-computable candidate
quantities - `file_size`, `body_len` (file size minus header length),
total raw `0xFFFFFFFF` sentinel count, 34-byte record-shape match count,
null-terminated string count at both `min_length=1` and `min_length=4`,
and unique string count at `min_length=4` - and tested whether field B,
C, or D exactly equals any candidate (or that candidate ±1) across all
21 files simultaneously (the same method that found `header_length =
len(name)+28`).

**Result: no exact match found for any of the three fields against any
of the 7 tested candidates, with or without a ±1 offset.** This is a
real negative result, not a gap in effort - the same systematic
equality-testing approach that successfully cracked the header length
formula came up empty here. None of field B/C/D is simply "a count of
X" for any of the quantities that were readily computable from what
this investigation already knows how to measure.

**One observation worth recording despite the negative correlation
test:** field B's value distribution across the 21 files is `{3: 15
files, 2: 4 files, 4: 1 file, 30: 1 file}` - i.e. it looks categorical
(a small, mostly-repeated set of values) rather than a raw count, for
20 of the 21 files. The 4 files with field B = 2 are `ConfigCampaign`,
`JSTestCampaign` (both copies), and `Test maps` - all test/tooling
scripts by name, not player-facing content, which is suggestive but
unconfirmed (not verified against any independent classification of
these scripts). `RPGCompute` is the one outlier at 30, standing apart
from the mostly-2/3/4 pattern the other 20 files share - consistent
with `RPGCompute` also being an outlier on nearly every other measured
quantity in this investigation (most strings, most sentinels, most
record matches, by a wide margin), suggesting it may be a fundamentally
different kind of file (a shared utility/library script) rather than a
per-quest content script like most of the other 20.

**Stopping point (2026-07-16).** Continuing would need either testing
against candidates this investigation doesn't yet have tooling to
compute (e.g. counts of specific bytecode patterns not yet identified,
or a count of *type-3* files vs *type-2* files if field B really is
categorical), or accepting that these fields may not be resolvable from
static analysis of the `.eco` files alone - a new planning decision, not
a continuation of this pass. The other pre-existing open thread (whether
`RESURRECT_EFFECT`, `translateAddedSkillPoints`, and `Summons` - the
34-byte record's three occurrence sites in `TwoWorlds2Quests.eco` - are
related in the game's own logic) remains entirely unstarted and would
likely need a different kind of research (game content/wiki lookup)
rather than more binary analysis.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/correlate_header_fields.py`.

## Record-neighbor alignment — no framing instruction found (2026-07-16)

Re-pointed the "gaps between the two remaining threads" decision toward
the more promising one: since the 34-byte record is now known to be
universal (196 occurrences, not special to 3 sites), the "are
`RESURRECT_EFFECT`/`translateAddedSkillPoints`/`Summons` related
in-game" thread lost its premise - the record isn't tied to those 3
strings specifically, it's everywhere. Redirected effort into what the
design doc originally called Stage 2: use the confirmed record as an
anchor and check what surrounds it, the same byte-position-invariance
technique Stage 1 used on string literals, now anchored on a much
stronger, universal anchor across all 196 occurrences in all 21 files
instead of one string's dozen repeats.

**Result: no consistent calling/framing instruction found.** Aligned a
16-byte-before/16-byte-after window around every one of the 196
confirmed record occurrences. Exactly one position came back invariant
- the single byte immediately before the sentinel, always `0x00` - and
every other position (15 more before, all 16 after) varied freely.

**That one invariant byte is a coincidental artifact, not a real
framing byte - checked directly, not assumed.** Inspected the actual 4
bytes preceding several individual occurrences across different files:
at `DLC_2.eco`'s only occurrence, those 4 bytes decode to the small
integer 53 (the file header's own `field D`, LE-encoded, top byte
naturally zero); at two different occurrences inside `RPGCompute.eco`
and `MagicControl.eco`, those same 4 bytes instead spell out `"ing\0"`
and `"ion\0"` respectively - the tail and null terminator of a
completely unrelated preceding string. Same underlying cause Stage 1
already diagnosed for `MARKER_CHEST`'s invariant byte: **both small
little-endian integers (top byte usually zero) and string null
terminators (always zero) coincidentally produce a zero byte at this
position**, regardless of what kind of data actually precedes the
record. It is not a marker, delimiter, or opcode belonging to the
record's own encoding.

**Stopping point (2026-07-16).** Direct byte-alignment around this
record - even with 196 occurrences across every real script, a far
stronger anchor than Stage 1 had - does not surface a framing
instruction the same way it didn't for string literals. This is
consistent with the file format's general character observed
throughout this investigation: everything (strings, this record type,
header fields) is packed tightly with small little-endian integers and
no reliable padding/alignment convention, which defeats simple
position-invariance search regardless of how good the anchor is.
Continuing would need a fundamentally different technique - e.g.
tracing what specific opcode/byte pattern immediately *calls into* one
of these records at the VM level (would require understanding at least
one real opcode first, which this investigation has not yet identified)
rather than more alignment around this or any other anchor. Both
previously-identified open threads (header fields B/C/D's meaning, and
the record type's actual VM-level purpose) remain open; no fully new
lead was found this pass.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/align_record_neighbors.py`.

## Jump/branch-target detection — a real record-index table found in `RPGCompute.eco` (2026-07-16)

Tried a genuinely different technique from the alignment approach used
three times already: instead of looking for fixed framing around an
anchor, searched every byte position in each `.eco` file for u16/u32
integers (both endiannesses) that exactly match the absolute file offset
of a confirmed 34-byte record's own start or end position - the
"branch/jump instruction" idea from the original design doc, using the
196 confirmed records as landing sites instead of raw string offsets
(which Stage 1 Task 5 already ruled out).

**First pass produced a lot of hits, almost all noise.** A naive
assumption that "a u32 exact match is inherently much less likely to be
coincidental than u16" turned out **wrong for this dataset**: record
offsets are small numbers (well under 65536 for most files), so as
u32-LE they have zero high bytes - and this file format is full of
null-byte padding, so small-value matches (especially against a target
set that includes the tiny `body_start`/header-length values) occur
constantly by chance. Dropped `body_start` from the target set (pure
noise, confirmed on the first pass) and built a **randomized control
test**: for each file, shifted every real target by a fixed offset
(preserving count and rough magnitude but pointing at positions that
are *not* real record boundaries), re-ran the identical search, and
compared real vs. shifted-fake hit counts - repeated with 30
independent random shifts for the two files whose initial 3-shift
comparison looked interesting, to get a reliable noise-distribution
estimate rather than trusting a small sample.

**Result: `RPGCompute.eco` shows an overwhelming, unambiguous signal;
`TwoWorlds2Quests.eco`'s initially-interesting signal turned out to be
noise on closer inspection.**

**Correction after independent re-verification (2026-07-16):** the
initial raw-hit-count statistic below ("188 vs. a 30-shift control")
turned out **not to be a robust test** - a more thorough resampling (200
trials) found roughly 1-in-18 random shifts meet or exceed the real
count of 188, because some shifted target sets happen to land on an
unrelated region of the file (~offset 292500+) containing repetitive
machine-code-like byte patterns that spuriously match small values very
often. The raw hit count conflates genuine table structure (138 of the
188 real hits sit inside the table's own byte span) with ordinary
background noise elsewhere in the file (the other 50), and the control
shifts can occasionally rack up large noise counts of their own. A far
more decisive, robust statistic replaces it: **the longest contiguous
run of ascending, exactly-34-apart `(value, value+1)` pairs is 132 for
the real data, versus a maximum run length of only 1 across 30
independent random-shift control trials.** A dense, perfectly-spaced,
132-entry ascending run never arises by chance in any control trial -
this is what actually establishes the finding, not the raw count.

- `RPGCompute.eco`: real u32 hit count 188 (138 inside the table's own
  span, 50 scattered background noise elsewhere - comparable in
  magnitude to ordinary control noise). The longest ascending
  `(value, value+1)`-run statistic is the reliable one: 132, vs. a
  control maximum of 1.
- `TwoWorlds2Quests.eco`: real count 25 sits at the 97th percentile of
  its own 30-shift control distribution, but one control shift scored
  70 - higher than the real count - making the control distribution
  itself unreliable/skewed and the "signal" not trustworthy on this
  evidence alone. Checked why: the real hits are overwhelmingly just
  two small values (`183`, `217` - one record's own start/end offset)
  recurring at scattered, non-contiguous positions, not an ordered
  table - consistent with coincidental small-value recurrence, the same
  root cause already diagnosed for this file's earlier false leads.

**Decoded the `RPGCompute.eco` signal directly - it is a literal
record-index table, not just a statistical anomaly.** At file offset
**35051-36107 (1056 bytes = 132 x 8, all standard 4-byte-aligned u32-LE
reads, no alignment trick needed** - corrected after independent
re-verification found the original end offset, 36103, was off by 4: it
marked the start of the last entry's `+1` companion field, not the
table's actual end) sits a contiguous run of 132 entries, each 8
bytes: `(record_offset, record_offset + 1)`. The 132 `record_offset`
values are **132 of RPGCompute's 133 confirmed record positions, in
exact ascending order, each exactly 34 bytes (one record length) apart**
- verified programmatically, not eyeballed. Only the file's very last
record (offset 30457) is absent from the table; every other confirmed
record from the first (25969) through the second-to-last (30423) is
present, contiguous, correctly ordered, with no gaps or out-of-order
entries.

**Checked every other file with 3+ records for the same table shape -
none has one.** `ConfigCampaign`, `heroControl`, and `JSTestCampaign`
each have exactly one isolated match (a single record referenced once,
not a run); `Default_Events_Script`, `JSTestCampaign_2`, `Sounds_Script`,
`Test_maps`, `TwoWorlds2Quests`, `TwoWorlds2Trainers`, and
`Weather_Script` have none at all. **This table mechanism, as found, is
specific to `RPGCompute.eco` among all 21 real scripts** - not (yet)
confirmed as a general `.eco` format feature.

**Interpretation:** this is the clearest evidence found in this entire
investigation of one part of an `.eco` file's bytecode referencing
another part by absolute file offset - the exact "how does bytecode
reference other structures" question this project has been chasing
since Stage 1. `RPGCompute.eco` is already an outlier on every other
measured quantity in this investigation (most records by a wide margin,
most strings, header field B = 30 instead of the near-universal 2/3/4)
- consistent with it being a fundamentally different kind of file (a
large shared function/utility library with ~133 callable routines)
that specifically needs an index/dispatch table, unlike the other 20
scripts which have too few records for such a structure to show up
this way (or use a different, not-yet-found mechanism).

**Still open:** the meaning of the `+1` companion value in each pair;
why exactly 132 entries rather than 133 (the missing last record);
what actually *reads* this table (no calling instruction/opcode
identified yet - this establishes the table's existence and shape, not
what consumes it); and whether the other 20 files reference their own
records by some different, not-yet-found mechanism, or don't need to at
all.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/search_jump_targets.py`,
`script/wd_extract/jump_target_control_test.py`,
`script/wd_extract/rigorous_control_test.py`,
`script/wd_extract/decode_rpg_index_table.py`,
`script/wd_extract/decode_table_full_range.py`,
`script/wd_extract/check_all_files_for_tables.py`.

## Searching for the table's consumer — inconclusive, but the table's boundaries confirmed clean (2026-07-16)

Followed up on the open question from the previous section: what
bytecode instruction actually *reads* the confirmed `RPGCompute.eco`
index table (35051-36107)? Tried the most direct approach - searching
the whole file for a u16/u32 integer (either endianness) exactly
matching the table's own start offset (35051), end offset (36107), or
entry count (132 or 133), on the theory that a "load this table" or
"loop N times" instruction would need to encode one of those numbers
somewhere.

**Result: no reference to the table's absolute position found
anywhere.** Zero hits for 35051 or 36107 - if something loads this
table by address, it isn't via a simple absolute-offset integer stored
elsewhere in the file. Hits for the entry counts 132/133 were
plentiful (131 matches) but immediately recognizable as the same class
of noise already diagnosed twice before in this investigation: both
values are under 256, and this format's constant null-byte padding
makes any specific small value recur throughout a 293KB file by pure
chance. Checked the two boundary regions directly (immediately before
byte 35051 and immediately after byte 36107) for a header/footer count
field instead of a scattered match - found none: no clean "132" or
"133" sits adjacent to either boundary.

**One useful byproduct: the table's boundaries are confirmed clean, not
an artifact of the search window.** The bytes immediately preceding
35051 (offsets ~35003-35047) follow a *different, irregular* value
progression (deltas of 20, 20, 20, 19, 1, 13, 13, 12, 13, 12, 1 -
nothing like the clean, confirmed table's 34-then-1 pattern) - i.e. the
ordered table genuinely *starts* at the first confirmed record (25969),
it doesn't extend further back with unclassified entries. The bytes
immediately following 36107 are also clearly a different structure
(values 1136, 1087, 1202, 1317, 1415, ... - much smaller, non-monotonic,
no relationship to any confirmed record offset). Both neighboring
regions remain unidentified, but are confirmed to be something other
than a continuation of this same table.

**Stopping point (2026-07-16).** Identifying what reads this table
would require either finding a *relative* (rather than absolute)
address reference - untested so far, same gap noted since Stage 1 - or
actually identifying at least one real opcode/instruction meaning by
some other route, which is a fundamentally different and larger task
than more offset-searching (this was flagged as a risk from the
project's very first design doc). The table's existence and internal
shape remain a solid, independently-verified positive finding from the
prior section; only "what consumes it" is unresolved by this pass.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/extract_rpg.py`,
`script/wd_extract/search_table_references.py`.

## Back to the main goal: a broader PCQ survey, a critical save-sequence correction, and a promising new lead (2026-07-16)

Zoomed back out from the `.eco` bytecode side-investigation to the
project's actual main goal - quest-progress encoding in the save file.
Casbrim's own `PCQ` history never showed anything past its settle value
(`853`, accepted-but-not-completed) across the whole available save
range, so tried a broader approach: instead of studying Casbrim alone,
survey *every* NPC that has a `PCQ` property bag, to see whether any
other NPC's questline shows a richer progression - possibly reaching an
observable "completed" state that could serve as a template.

**Enumerated the full roster: 40 distinct NPC entities carry a `PCQ`
property bag** (found by locating every property bag containing `PCQ`
in save `000280` and associating each with its nearest preceding named
record, per the already-documented `[name][transform][...][count][k/v
pairs]` structure) - far more than the 16 examined in the original
Casbrim-focused pass. Tracked all 40 across every sequential save
`000000`-`000280` (reusing the same property-bag-diff technique already
proven for Casbrim). Several show much richer histories than Casbrim's
3-value cycle: `DLC3_CAPTAIN_SHAGIR` (9 distinct values),
`DLC3_Orias` (8), `DLC3_BERNARD_VAN`/`DLC3_MENDEL`/`DLC3_Darpha_Archer`/
`DLC3_ROGDOR` (5 each), `DLC3_MASTER_LAGINU`/`DLC3_LARLANDOR_UNARMED`/
`DLC3_ELVEN_BOWMAKER` (4 each).

**Critical correction: saves `000000`-`000280` are NOT one continuous
playthrough - there are at least 9 session breaks in the sequence.**
Discovered by checking `parse_save_summary`'s `play_time` and `level`
fields across the full range: playtime *decreases* (and sometimes level
drops) between several consecutive save numbers - most dramatically
between `000220` (level 91, playtime 11 days) and `000221` (level 80,
playtime 1 hour 10 minutes, a completely different location and
mission). Smaller breaks also exist at saves 69→70, 76→77, 108→109,
121→122, 124→125, 153→154, 164→165, 180→181. **This means the save
number is not a reliable chronology - the player reloaded an earlier
checkpoint and continued forward multiple times, creating several
distinct chronological segments that share the same numbered-slot
sequence.** This is a real correction to how this whole investigation
should treat "save order" going forward, not just for this pass -
segments (by save number, inclusive): `[0-69]`, `[70-76]`, `[77-108]`,
`[109-121]`, `[122-124]`, `[125-153]`, `[154-164]`, `[165-180]`,
`[181-220]`, `[221-280]`.

**A promising, convergent finding despite the discontinuity - checked
programmatically, not eyeballed** (an earlier draft of this note
misread `DLC3_Orias`'s two forks as converging; re-verified with a
small script comparing each entity's exact value at save `220` vs. save
`280`, corrected below). Segment `[181-220]` and segment `[221-280]`
are two independent chronological forks (the second starting from an
earlier, lower-level checkpoint than where the first one ended). Of the
9 entities checked this way, **6 converge to the exact same terminal
`PCQ` value at the end of both independent forks**: `DLC3_ROGDOR(90)`
(`802` both), `DLC3_BERNARD_VAN(80)` (`757` both),
`DLC3_MASTER_LAGINU(50)` (`805` both), `DLC3_MENDEL(40)` (`225` both),
`DLC3_LARLANDOR_UNARMED` (`561` both), `DLC3_CAPTAIN_SHAGIR` (`2214`
both). **`DLC3_Orias` does NOT converge** (`338` at save `220` vs. `744`
at save `280`) - the second fork's Orias progressed further than the
first fork ever did, rather than landing on the same value; treat this
one as still-progressing, not settled. `DLC3_ELVEN_BOWMAKER(30)` has no
value at save `220` (`None` - player wasn't near that NPC at that exact
save) so isn't a valid comparison either way. Six-out-of-nine
independently-diverged playthrough forks landing on the *same* terminal
value for the same NPC is meaningful corroboration that those six are
real, stable "reached current maximum progress" states for those NPCs'
own questlines - not coincidence or noise.

**Important caveat, matching Casbrim's own pattern:** Casbrim's `PCQ`
also converges to the same value (`853`) across both forks - and we
already know from the original investigation that `853` is
*accepted-but-not-completed*, not confirmed-solved (the "Aktywna misja"
tracked-quest field never shows Casbrim's quest as active in the
available saves). So reaching a stable terminal value across forks is
evidence of "reached the currently-available maximum progress," not
proof of full completion - the same ambiguity that has blocked this
investigation since the first property-bag breakthrough. **Whether any
of `DLC3_ROGDOR`/`DLC3_BERNARD_VAN`/`DLC3_MASTER_LAGINU`/`DLC3_MENDEL`/
`DLC3_LARLANDOR_UNARMED`/`DLC3_CAPTAIN_SHAGIR`'s questlines were
actually *completed* (as opposed to just reaching their own "settled"
ceiling, like Casbrim) is not something this data alone can answer - it
needs the user's own knowledge of what was actually finished in this
playthrough.**

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/find_pcq_roster.py`,
`script/wd_extract/track_all_pcq_histories.py`,
`script/wd_extract/compress_pcq_runs.py`,
`script/wd_extract/find_session_breaks.py`,
`script/wd_extract/check_save_summaries_around_220.py`.

## User-confirmed breakthrough: fork-convergence in PCQ means quest completion (2026-07-16)

Asked the user directly whether any of the 6 NPCs whose `PCQ` converged
to the same terminal value across the two independent chronological
forks (`DLC3_ROGDOR`, `DLC3_BERNARD_VAN`, `DLC3_MASTER_LAGINU`,
`DLC3_MENDEL`, `DLC3_LARLANDOR_UNARMED`, `DLC3_CAPTAIN_SHAGIR`) had
actually had their questlines *completed* in this playthrough, since
that's not something derivable from the save files alone. **The user
confirmed all six.**

**This empirically validates the pattern found in this pass: reaching a
`PCQ` value that stays stable and reappears identically across
independently-diverged save-history forks (rather than resetting to an
earlier value on the next zone visit) signals that NPC's questline was
completed.** This is the first time this whole investigation has had a
confirmed, positive example of what "quest completed" looks like in the
`PCQ` encoding - previously only "accepted-but-settled" (Casbrim's
`853`) had been observed.

**Casbrim's own `853` remains the open puzzle.** It shows the *exact
same fork-convergence signature* (settles at `853` in both `[181-220]`
and `[221-280]`, per the original investigation and this pass) that
just got validated as "completed" for six other NPCs - yet the
"Aktywna misja" tracked-quest field never shows Casbrim's quest as
active, and the user's own multi-session play history never completed
it. Two explanations, not yet distinguished: (a) fork-convergence is a
necessary but not sufficient signal - it just means "reached the
currently available conversation-tree depth," which happens to equal
full completion for short quests but not for Casbrim's longer "Expert
Side Adventure" (a title that itself implies more content than a
typical side quest); or (b) something else in the property bag (`PSDN`,
`PQUS`, `PQBS`, `PQTIMED` - not yet examined for this purpose) actually
carries the real completed/not-completed distinction, and `PCQ`
convergence alone is coincidental for the six confirmed cases.

**Immediate next step, not yet done:** compare the *full* property bag
(all keys, not just `PCQ`) between the six confirmed-completed NPCs and
Casbrim, at their respective converged/settled saves, to check whether
any other key (most likely candidate: `PQBS`, given the "S" could stand
for "solved"/"state") differs in a way that distinguishes "genuinely
completed" from "reached-current-ceiling."

## Full property-bag comparison: no separate "completed" flag exists (2026-07-16)

Pulled the complete property bag (every key, not just `PCQ`) for
Casbrim and all 6 confirmed-completed NPCs at save `000280`, using the
exact same first-occurrence-with-`PCQ` matching logic that built the
validated `PCQ` timelines (not `find_pcq_roster.py`'s "nearest
preceding name" heuristic, which was found to sometimes land on a
*different* bag - e.g. a stale template copy - with a different `PCQ`
value than the validated history; a real methodological trap worth
remembering for any future work on this data: an entity name can have
multiple property-bag instances in the same save, and only the
first-occurrence-with-`PCQ` match has been cross-validated against a
real before/after quest-accept pair).

**Result: no other key distinguishes the confirmed-completed group from
Casbrim.** `PSDN` is `0` and `PQUS` is `2` for all seven, with zero
exceptions - identical for both the completed NPCs and Casbrim's
not-completed state, so neither carries a completion signal. `PQTIMED`
appears only for `DLC3_ROGDOR` and `DLC3_LARLANDOR_UNARMED` (both `0`)
and `eStImmortalUnit` only for `DLC3_CAPTAIN_SHAGIR` (`1`, plausibly an
unrelated combat-unit flag) - neither is consistent across the
confirmed-completed group itself, so neither is a reliable completion
marker either. `Lector` and `PUMN` vary per entity as expected (already
known to be per-NPC identifiers, not state flags).

**This resolves the open question from the previous section in favor
of interpretation (a): there is no separate "completed" flag in the
property bag.** `PCQ` fork-convergence (a value that stays stable and
reappears identically across independently-diverged save-history
forks) is the only observable completion signal this data provides -
and it means "reached the currently-available conversation-tree depth
for this NPC," which happens to coincide with true completion for the
six (apparently shorter) confirmed quests, but not necessarily for
Casbrim's longer "Expert Side Adventure." **The most likely explanation
for Casbrim's `853` not being completion, despite showing the identical
convergence signature, is that his quest simply has more stages beyond
what's reachable in the available save history** - not a hidden
distinguishing flag this investigation missed.

**Practical conclusion for the main project goal:** the toolkit can now
reliably detect "this NPC's questline has progressed as far as the
available save data shows" via `PCQ` fork-convergence (or, within a
single continuous session, via `PCQ` settling and staying constant
across many consecutive saves without reverting) - and, per this
session's user-confirmed cases, that signal *is* full completion for
most quests. Confirming it specifically for Casbrim's quest would
require either further real gameplay (a save where "Aktywna misja"
stops tracking Gods and Demons as active, or a save further past `853`)
or actual `.eco` bytecode decoding to determine the true length of his
dialogue tree - the same wall this investigation's bytecode side-thread
already reached and stopped at.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/full_bags_at_save.py`.

## Back to `.eco` bytecode: relative-offset reference to the table also comes up empty (2026-07-16)

Resumed the `.eco` bytecode side-thread. The prior pass's "what reads
the table" search only checked absolute file offsets; tried the
explicitly-flagged-as-untested alternative: a **relative** displacement
(the operand's own position, or the position right after it, plus a
signed offset landing on the table's start or end) - the standard
relative-jump encoding used by many real ISAs.

**Result: also empty, and even the raw hit count came in under the
noise floor.** Tested every byte position in `RPGCompute.eco` for a
signed 16-bit or 32-bit displacement (both endiannesses, both "from
this position" and "from right after this operand" base conventions)
that would exactly reach the table's start (35051) or end (36107) -
only checking positions where the needed displacement actually fits in
the given width's signed range, not just improbable ones. Found 8 hits
outside the table's own bytes, all small 16-bit matches - fewer than
the roughly 18 coincidental hits pure chance would predict for that
many (width, target, base-convention) combinations, and zero 32-bit
hits at all. **This isn't just "no signal" - it's *below*-chance,
about as clean a negative as this kind of search can produce.**

**Both offset conventions (absolute, now relative) have been tried
against this table and found nothing.** Whatever mechanism the VM uses
to locate this table, it isn't expressible as a simple stored file
offset (absolute or relative) elsewhere in the bytecode - confirming
this really does require identifying actual opcode semantics to make
further progress, not another variation on offset-searching.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/search_relative_offsets.py`.

## Generalizing the flag byte finds no sibling table family (2026-07-16)

Tried a genuinely different angle rather than more offset-searching:
relaxed the confirmed record shape to allow *any* single flag byte
(not just the confirmed `0x80`) - sentinel + 10 zero bytes + [any byte]
+ 7 zero bytes + ascending u32-LE triplet `V,V+4,V+5` - across all 21
real `.eco` scripts, on the theory that a sibling "table family" using
the identical framing but a different flag/type byte might index
something else entirely (most hoped-for: string offsets, which would
finally answer the original "how does bytecode reference a string"
question this whole investigation started with in Stage 1).

**Result: the flag byte is `0x80` in all 196 occurrences, across every
one of the 21 files, with zero exceptions.** No sibling family exists
under this exact framing - the structure really is singular, and its
`V` values only ever reference other 34-byte records (never strings,
already established). This rules out "relax the flag byte" as a route
to a string-referencing structure.

**Where this leaves the bytecode side-thread.** Absolute-offset
reference search, relative-offset reference search, and now flag-byte
generalization have all been tried against this table and its record
shape and found nothing further. Every technique available without
actually decoding real VM opcode semantics has now been exhausted on
this specific structure. Continuing productively from here requires
committing to the larger, originally-flagged-as-out-of-scope effort:
identifying real opcodes (e.g. by examining the bytes immediately
surrounding a call site for the *other* record type already
partially explored - the Stage-1 string literals - with fresh eyes now
that the tightly-packed-with-no-framing structure is well understood,
or by attempting to manually trace one of the smallest scripts,
`DLC_2.eco`/`DLC_3.eco` (1468 bytes, exactly one confirmed record each)
byte-by-byte in full, since their small size makes total manual
coverage newly tractable) - not another pattern-search variation.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/generalize_flag_byte.py`.

## Full trace of a tiny script finds a real, cross-validated instruction cadence (2026-07-16)

With every offset-search/pattern-generalization idea exhausted on the
big files, tried the other concrete idea flagged in the previous
section: fully trace one of the smallest real `.eco` scripts
(`DLC_2.eco`, 1468 bytes total) byte-by-byte, since its size makes
total manual coverage newly tractable, unlike the much larger scripts
this investigation has otherwise worked with.

**Layout confirmed:** 33-byte header (already known) + the confirmed
34-byte sentinel/flag/triplet record (bytes 33-66) + two real strings,
`"Initialize"` (offset 67) and `"Nothing"` (offset 78) - almost
certainly a function name and a description of its (stub) body, given
the name. Checked whether either string's offset or length appears
anywhere in the remaining ~1380 bytes (86 onward) as a u16/u32
integer - a clean, complete negative (not even the tiny length values 7
or 10 turned up), same as the big files' string-reference searches.

**But the remaining bytes (86-338) are NOT random/opaque - they contain
a real, clean, repeating instruction-like pattern**, found by decoding
this small region as 4-byte-aligned u32-LE values instead of continuing
to hand-trace hex (a previously-demonstrated source of error in this
investigation). Structure: a 4-byte "marker" field cycling through
exactly 4 values (`96`, `257`, `97`, `258`, then repeating) immediately
followed by a 4-byte "operand" field, each pair occupying a clean
8-byte stride - i.e. `[marker][operand]` repeating with marker values
`96→257→97→258→96→257→97→258→...` and the operand values climbing
roughly monotonically (`64, 100, 105, 133, 138, 172, 177, 205, 210,
238, 243, 249, 254, 281, 286, 292, 297`, several pairs of which differ
by exactly `5`). All operand values are valid byte offsets within this
1468-byte file, but checking what actually sits at each such position
(treating them as self-referential file offsets) just lands on other
bytes of this same repeating sequence - inconclusive, likely
coincidental range overlap rather than genuine self-reference (both the
operand values and their own file positions happen to fall in the same
86-338 numeric neighborhood).

**Cross-validated against the other two structurally similar tiny
scripts.** `DLC_3.eco` (also 1468 bytes) reproduces the *exact same*
marker sequence at the *exact same* byte positions as `DLC_2.eco` -
the two files are apparently near-duplicate "is this DLC installed"
checks. `DLC_PIRATES.eco` (1474 bytes, name `DLC_PIRATES` is 6
characters longer than `DLC_2`/`DLC_3`) reproduces the identical
pattern shifted by exactly +6 bytes throughout - precisely matching the
header-length difference from the longer name, confirming this is a
real, position-independent structural feature of the format, not
coincidence in one file.

**This is the cleanest instruction-cadence pattern found in this whole
investigation** - a genuine, cross-validated, fixed 8-byte instruction
stride with a small, closed set of marker values (`96`, `97`, `257`,
`258`) - but their actual opcode *semantics* (what each does, what the
climbing operand values represent - byte offsets elsewhere, numeric
literals, or something else) remain undetermined. This is a
substantially better anchor for any future opcode-identification
attempt than anything found in the larger, more complex scripts, since
`DLC_2`/`DLC_3`/`DLC_PIRATES` are small enough to reason about in full
and the pattern is already confirmed to reproduce identically across
files.

**Stopping point for this pass.** Determining what `96`/`97`/`257`/
`258` actually do would need either dynamic analysis (not available -
no debugger, no live instrumentation, the standing constraint on this
entire investigation) or a much deeper static effort: manually
correlating this exact 3-file pattern against what these DLC-check
scripts are known to do in the game (check DLC ownership, likely set a
flag) and treating the small marker set as a closed enumeration to
reason about exhaustively - real progress, but a distinctly bigger
undertaking than this pass, and a natural point to check in before
continuing further.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/dump_dlc2_full.py`,
`script/wd_extract/decode_dlc2_body.py`,
`script/wd_extract/analyze_dlc2_pattern.py`.

## The DLC-script instruction cadence is a generic, content-free template (2026-07-16)

Pushed further on the newly-found instruction cadence by diffing the
three tiny DLC-check scripts byte-for-byte, on the theory that
whatever differs between "check DLC 2" and "check DLC 3" would
pinpoint the DLC-ID-specific field.

**Result: `DLC_2.eco` and `DLC_3.eco` are byte-identical except for
exactly one byte** - offset 20, which is the last character of the
script's own embedded name (`'2'` vs `'3'`, i.e. the name string
itself, not any separate ID field). `DLC_PIRATES.eco` (whose longer
name shifts everything after the header by +6 bytes) is **fully
byte-identical** to `DLC_2.eco` once that shift is accounted for -
zero differing bytes anywhere in the shared region.

**This means the marker/operand instruction cadence found in the
previous section carries zero DLC-specific content.** It's a fully
generic template, reused verbatim for every DLC-check script - the
game must associate a specific DLC with a specific script purely via
the script's own name (matched externally, likely by the engine or
some other registry not in this file), not via anything encoded in its
bytecode. This also reframes the `"Initialize"`/`"Nothing"` strings
found earlier: this is very likely a genuine placeholder/stub function
body (`Initialize` that does `Nothing`), and the marker/operand pattern
is boilerplate scaffolding for a trivial empty function - not
business-logic opcodes.

**Reframed as a positive tool rather than a dead end: this is now a
confirmed fingerprint for "a trivial/stub function body."** If the same
exact byte pattern appears inside a larger, business-logic-bearing
script (e.g. `TwoWorlds2Quests.eco`), it would help delineate function
boundaries there - a stub function is still a function, and finding
several would map out where real (non-stub) function bodies must sit,
even without decoding what those do yet.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/extract_dlc_scripts.py`,
`script/wd_extract/diff_dlc_scripts.py`.

## Correction: the marker cadence is pervasive, not stub-specific (2026-07-16)

Checked all 21 real scripts for the same `{96, 257, 97, 258}` marker
cadence found in the DLC-check stub, to see if it helps map function
boundaries elsewhere. **It does not narrowly mark stub functions - it
is a pervasive, general structural element appearing throughout every
single one of the 21 scripts**, in run lengths ranging from 4 markers
(one cycle) up to 324 consecutive markers in `RPGCompute.eco` (at file
offset 86711-89299) and a second 196-marker run right after it
(89391-90955). A run that long cannot plausibly be one trivial stub
function - `RPGCompute.eco` is the large computation-heavy library, not
a placeholder-function-dense file.

**This corrects the previous section's framing.** The DLC-check
scripts' occurrence of this pattern isn't special because it marks
"a stub" - it's just an unusually *short*, isolated instance of an
otherwise-ubiquitous instruction cadence, made visible because those
scripts are almost entirely composed of little else. The far more
likely interpretation, given how common and long-running this pattern
is: `96`/`97`/`257`/`258` are a **generic, frequently-used instruction**
(most plausibly something like "push a small integer/constant onto a
stack," alternating between two closely-related opcode variants) rather
than anything specific to trivial placeholder bodies. This reframes but
doesn't invalidate the DLC-check diff finding from the previous
section - `DLC_2`/`DLC_3`/`DLC_PIRATES` genuinely are byte-identical
generic templates, that part still stands; it's the *reason* (stub vs.
"trivial script that's almost entirely this one common instruction")
that changes.

**This is still useful, still a positive finding, and still short of
full semantics.** It confirms `96`/`97`/`257`/`258` form the single
most common, cleanly-cadenced instruction pattern identified in this
entire investigation, occurring at every scale from a handful of
repeats to hundreds - a strong signal this is a fundamental,
high-frequency primitive of the instruction set (a real candidate for
"the first opcode to actually decode," if this investigation continues
toward genuine opcode semantics), but what the two opcode-pairs
(`96`/`257` vs. `97`/`258`) actually *do*, and what the climbing operand
values represent, remain undetermined by static analysis alone.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/search_stub_fingerprint.py`.

## Tying the two threads together: PCQ/quest-ID constants not found among push-constant operands (2026-07-16)

With dynamic analysis confirmed off the table (asked the user directly
rather than continuing to assume it), tried the most promising
remaining static idea: use the newly-confirmed `{96,257,97,258}`
"push a constant" instruction pattern as a structural anchor to search
for the *already-known-semantic* `PCQ` transition values (`20`, `3483`,
`853`, confirmed via the real before/after quest-accept save pair) and
quest IDs (`45` for `Q_45`, `2` for `GROUP_2`, confirmed via
cross-language validation) inside `TwoWorlds2Quests.eco` specifically -
the one script that actually contains this quest's logic. This is a
structurally-anchored test (only checking operands of a confirmed,
cleanly-cadenced instruction, not a blind byte scan), unlike earlier
Stage 1 attempts that searched raw bytes near string anchors.

**Result: clean, complete negative.** Found 88 total marker+operand
pairs in `TwoWorlds2Quests.eco`'s clean (8-byte-stride, full-cycle)
runs of this instruction. Zero of the 88 operands match any of the 5
target constants. Whatever mechanism actually compares against `PCQ`'s
values in the compiled quest logic, it isn't via this specific "push a
small constant" instruction carrying one of these literal numbers as
its direct operand.

**Assessment: the static-analysis avenues for this bytecode are now
genuinely exhausted for connecting it back to the save-file findings.**
Across this investigation: string-offset anchoring (Stage 1), gap
content inspection, absolute and relative offset-reference search,
flag-byte generalization, full manual tracing of a tiny script, and now
this constant-value cross-reference have all been tried. Real further
progress would need either dynamic analysis (confirmed unavailable) or
accepting that identifying actual opcode semantics from static bytes
alone, with no ground truth beyond structural self-consistency, is a
fundamentally harder problem than this investigation's find-and-
correlate techniques can solve - a legitimate stopping point for this
side-thread, not a failure of effort.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/extract_quests.py`,
`script/wd_extract/search_pcq_constants.py`.

## User reports Casbrim's quest is genuinely bugged (not under-observed) - practical workaround attempt (2026-07-16)

The user clarified that Casbrim's "Gods and Demons" quest never
progressing past `PCQ=853` isn't a gap in the available save data -
it's a real, known-to-the-user in-game bug that prevents the quest
from advancing at all. This reframes the goal from "find how
completion is encoded" (research) to "find a practical save-edit
workaround" (a fix).

**Checked two new leads for a hidden quest-journal flag - both ruled
out.** (1) `PQBS` (78 occurrences in a save) is **unrelated** to
dialogue-quest tracking - every entity carrying it is a combat
mob/spawn or weapon-drop item (e.g. `BATMANS_ARCHER_01_E`,
`Fenrir_Sword_1`, `DLC3_DESERT_DEMON_12`), none of which have a `PCQ`
at all; it's almost certainly a "has this unique
enemy/drop already spawned" flag, not a quest-completion marker.
(2) `QUEST_GHOST_DLC` and `DLC3_QUESTWAND_1/2/3` (thematically
suggestive names found via a broader named-record scan) did not yield
a property bag in this pass. Combined with the original 2026-07-11
investigation's exhaustive check (the confirmed quest ID `45`/`GROUP_2`
against all ~969 property bags in a save - zero matches anywhere),
**there is no separate save-file structure tracking "is this quest
complete" - `PCQ` is the only lever this investigation has found.**

**Checked Queen Arbellen (mechanically tied to the same Casbrim-accept
trigger, but a different quest) for comparison.** Her `PCQ` converges
to `992` in both independent chronological forks (`[181-220]` and
`[221-280]`) - the same validated completion signature found for the
six confirmed-completed NPCs earlier this session. This confirms the
bug is specific to *Casbrim's own* script logic, not a save-wide data
problem: the same "talk to Casbrim" trigger correctly advances
Arbellen's parallel quest while Casbrim's own stays stuck.

**No data-only method can determine the correct "next" PCQ value** -
`853` never changed into anything else across the entire available
save history, and this session's `.eco` bytecode work could not
recover the actual comparison logic that would reveal it. Also
genuinely possible: PCQ may not even be the true blocker (the bug
could be in an unrelated precondition that never fires).

**Delivered an experimental diagnostic instead of a derived fix** -
the same category of action as the earlier (successful) Casbrim-
position patch experiment. Generated three candidate saves, each a
copy of `saves/remote/000280.TwoWorldsIISave` with *only* Casbrim's
`PCQ` value changed (same-length ASCII substitution: `853`→`854`/
`900`/`999`, chosen as a low-risk, easy-to-verify range of guesses,
not derived from any specific evidence about the correct value) via
`patch_zlib_block`:
- `files/quest_saves/000280_casbrim_pcq_854.TwoWorldsIISave`
- `files/quest_saves/000280_casbrim_pcq_900.TwoWorldsIISave`
- `files/quest_saves/000280_casbrim_pcq_999.TwoWorldsIISave`

Verified: the original save's SHA-256 hash is unchanged after all
patch operations; each candidate file decompresses cleanly and shows
*only* the `PCQ` field changed (every other property in Casbrim's own
bag - `PSDN`, `PQUS`, `Lector`, `PUMN` - byte-identical to the
original).

**This is a genuine experiment, not a confirmed fix** - report back
what happens with each candidate (does dialogue open at all? does
anything visibly change?) so the next attempt can be informed by what
was actually observed in-game, the same iterative approach already
used successfully for the position-patch diagnostic.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/search_quest_lifecycle_in_save.py`,
`script/wd_extract/investigate_pqbs_and_ghost.py`,
`script/wd_extract/track_arbellen_pcq.py`,
`script/wd_extract/locate_casbrim_pcq_bytes.py`,
`script/wd_extract/patch_casbrim_pcq_candidates.py`,
`script/wd_extract/verify_patched_saves.py`.

## Combined reposition+PCQ candidates, and the "PCQ never duplicated across quests" assumption falsified (2026-07-16)

Two follow-ups requested: (1) the PCQ-candidate saves need Casbrim's
position fix too, since he's not otherwise visible/findable; (2) a
list of "possible" PCQ values, on the user's working assumption that
PCQ increases monotonically and is never reused across different
quests/NPCs.

**Combined saves delivered by reapplying the exact confirmed-working
byte diff, not re-deriving the float patch.** Diffed
`000280_casbrim_repositioned.TwoWorldsIISave` (from the original
2026-07-11 position experiment) against the plain original `000280` at
the byte level: exactly 23 differing bytes, all within Casbrim's own
transform region (chunk offsets 1535789-1535847) - completely disjoint
from the PCQ value's location (1535901), confirmed non-overlapping.
Reapplied those same 23 bytes on top of each PCQ candidate in one
patch pass:
- `files/quest_saves/000280_casbrim_repositioned_pcq_854.TwoWorldsIISave`
- `files/quest_saves/000280_casbrim_repositioned_pcq_900.TwoWorldsIISave`
- `files/quest_saves/000280_casbrim_repositioned_pcq_999.TwoWorldsIISave`

Verified: original's hash unchanged; each combined file has exactly
23 position-patch bytes plus only the expected PCQ digit changes (1
differing digit for `854` vs. `853`, 3 for `900`/`999`) - nothing else
touched.

**Built a global catalog of every distinct PCQ value ever observed for
all 40 roster entities across the full 0-280 save range, to test the
"never duplicated" assumption directly rather than assume it.** Result:
**the assumption is empirically false.** Excluding same-entity
bare-name/`(NN)`-suffix pairs (which are the same NPC's own two bag
instances, not different quests), there are genuine cross-entity
duplicates: `DLC3_ROGDOR` (one of the six confirmed-completed quests
from earlier this session) shares the exact values `89`, `991`, and
`992` with `DLC3_KING_TALINOR` and `DLC3_Darpha_Archer` - completely
different, unrelated NPCs. This is consistent with `PCQ` being a
conversation/dialogue-state index drawn from a **shared, reusable pool**
(e.g. common dialogue-tree template nodes), not a globally unique
per-quest identifier - so "value X is unused elsewhere" cannot be
treated as confirmation that X is a valid or safe guess for Casbrim's
own quest, only as one weak, non-conclusive data point.

**With that caveat clearly stated, the observed global value landscape**
(88 distinct values across 40 entities, full range `0` to `3489`):
`[0, 1, 7, 12, 18, 20, 21, 22, 25, 47, 55, 63, 73, 74, 89, 118, 145,
149, 150, 166, 167, 181, 183, 184, 191, 198, 199, 200, 202, 204, 207,
218, 225, 226, 227, 228, 230, 238, 267, 270, 292, 338, 346, 445, 454,
456, 458, 463, 471, 561, 563, 566, 595, 630, 653, 659, 666, 667, 729,
730, 744, 746, 756, 757, 765, 781, 785, 789, 793, 794, 795, 802, 805,
810, 830, 840, 853, 937, 985, 991, 992, 1202, 1206, 1242, 2112, 2214,
3483, 3489]`. Immediately above Casbrim's `853`, the range `854-936` is
completely unused by any of the 40 cataloged entities - the widest
open gap directly adjacent to his stuck value. The two already-chosen
higher candidates (`900`, `999`) both land in currently-unused gaps
(`854-936` and `993-1201` respectively) - not derived from this
analysis, but not contradicted by it either.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/diff_repositioned_save.py`,
`script/wd_extract/patch_reposition_and_pcq.py`,
`script/wd_extract/build_global_pcq_catalog.py`.

## Direct answer on Abraham/Bernard Van, and a newly-noticed convergence case (2026-07-16)

User asked for `DLC3_ABRAHAM_VAN`'s and `DLC3_BERNARD_VAN`'s specific
`PCQ` values (both side-quest NPCs). Got precise full histories:

- `DLC3_BERNARD_VAN(80)`: cycles `181→183→184` per visit, settles at
  `184`, converges to **`757`** at the end of both independent
  chronological forks (`220` and `280`) - already user-confirmed
  completed earlier this session.
- `DLC3_ABRAHAM_VAN(67)`: cycles `63→566` per visit, settles at `566`,
  **also converges to `566`** at the end of both forks (`220` and
  `280`) - the identical fork-convergence signature already validated
  as a completion signal, but Abraham wasn't among the original 9
  candidates checked for this (he only had 2 distinct values in the
  first summary pass, below the threshold used to pick candidates
  worth a closer look). **Not yet confirmed by the user** whether
  Abraham's own quest was actually completed - flagged for the user to
  confirm, same as the original six.

Scratch scripts for this pass (gitignored, not committed):
`script/wd_extract/track_abraham_bernard.py`.
