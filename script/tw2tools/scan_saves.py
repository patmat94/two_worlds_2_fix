"""CLI: scan consecutive save-file pairs for small, localized byte-region changes."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import diff_byte_regions

SAVE_NAME_RE = re.compile(r"^(\d+)\.TwoWorldsIISave$")


def find_save_sequence(saves_dir: Path) -> list[tuple[int, Path]]:
    saves = []
    for path in saves_dir.iterdir():
        match = SAVE_NAME_RE.match(path.name)
        if match:
            saves.append((int(match.group(1)), path))
    return sorted(saves, key=lambda item: item[0])


def scan_saves(saves_dir: Path, max_region_size: int) -> list[dict]:
    saves = find_save_sequence(saves_dir)
    rows: list[dict] = []
    for (index_a, path_a), (index_b, path_b) in zip(saves, saves[1:]):
        a_data = path_a.read_bytes()
        b_data = path_b.read_bytes()
        for region in diff_byte_regions(a_data, b_data):
            if max(len(region.a_bytes), len(region.b_bytes)) > max_region_size:
                continue
            row = asdict(region)
            row["a_bytes"] = region.a_bytes.hex()
            row["b_bytes"] = region.b_bytes.hex()
            row["save_a"] = index_a
            row["save_b"] = index_b
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan consecutive save-file pairs for small, localized byte-region changes"
    )
    parser.add_argument(
        "saves_dir", type=Path, help="Directory containing NNNNNN.TwoWorldsIISave files"
    )
    parser.add_argument(
        "--max-region-size",
        type=int,
        default=256,
        help="Only report changed regions at or below this size in bytes (default: 256)",
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full results as JSON"
    )
    args = parser.parse_args()

    rows = scan_saves(args.saves_dir, args.max_region_size)
    print(
        f"Found {len(rows)} small region(s) (<= {args.max_region_size} bytes) "
        "across consecutive save pairs"
    )
    for row in rows[:20]:
        print(
            f"  save {row['save_a']:06d}->{row['save_b']:06d}: {row['op']} "
            f"a[{row['a_start']}:{row['a_end']}] -> b[{row['b_start']}:{row['b_end']}]"
        )
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full results to {args.json_out}")


if __name__ == "__main__":
    main()
