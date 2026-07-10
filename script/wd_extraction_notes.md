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
- The numeric-ID-indexed quest table, the `.wd`/`.eco` payload-location
  problem, and actually decoding the level/quest script logic that selects
  between named position markers all remain open — these would need
  `.eco` payload extraction (still unresolved) to make further progress,
  since that's where the actual scripted logic lives.
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
