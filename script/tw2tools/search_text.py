"""CLI: search files for text under multiple encodings (ASCII, UTF-16LE)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import search_text_multi


def collect_matches(path: Path, terms: list[str]) -> list[dict]:
    files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]

    rows: list[dict] = []
    for file_path in files:
        data = file_path.read_bytes()
        for match in search_text_multi(data, terms):
            row = asdict(match)
            row["file"] = str(file_path)
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Search file(s) for text under multiple encodings")
    parser.add_argument("path", type=Path, help="A single file or a directory to search recursively")
    parser.add_argument(
        "--term", dest="terms", action="append", required=True, help="Search term (repeatable)"
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full match table as JSON"
    )
    args = parser.parse_args()

    rows = collect_matches(args.path, args.terms)
    print(f"Found {len(rows)} match(es)")
    for row in rows[:20]:
        print(f"  {row['file']} term={row['term']!r} encoding={row['encoding']} offset={row['offset']}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full match table to {args.json_out}")


if __name__ == "__main__":
    main()
