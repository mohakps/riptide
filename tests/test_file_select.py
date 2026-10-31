import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide import __version__
from riptide.core.file_select import (
    add_to_selection,
    common_prefix,
    complete,
    format_browser_row,
    format_file_row,
    format_mtime,
    list_browser_entries,
    parse_dropped_text,
    total_size,
)


def test_parse_typed_name(tmp_path):
    (tmp_path / "report.pdf").write_bytes(b"hello")
    assert parse_dropped_text("report.pdf", tmp_path) == [tmp_path / "report.pdf"]


def test_parse_dropped_quoted_paths_with_spaces(tmp_path):
    target = tmp_path / "my file.txt"
    target.write_bytes(b"x")
    other = tmp_path / "other.txt"
    other.write_bytes(b"y")
    result = parse_dropped_text(f'"{target}" "{other}"', tmp_path)
    assert result == [target, other]


def test_parse_windows_path_string_is_not_crash(tmp_path):
    # A Windows path cannot resolve on Linux, so it is ignored, not an error.
    assert parse_dropped_text(r'"C:\Users\friend\file.txt"', tmp_path) == []


def test_dedupe_and_total_size(tmp_path):
    a = tmp_path / "a.txt"
    a.write_bytes(b"12345")
    selection = add_to_selection([], [a, a])
    assert selection == [a]
    assert total_size(selection) == 5


def test_complete(tmp_path):
    (tmp_path / "demo.mp4").write_text("x")
    (tmp_path / "notes.txt").write_text("x")
    assert complete("de", tmp_path) == ["demo.mp4"]
    assert complete("n", tmp_path) == ["notes.txt"]
    assert complete("zzz", tmp_path) == []


def test_complete_absolute_path_keeps_directory(tmp_path):
    (tmp_path / "document.pdf").write_text("x")
    (tmp_path / "other.txt").write_text("x")
    # Old bug: this returned ["document.pdf"], losing the directory.
    assert complete(str(tmp_path / "doc"), tmp_path) == [str(tmp_path / "document.pdf")]
    assert complete(str(tmp_path) + "/", tmp_path) == [
        str(tmp_path / "document.pdf"),
        str(tmp_path / "other.txt"),
    ]


def test_common_prefix():
    assert common_prefix(["/a/doc1", "/a/doc2"]) == "/a/doc"
    assert common_prefix(["abc", "abd"]) == "ab"
    assert common_prefix([]) == ""


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
