import struct
import zlib
from pathlib import Path

import pytest

from tw2tools.wd_format import decompress_all_blocks, find_zlib_offsets, parse_archive_entries, search_text_multi


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
