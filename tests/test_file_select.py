import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide import __version__
from riptide.core.file_select import (
    add_to_selection,
    format_browser_row,
    format_file_row,
    format_mtime,
    list_browser_entries,
    total_size,
)








def test_dedupe_and_total_size(tmp_path):
    a = tmp_path / "a.txt"
    a.write_bytes(b"12345")
    selection = add_to_selection([], [a, a])
    assert selection == [a]
    assert total_size(selection) == 5








def test_browser_entries_folders_first_no_size_date(tmp_path):
    (tmp_path / "zfile.txt").write_text("x")
    (tmp_path / "afolder").mkdir()
    (tmp_path / "bfile.txt").write_text("x")
    entries = list_browser_entries(tmp_path)
    assert entries[0].name == "afolder"
    assert entries[0].is_dir()
    display, size, mtime = format_browser_row(tmp_path / "afolder")
    assert display == "📁 afolder/"
    assert size == "" and mtime == ""
    display, size, mtime = format_browser_row(tmp_path / "zfile.txt")
    assert display == "zfile.txt"
    assert size and mtime

def test_dynamic_version_matches_pyproject():
    import tomllib
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    assert __version__ == data["project"]["version"]


def test_format_mtime_exact_format():
    # Example: 2026-10-31 14:15:00 UTC/local
    from datetime import datetime
    dt = datetime(2026, 10, 31, 14, 15, 0)
    ts = dt.timestamp()
    assert format_mtime(ts) == "31-10-2026 02:15 pm"

    dt_am = datetime(2026, 1, 5, 9, 7, 0)
    assert format_mtime(dt_am.timestamp()) == "05-01-2026 09:07 am"


def test_format_file_row(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    from datetime import datetime
    import os
    dt = datetime(2026, 5, 12, 16, 30, 0)
    os.utime(f, (dt.timestamp(), dt.timestamp()))

    name, size_str, mtime_str = format_file_row(f)
    assert name == "hello.txt"
    assert size_str == "11 B"
    assert mtime_str == "12-05-2026 04:30 pm"
