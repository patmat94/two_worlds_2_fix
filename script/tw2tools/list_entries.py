"""CLI: parse archive entry records out of extracted .wd chunk files."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import parse_archive_entries


def collect_entries(path: Path, suffix_filter: str | None) -> list[dict]:
    chunk_files = sorted(path.glob("*.bin")) if path.is_dir() else [path]

    rows: list[dict] = []
    for chunk_file in chunk_files:
        data = chunk_file.read_bytes()
        for entry in parse_archive_entries(data):
            if suffix_filter and not entry.path.lower().endswith(suffix_filter.lower()):
                continue
            row = asdict(entry)
            row["source_chunk"] = chunk_file.name
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List archive entry records parsed from .wd chunk file(s)"
    )
    parser.add_argument("path", type=Path, help="A chunk .bin file or a directory of chunk files")
    parser.add_argument(
        "--filter",
        dest="suffix_filter",
        default=None,
        help="Only include entries whose path ends with this suffix, e.g. .eco",
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write the full entry table as JSON"
    )
    args = parser.parse_args()

    rows = collect_entries(args.path, args.suffix_filter)
    print(f"Found {len(rows)} entr{'y' if len(rows) == 1 else 'ies'}")
    for row in rows[:20]:
        print(f"  {row['source_chunk']}: {row['path']} type_id={row['type_id']} flags={row['flags']}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full table to {args.json_out}")


if __name__ == "__main__":
    main()
