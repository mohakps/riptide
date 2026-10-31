from pathlib import Path
from riptide.core.file_select import format_file_row
from riptide.screens.session_screen import SessionScreen
from riptide.theme import TAGLINES


def test_file_row_structure(tmp_path):
    p = tmp_path / "testfile.dat"
    p.write_bytes(b"x" * 2048)
    name, size, mtime = format_file_row(p)
    assert name == "testfile.dat"
    assert "KB" in size
    assert "-" in mtime and ("am" in mtime or "pm" in mtime)


def test_session_tagline_present():
    assert "session" in TAGLINES
    assert "encrypted channel" in TAGLINES["session"]
