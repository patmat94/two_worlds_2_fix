import json
import subprocess
import sys
import zlib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.flag_timeline", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_flag_timeline_tracks_presence_across_saves(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(
        zlib.compress(b"nothing interesting here")
    )
    (saves_dir / "000001.TwoWorldsIISave").write_bytes(
        zlib.compress(b"prefix" + b"MyFlagTriggered" + b"suffix")
    )

    json_out = tmp_path / "timeline.json"
    result = _run(
        str(saves_dir), "--name", "MyFlagTriggered", "--json", str(json_out), cwd=SCRIPT_DIR
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert rows[0]["save"] == 0
    assert rows[0]["MyFlagTriggered"] is None
    assert rows[1]["save"] == 1
    assert rows[1]["MyFlagTriggered"] is not None


def test_flag_timeline_tracks_multiple_names(tmp_path):
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    (saves_dir / "000000.TwoWorldsIISave").write_bytes(
        zlib.compress(b"has" + b"FlagA" + b"only")
    )

    result = _run(str(saves_dir), "--name", "FlagA", "--name", "FlagB", cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "FlagA=present" in result.stdout
    assert "FlagB=absent" in result.stdout
