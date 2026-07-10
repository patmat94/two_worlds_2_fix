import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.save_summary", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _build_summary_block(text: str) -> bytes:
    return struct.pack("<I", len(text)) + text.encode("utf-16-le")


SAMPLE_TEXT = (
    "Miejsce: Test Place\nCzas gry: 01:00\nAktywna misja: Test Quest\n"
    "Poziom: 5\nPD: 100/200"
)


def test_save_summary_reads_header_file_directly(tmp_path):
    header_path = tmp_path / "000000.TwoWorldsIISave_header"
    header_path.write_bytes(b"pad" + _build_summary_block(SAMPLE_TEXT))
    json_out = tmp_path / "out.json"

    result = _run(str(header_path), "--json", str(json_out), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 1 save summary" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert rows[0]["active_mission"] == "Test Quest"
    assert rows[0]["location"] == "Test Place"


def test_save_summary_decompresses_main_save_file_when_needed(tmp_path):
    save_path = tmp_path / "000000.TwoWorldsIISave"
    compressed = zlib.compress(_build_summary_block(SAMPLE_TEXT))
    save_path.write_bytes(b"uncompressed prefix" + compressed)

    result = _run(str(save_path), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 1 save summary" in result.stdout


def test_save_summary_directory_prefers_header_over_main_file(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    (saves_dir / "000000.TwoWorldsIISave_header").write_bytes(
        b"pad" + _build_summary_block(SAMPLE_TEXT)
    )
    # Main file has no valid summary/zlib data at all - if the CLI fell back
    # to it instead of using the header, it would find nothing for this save.
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(b"not a valid save file")

    json_out = tmp_path / "out.json"
    result = _run(str(saves_dir), "--json", str(json_out), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["source"] == "000000.TwoWorldsIISave_header"
    assert rows[0]["active_mission"] == "Test Quest"
