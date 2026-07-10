"""CLI: compare two save/header files and report the changed byte region."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import diff_byte_regions


def main() -> None:
    parser = argparse.ArgumentParser(description="Diff two Two Worlds II save (or header) files")
    parser.add_argument("save_a", type=Path, help="First save/header file")
    parser.add_argument("save_b", type=Path, help="Second save/header file")
    parser.add_argument(
        "--min-size", type=int, default=1, help="Skip regions smaller than this many bytes"
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full diff regions as JSON"
    )
    args = parser.parse_args()

    a_data = args.save_a.read_bytes()
    b_data = args.save_b.read_bytes()
    regions = diff_byte_regions(a_data, b_data)
    regions = [r for r in regions if max(len(r.a_bytes), len(r.b_bytes)) >= args.min_size]

    print(f"Found {len(regions)} changed region(s) (sizes: a={len(a_data)} b={len(b_data)})")
    for region in regions:
        print(
            f"  {region.op}: a[{region.a_start}:{region.a_end}] ({len(region.a_bytes)}B) -> "
            f"b[{region.b_start}:{region.b_end}] ({len(region.b_bytes)}B)"
        )

    if args.json_out:
        rows = [
            {**asdict(r), "a_bytes": r.a_bytes.hex(), "b_bytes": r.b_bytes.hex()} for r in regions
        ]
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full diff to {args.json_out}")


if __name__ == "__main__":
    main()
