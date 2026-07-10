import struct
import zlib
from pathlib import Path

import pytest

from tw2tools.wd_format import decompress_all_blocks, find_zlib_offsets, parse_archive_entries, search_text_multi, diff_byte_regions, parse_save_summary, find_named_records, parse_property_bags, patch_zlib_block, find_eco_files


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


def test_search_text_multi_finds_ascii():
    data = b"padding" + "Casbrim".encode("ascii") + b"padding"
    matches = search_text_multi(data, ["Casbrim"])
    assert any(m.encoding == "ascii" and m.offset == 7 for m in matches)


def test_search_text_multi_finds_utf16le_including_polish_diacritics():
    needle = "Ekspercka przygoda poboczna".encode("utf-16-le")
    data = b"\x00\x00" + needle + b"\x00\x00"
    matches = search_text_multi(data, ["Ekspercka przygoda poboczna"])
    assert any(m.encoding == "utf-16-le" and m.offset == 2 for m in matches)


def test_search_text_multi_handles_terms_with_diacritics_ascii_encode_fails():
    # This test verifies the UnicodeEncodeError catch branch for terms with actual Polish diacritics
    term = "Starożytna kopalnia"  # Contains "ż", a non-ASCII Polish character
    needle = term.encode("utf-16-le")
    data = b"\x00\x00" + needle + b"\x00\x00"
    matches = search_text_multi(data, [term])
    # Should find a UTF-16LE match at the expected offset
    assert len(matches) >= 1
    assert any(m.encoding == "utf-16-le" and m.offset == 2 for m in matches)
    # Verify no spurious ASCII match is produced (since term.encode("ascii") would fail)
    assert not any(m.encoding == "ascii" for m in matches if m.term == term)


def test_search_text_multi_no_match_returns_empty_list():
    data = b"nothing interesting here"
    assert search_text_multi(data, ["Casbrim"]) == []


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


def _build_save_summary_block(text: str) -> bytes:
    encoded = text.encode("utf-16-le")
    char_count = len(text)
    return struct.pack("<I", char_count) + encoded


def test_parse_save_summary_extracts_known_fields():
    text = "Miejsce: Zamek Vahkmaar\nCzas gry: 03:39\nAktywna misja: Ucieczka z wiezienia\nPoziom: 1\nPD: 0/2600"
    data = b"leading garbage" + _build_save_summary_block(text) + b"trailing garbage"
    summary = parse_save_summary(data)
    assert summary is not None
    assert summary.location == "Zamek Vahkmaar"
    assert summary.play_time == "03:39"
    assert summary.active_mission == "Ucieczka z wiezienia"
    assert summary.level == "1"
    assert summary.experience == "0/2600"
    assert summary.raw_text == text


def test_parse_save_summary_returns_none_when_anchor_missing():
    assert parse_save_summary(b"no summary block here") is None


def test_find_named_records_finds_length_prefixed_ascii_names():
    blob = (
        b"noise"
        + struct.pack("<I", 7)
        + b"MyFlag1"
        + b"gap"
        + struct.pack("<I", 16)
        + b"CasbrimTriggered"
        + b"tail"
    )
    records = find_named_records(blob)
    names = [r.name for r in records]
    assert "MyFlag1" in names
    assert "CasbrimTriggered" in names


def test_find_named_records_respects_length_bounds():
    # length prefix of 2 is below the default min_length=3, so it must not match
    blob = struct.pack("<I", 2) + b"AB"
    assert find_named_records(blob, min_length=3, max_length=64) == []


def test_find_named_records_rejects_non_printable_candidates():
    blob = struct.pack("<I", 5) + b"\x00\x01\x02\x03\x04"
    assert find_named_records(blob) == []


def _build_property_bag(pairs: list[tuple[str, str]]) -> bytes:
    out = struct.pack("<I", len(pairs))
    for key, value in pairs:
        out += struct.pack("<I", len(key)) + key.encode("ascii")
        out += struct.pack("<I", len(value)) + value.encode("ascii")
    return out


def test_parse_property_bags_finds_key_value_pairs():
    blob = b"noise" + _build_property_bag(
        [("PCQ", "3483"), ("PSDN", "0"), ("PQUS", "2")]
    ) + b"tail"
    bags = parse_property_bags(blob)
    assert len(bags) == 1
    assert bags[0].properties == {"PCQ": "3483", "PSDN": "0", "PQUS": "2"}


def test_parse_property_bags_respects_count_bounds():
    # count of 0 is below the default min_props=1, must not match
    blob = struct.pack("<I", 0)
    assert parse_property_bags(blob) == []


def test_parse_property_bags_ignores_malformed_candidates():
    # count says 2 pairs but there's only one valid key/value present
    blob = struct.pack("<I", 2) + struct.pack("<I", 3) + b"PCQ" + struct.pack("<I", 4) + b"3483"
    assert parse_property_bags(blob) == []


def test_patch_zlib_block_replaces_content_and_preserves_surrounding_bytes():
    original_payload = b"original content here"
    compressed = zlib.compress(original_payload)
    data = b"PREFIX" + compressed + b"SUFFIX"
    offset = len(b"PREFIX")

    new_payload = b"replaced content, different length!!"
    patched = patch_zlib_block(data, offset, new_payload)

    assert patched.startswith(b"PREFIX")
    assert patched.endswith(b"SUFFIX")
    blocks = list(decompress_all_blocks(patched))
    assert len(blocks) == 1
    assert blocks[0][1] == new_payload


def test_patch_zlib_block_raises_for_invalid_offset():
    with pytest.raises(ValueError):
        patch_zlib_block(b"not a zlib stream at all", 0, b"data")


def _build_eco_file(name: str, body: bytes = b"") -> bytes:
    header = b"ECO" + b"\x00" + struct.pack("<HH", 0, 6)
    name_bytes = name.encode("ascii")
    return header + struct.pack("<II", 3, len(name_bytes)) + name_bytes + body


def test_find_eco_files_identifies_by_embedded_name():
    data = b"padding" + _build_eco_file("DLC_3", b"bytecode...") + b"trailing"
    files = find_eco_files(data)
    assert len(files) == 1
    assert files[0].name == "DLC_3"
    assert files[0].data.startswith(b"ECO")


def test_find_eco_files_returns_empty_list_when_no_magic_present():
    assert find_eco_files(b"nothing interesting here") == []
