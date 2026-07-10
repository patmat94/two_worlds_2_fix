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


SEARCH_ENCODINGS = ("ascii", "utf-16-le")


@dataclass
class Match:
    term: str
    encoding: str
    offset: int
    context: str


def _context(data: bytes, offset: int, length: int, radius: int = 16) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + length + radius)
    snippet = data[start:end]
    printable = "".join(chr(b) if 32 <= b < 127 else "." for b in snippet)
    return f"{snippet.hex(' ')} | {printable}"


def search_text_multi(data: bytes, terms: list[str]) -> list[Match]:
    matches: list[Match] = []
    for term in terms:
        for encoding in SEARCH_ENCODINGS:
            try:
                needle = term.encode(encoding)
            except UnicodeEncodeError:
                continue
            start = 0
            while True:
                idx = data.find(needle, start)
                if idx == -1:
                    break
                matches.append(
                    Match(
                        term=term,
                        encoding=encoding,
                        offset=idx,
                        context=_context(data, idx, len(needle)),
                    )
                )
                start = idx + 1
    return matches


@dataclass
class DiffRegion:
    op: str
    a_start: int
    a_end: int
    b_start: int
    b_end: int
    a_bytes: bytes
    b_bytes: bytes


def diff_byte_regions(a: bytes, b: bytes) -> list[DiffRegion]:
    max_prefix = min(len(a), len(b))
    prefix_len = 0
    while prefix_len < max_prefix and a[prefix_len] == b[prefix_len]:
        prefix_len += 1

    max_suffix = max_prefix - prefix_len
    suffix_len = 0
    while (
        suffix_len < max_suffix
        and a[len(a) - 1 - suffix_len] == b[len(b) - 1 - suffix_len]
    ):
        suffix_len += 1

    a_start, a_end = prefix_len, len(a) - suffix_len
    b_start, b_end = prefix_len, len(b) - suffix_len

    if a_start == a_end and b_start == b_end:
        return []

    if a_start == a_end:
        op = "insert"
    elif b_start == b_end:
        op = "delete"
    else:
        op = "replace"

    return [
        DiffRegion(
            op=op,
            a_start=a_start,
            a_end=a_end,
            b_start=b_start,
            b_end=b_end,
            a_bytes=a[a_start:a_end],
            b_bytes=b[b_start:b_end],
        )
    ]
