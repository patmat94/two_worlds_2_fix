import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.entity_property", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _build_property_bag(pairs: list[tuple[str, str]]) -> bytes:
    out = struct.pack("<I", len(pairs))
    for key, value in pairs:
        out += struct.pack("<I", len(key)) + key.encode("ascii")
        out += struct.pack("<I", len(value)) + value.encode("ascii")
    return out


def test_entity_property_finds_value_near_entity_name(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    payload = (
        b"junk"
        + b"MY_NPC_NAME"
        + b"transform data here"
        + _build_property_bag([("PCQ", "100"), ("PSDN", "0")])
        + b"more junk"
    )
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(zlib.compress(payload))

    json_out = tmp_path / "out.json"
    result = _run(
        str(saves_dir),
        "--entity",
        "MY_NPC_NAME",
        "--prop",
        "PCQ",
        "--json",
        str(json_out),
        cwd=SCRIPT_DIR,
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert rows[0]["save"] == 0
    assert rows[0]["PCQ"] == "100"


def test_entity_property_skips_occurrences_too_far_from_a_property_bag(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    payload = (
        b"MY_NPC_NAME"  # this occurrence has no nearby property bag
        + b"x" * 5000
        + b"MY_NPC_NAME"  # this occurrence does
        + _build_property_bag([("PCQ", "200")])
    )
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(zlib.compress(payload))

    result = _run(str(saves_dir), "--entity", "MY_NPC_NAME", "--prop", "PCQ", cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "PCQ=200" in result.stdout


def test_entity_property_reports_missing_when_not_found(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(zlib.compress(b"nothing here"))

    result = _run(str(saves_dir), "--entity", "MY_NPC_NAME", "--prop", "PCQ", cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "PCQ=None" in result.stdout
