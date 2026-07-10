import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.scan_saves", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_scan_saves_reports_only_small_regions_and_ignores_headers(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(b"HEADER" + b"OLDVAL" + b"FOOTER")
    (saves_dir / "000001.TwoWorldsIISave").write_bytes(b"HEADER" + b"NEWVAL" + b"FOOTER")
    (saves_dir / "000002.TwoWorldsIISave").write_bytes(b"HEADER" + b"X" * 1000 + b"FOOTER")
    (saves_dir / "000000.TwoWorldsIISave_header").write_bytes(b"ignored header file")

    json_out = tmp_path / "scan.json"
    result = _run(
        str(saves_dir), "--max-region-size", "64", "--json", str(json_out), cwd=SCRIPT_DIR
    )

    assert result.returncode == 0, result.stderr
    assert "Found 1 small region(s)" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["save_a"] == 0
    assert rows[0]["save_b"] == 1
    assert bytes.fromhex(rows[0]["a_bytes"]) == b"OLD"
    assert bytes.fromhex(rows[0]["b_bytes"]) == b"NEW"


def test_scan_saves_skips_pairs_with_no_changes(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(b"IDENTICAL")
    (saves_dir / "000001.TwoWorldsIISave").write_bytes(b"IDENTICAL")

    result = _run(str(saves_dir), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 0 small region(s)" in result.stdout
