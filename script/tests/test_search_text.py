import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.search_text", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_search_text_finds_ascii_and_utf16(tmp_path):
    data = (
        b"padding"
        + "Casbrim".encode("ascii")
        + b"padding"
        + b"\x00\x00"
        + "Casbrim".encode("utf-16-le")
        + b"\x00\x00"
    )
    target = tmp_path / "sample.bin"
    target.write_bytes(data)
    json_out = tmp_path / "matches.json"

    result = _run(str(target), "--term", "Casbrim", "--json", str(json_out), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Found 2 match(es)" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    encodings = {row["encoding"] for row in rows}
    assert encodings == {"ascii", "utf-16-le"}
