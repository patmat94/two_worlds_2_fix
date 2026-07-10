import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.diff_saves", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_diff_saves_reports_changed_region(tmp_path):
    save_a = tmp_path / "a.save"
    save_b = tmp_path / "b.save"
    save_a.write_bytes(b"HEADER" + b"OLDVALUE" + b"FOOTER")
    save_b.write_bytes(b"HEADER" + b"NEWVAL!!" + b"FOOTER")
    json_out = tmp_path / "diff.json"

    result = _run(str(save_a), str(save_b), "--json", str(json_out), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 1 changed region(s)" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert rows[0]["op"] == "replace"
    assert bytes.fromhex(rows[0]["a_bytes"]) == b"OLDVALUE"
    assert bytes.fromhex(rows[0]["b_bytes"]) == b"NEWVAL!!"


def test_diff_saves_min_size_filters_small_regions(tmp_path):
    save_a = tmp_path / "a.save"
    save_b = tmp_path / "b.save"
    save_a.write_bytes(b"HEADER" + b"X" + b"FOOTER")
    save_b.write_bytes(b"HEADER" + b"Y" + b"FOOTER")

    result = _run(str(save_a), str(save_b), "--min-size", "4", cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 0 changed region(s)" in result.stdout


def test_diff_saves_min_size_keeps_exact_boundary_region(tmp_path):
    save_a = tmp_path / "a.save"
    save_b = tmp_path / "b.save"
    save_a.write_bytes(b"HEADER" + b"WXYZ" + b"FOOTER")
    save_b.write_bytes(b"HEADER" + b"ABCD" + b"FOOTER")

    result = _run(str(save_a), str(save_b), "--min-size", "4", cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 1 changed region(s)" in result.stdout
