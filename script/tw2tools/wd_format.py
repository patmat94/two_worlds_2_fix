"""Core parsing logic for Two Worlds II .wd archives and save files."""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
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
