import json
import struct
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tw2tools.list_entries", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _build_entry(path, type_id, flags, word1, word2, word3, word4, marker=b"$"):
    footer = struct.pack("<HHIIII", type_id, flags, word1, word2, word3, word4)
    return marker + path.encode("ascii") + b"\x01\x00" + footer


def test_list_entries_filters_by_suffix(tmp_path):
    blob = _build_entry("Scripts\\Foo.eco", 1, 0, 1, 2, 3, 4) + _build_entry(
        "Textures\\Bar.dds", 2, 0, 5, 6, 7, 8
    )
    chunk_file = tmp_path / "chunk_00000000.bin"
    chunk_file.write_bytes(blob)
    json_out = tmp_path / "entries.json"

    result = _run(
        str(chunk_file), "--filter", ".eco", "--json", str(json_out), cwd=SCRIPT_DIR
    )

    assert result.returncode == 0, result.stderr
    assert "Found 1 entry" in result.stdout
    rows = json.loads(json_out.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["path"] == "Scripts\\Foo.eco"
    assert rows[0]["source_chunk"] == "chunk_00000000.bin"
