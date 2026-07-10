"""CLI: track a named entity's property-bag value across a save history.

Two Worlds II save files carry per-entity "property bags" near each named
entity (e.g. an NPC like `DLC3_CHANCELLOR_CASBRIM`): a
`[count][key][value]...` block of small string key-value pairs (`PCQ`,
`PSDN`, `PQUS`, ...). An entity's name can appear multiple times in a save
(references, other tables); only some occurrences are immediately followed
by a property bag, so every occurrence is tried in turn within a bounded
search window until one yields the requested property.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tw2tools.wd_format import decompress_all_blocks, parse_property_bags

SAVE_NAME_RE = re.compile(r"^(\d+)\.TwoWorldsIISave$")


def find_save_sequence(saves_dir: Path) -> list[tuple[int, Path]]:
    saves = []
    for path in saves_dir.iterdir():
        match = SAVE_NAME_RE.match(path.name)
        if match:
            saves.append((int(match.group(1)), path))
    return sorted(saves, key=lambda item: item[0])


def find_entity_property(
    data: bytes, entity_name: str, prop_key: str, search_window: int = 4000
) -> str | None:
    needle = entity_name.encode("ascii")
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx == -1:
            return None
        window = data[idx : idx + search_window]
        for bag in parse_property_bags(window):
            if prop_key in bag.properties:
                return bag.properties[prop_key]
        start = idx + 1


def collect_entity_property_timeline(
    saves_dir: Path, entity_name: str, prop_key: str
) -> list[dict]:
    rows: list[dict] = []
    for index, path in find_save_sequence(saves_dir):
        data = path.read_bytes()
        value = None
        for _, chunk in decompress_all_blocks(data):
            value = find_entity_property(chunk, entity_name, prop_key)
            if value is not None:
                break
        rows.append({"save": index, prop_key: value})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Track a named entity's property-bag value across a save-history directory"
    )
    parser.add_argument(
        "saves_dir", type=Path, help="Directory containing NNNNNN.TwoWorldsIISave files"
    )
    parser.add_argument("--entity", required=True, help="Entity name to search for (e.g. DLC3_CHANCELLOR_CASBRIM)")
    parser.add_argument("--prop", required=True, help="Property key to read (e.g. PCQ)")
    parser.add_argument(
        "--json", dest="json_out", type=Path, default=None, help="Write full results as JSON"
    )
    args = parser.parse_args()

    rows = collect_entity_property_timeline(args.saves_dir, args.entity, args.prop)
    print(f"Checked {len(rows)} save(s) for {args.entity}.{args.prop}")
    for row in rows[:20]:
        print(f"  save {row['save']:06d}: {args.prop}={row[args.prop]}")
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more (use --json to see all)")

    if args.json_out:
        args.json_out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Wrote full results to {args.json_out}")


if __name__ == "__main__":
    main()
