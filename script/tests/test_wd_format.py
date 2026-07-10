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
