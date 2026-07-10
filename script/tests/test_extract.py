import subprocess
import sys
import zlib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.extract", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_extract_writes_chunk_files(tmp_path):
    archive = tmp_path / "sample.wd"
    first = zlib.compress(b"first block payload")
    second = zlib.compress(b"second block payload")
    archive.write_bytes(first + second)
    out_dir = tmp_path / "out"

    result = _run(str(archive), "-o", str(out_dir), cwd=SCRIPT_DIR)

    assert result.returncode == 0, result.stderr
    assert "Extracted 2 block(s)" in result.stdout
    chunk_files = sorted(out_dir.glob("sample_chunk_*.bin"))
    assert len(chunk_files) == 2
    assert chunk_files[0].read_bytes() == b"first block payload"
    assert chunk_files[1].read_bytes() == b"second block payload"
