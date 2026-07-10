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
