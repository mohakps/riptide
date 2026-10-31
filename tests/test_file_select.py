import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.file_select import add_to_selection, complete, parse_dropped_text, total_size


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
