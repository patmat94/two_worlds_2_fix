from pathlib import Path
import argparse
import zlib
import re

ZLIB_SIGNATURES = [b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda"]
ENTRY_MARKERS = [b"$", b"*"]


def find_zlib_offsets(data):
    offsets = []
    for sig in ZLIB_SIGNATURES:
        start = 0
        while True:
            idx = data.find(sig, start)
            if idx == -1:
                break
            offsets.append(idx)
            start = idx + 1
    return sorted(set(offsets))


def decompress_at(data, offset):
    try:
        obj = zlib.decompressobj()
        result = bytearray()
        pos = offset
        while pos < len(data):
            chunk = data[pos : pos + 32768]
            result.extend(obj.decompress(chunk))
            pos += len(chunk)
            if obj.unused_data:
                return bytes(result), offset + pos - len(obj.unused_data)
            if obj.eof:
                return bytes(result), pos
        if obj.eof:
            return bytes(result), pos
        return None, None
    except zlib.error:
        return None, None


def parse_archive_entries(data):
    entries = []
    pos = 0
    while True:
        idx = data.find(b"\x01\x00", pos)
        if idx == -1:
            break
        marker_pos = None
        for marker in ENTRY_MARKERS:
            candidate = data.rfind(marker, pos, idx)
            if candidate != -1 and (marker_pos is None or candidate > marker_pos):
                marker_pos = candidate
        if marker_pos is None or idx - marker_pos < 4:
            pos = idx + 2
            continue
        name_bytes = data[marker_pos + 1 : idx]
        if len(name_bytes) < 3 or any(b < 32 or b > 126 for b in name_bytes):
            pos = idx + 2
            continue
        try:
            path_name = name_bytes.decode("ascii")
        except UnicodeDecodeError:
            path_name = name_bytes.decode("latin1", errors="replace")
        field_start = idx + 2
        if field_start + 16 > len(data):
            break
        type_id = int.from_bytes(data[field_start : field_start + 2], "little")
        flags = int.from_bytes(data[field_start + 2 : field_start + 4], "little")
        offset = int.from_bytes(data[field_start + 4 : field_start + 8], "little")
        length = int.from_bytes(data[field_start + 8 : field_start + 12], "little")
        extra = int.from_bytes(data[field_start + 12 : field_start + 16], "little")
        entries.append({
            "marker": data[marker_pos:marker_pos+1].decode("ascii", errors="ignore"),
            "path": path_name,
            "type_id": type_id,
            "flags": flags,
            "offset": offset,
            "length": length,
            "extra": extra,
            "entry_pos": marker_pos,
            "data_pos": field_start,
        })
        pos = field_start + 16
    return entries


def clean_path(path_name: str) -> Path:
    clean = path_name.replace("\\", "/")
    clean = clean.lstrip("./")
    return Path(*[p for p in clean.split("/") if p])


def extract_wd(path: Path, output_dir: Path, max_blocks: int | None = None, extract_files: bool = False, only_eco: bool = False):
    data = path.read_bytes()
    offsets = find_zlib_offsets(data)
    print(f"Found {len(offsets)} candidate zlib offsets in {path.name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted = 0
    file_count = 0
    for offset in offsets:
        if max_blocks is not None and extracted >= max_blocks:
            break
        out_data, end = decompress_at(data, offset)
        if out_data is None:
            continue
        chunk_name = f"{path.stem}_chunk_{offset:08x}.bin"
        chunk_path = output_dir / chunk_name
        chunk_path.write_bytes(out_data)
        print(f"  extracted {chunk_name}: {len(out_data)} bytes (offset 0x{offset:x})")
        entries = parse_archive_entries(out_data)
        if entries:
            print(f"    found {len(entries)} archive entries")
            for entry in entries[:10]:
                print("     ", entry["path"], "offset", entry["offset"], "len", entry["length"], "flags", entry["flags"])
            if extract_files:
                files_dir = output_dir / f"{path.stem}_files_{offset:08x}"
                for entry in entries:
                    if only_eco and not entry["path"].lower().endswith(".eco"):
                        continue
                    out_offset = entry["offset"]
                    out_length = entry["length"]
                    if out_offset + out_length > len(out_data) or out_length <= 0:
                        continue
                    file_path = files_dir / clean_path(entry["path"])
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_bytes(out_data[out_offset : out_offset + out_length])
                    file_count += 1
                if file_count:
                    print(f"    extracted {file_count} files to {files_dir}")
        strings = re.findall(rb"[ -~]{8,}", out_data[:32768])
        if strings:
            print(f"    sample strings: {strings[:8]}")
        extracted += 1
    if extracted == 0:
        print("No valid zlib blocks extracted.")
    else:
        print(f"Extracted {extracted} blocks to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Extract Two Worlds II .wd archive blocks and optional file entries")
    parser.add_argument("archive", type=Path, help="Path to the .wd archive")
    parser.add_argument("output_dir", type=Path, nargs="?", default=Path("wd_extract"), help="Destination folder for decompressed blocks and extracted files")
    parser.add_argument("--max", type=int, default=10, help="Maximum number of blocks to extract")
    parser.add_argument("--extract-files", action="store_true", help="Extract files in detected archive entries")
    parser.add_argument("--only-eco", action="store_true", help="Only extract .eco files from detected archive entries")
    args = parser.parse_args()
    extract_wd(args.archive, args.output_dir, max_blocks=args.max, extract_files=args.extract_files, only_eco=args.only_eco)


if __name__ == "__main__":
    main()
