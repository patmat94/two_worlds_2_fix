"""CLI: extract the human-readable save summary from Two Worlds II save files.

The summary (location, play time, active mission, level, experience) is
stored raw in the small `_header` file, and also embedded (after
decompression) in the main save file's compressed state blob. This tool
prefers the fast header-file path and only decompresses the main save file
as a fallback.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from tw2tools.wd_format import decompress_all_blocks, parse_save_summary

SAVE_STEM_RE = re.compile(r"^(\d+)\.TwoWorldsIISave(_header)?$")


def find_save_stems(saves_dir: Path) -> list[str]:
    stems: set[str] = set()
    for path in saves_dir.iterdir():
        match = SAVE_STEM_RE.match(path.name)
        if match:
            stems.add(match.group(1))
    return sorted(stems, key=int)


def _summary_from_file(path: Path) -> dict | None:
    data = path.read_bytes()
    summary = parse_save_summary(data)
    if summary is None:
        for _, chunk in decompress_all_blocks(data):
            summary = parse_save_summary(chunk)
            if summary is not None:
                break
    if summary is None:
        return None
    return {"save": path.stem, "source": path.name, **asdict(summary)}


def summarize_save(stem: str, saves_dir: Path) -> dict | None:
    header_path = saves_dir / f"{stem}.TwoWorldsIISave_header"
    if header_path.exists():
        row = _summary_from_file(header_path)
        if row is not None:
            return row

    save_path = saves_dir / f"{stem}.TwoWorldsIISave"
    if save_path.exists():
        row = _summary_from_file(save_path)
        if row is not None:
            return row

    return None


def collect_summaries(path: Path) -> list[dict]:
    if path.is_dir():
        rows = []
        for stem in find_save_stems(path):
            row = summarize_save(stem, path)
            if row is not None:
                rows.append(row)
        return rows

    row = _summary_from_file(path)
    return [row] if row is not None else []


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the save summary (location, play time, active mission, "
            "level, experience) from a save/header file or a directory of them"
        )
    )
    parser.add_argument(
        "path", type=Path, help="A single save/header file, or a directory of them"
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full results as JSON"
    )
    args = parser.parse_args()

    rows = collect_summaries(args.path)
    print(f"Found {len(rows)} save summar{'y' if len(rows) == 1 else 'ies'}")
    for row in rows[:20]:
        print(
            f"  {row['save']}: mission={row['active_mission']!r} "
            f"location={row['location']!r} level={row['level']} xp={row['experience']}"
        )
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Wrote full results to {args.json_out}")


if __name__ == "__main__":
    main()
