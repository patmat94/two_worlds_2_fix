"""CLI: extract all zlib-compressed blocks from a Two Worlds II .wd archive."""
from __future__ import annotations

import argparse
from pathlib import Path

from tw2tools.wd_format import decompress_all_blocks


def extract(archive_path: Path, output_dir: Path) -> int:
    data = archive_path.read_bytes()
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for offset, chunk in decompress_all_blocks(data):
        chunk_name = f"{archive_path.stem}_chunk_{offset:08x}.bin"
        (output_dir / chunk_name).write_bytes(chunk)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract zlib blocks from a Two Worlds II .wd archive"
    )
    parser.add_argument("archive", type=Path, help="Path to the .wd archive")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("wd_extract"),
        help="Destination folder for decompressed chunk files (default: ./wd_extract)",
    )
    args = parser.parse_args()

    count = extract(args.archive, args.output_dir)
    print(f"Extracted {count} block(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
