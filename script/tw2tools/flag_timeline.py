"""CLI: track presence of named save-state flags/records across a save history."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tw2tools.wd_format import decompress_all_blocks, search_text_multi

SAVE_NAME_RE = re.compile(r"^(\d+)\.TwoWorldsIISave$")


def find_save_sequence(saves_dir: Path) -> list[tuple[int, Path]]:
    saves = []
    for path in saves_dir.iterdir():
        match = SAVE_NAME_RE.match(path.name)
        if match:
            saves.append((int(match.group(1)), path))
    return sorted(saves, key=lambda item: item[0])


def check_flags(data: bytes, names: list[str]) -> dict[str, int | None]:
    result: dict[str, int | None] = {name: None for name in names}
    for _, chunk in decompress_all_blocks(data):
        for match in search_text_multi(chunk, names):
            if result[match.term] is None:
                result[match.term] = match.offset
    return result


def collect_flag_timeline(saves_dir: Path, names: list[str]) -> list[dict]:
    rows: list[dict] = []
    for index, path in find_save_sequence(saves_dir):
        offsets = check_flags(path.read_bytes(), names)
        rows.append({"save": index, **offsets})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Track presence of named save-state flags across a save-history directory"
    )
    parser.add_argument(
        "saves_dir", type=Path, help="Directory containing NNNNNN.TwoWorldsIISave files"
    )
    parser.add_argument(
        "--name", dest="names", action="append", required=True, help="Flag/record name to track (repeatable)"
    )
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full results as JSON"
    )
    args = parser.parse_args()

    rows = collect_flag_timeline(args.saves_dir, args.names)
    print(f"Checked {len(rows)} save(s) for {len(args.names)} flag(s)")
    for row in rows[:20]:
        status = ", ".join(
            f"{name}={'present' if row[name] is not None else 'absent'}" for name in args.names
        )
        print(f"  save {row['save']:06d}: {status}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full results to {args.json_out}")


if __name__ == "__main__":
    main()
