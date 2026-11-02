"""File selection: the file manager listing and display.

Files are selected only from the file manager, with Space, and
sent with Enter. This module is deliberately stdlib-only so it
is easy to test.
"""
from __future__ import annotations
from datetime import datetime
import re
import shlex
from pathlib import Path


def format_bytes(n: int) -> str:
    n = int(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n = n / 1024  # type: ignore[assignment]
    return f"{n} B"


def total_size(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            pass
    return total

def format_mtime(mtime: float) -> str:
    """Format modification timestamp as strictly dd-mm-yyyy hh:mm am/pm in lowercase."""
    dt = datetime.fromtimestamp(mtime)
    return dt.strftime("%d-%m-%Y %I:%M %p").lower()


def format_file_row(path: Path) -> tuple[str, str, str]:
    """Return (filename, size_str, mtime_str) for displaying in file tables."""
    stat = path.stat()
    return path.name, format_bytes(stat.st_size), format_mtime(stat.st_mtime)








def add_to_selection(selection: list[Path], new: list[Path]) -> list[Path]:
    seen = set(selection)
    for path in new:
        if path not in seen:
            seen.add(path)
            selection.append(path)
    return selection






def list_browser_entries(directory: Path) -> list[Path]:
    """File-manager entries for a directory: folders first, then
    files, each group alphabetical. Hidden entries are kept."""
    if not directory.is_dir():
        return []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    folders = sorted((p for p in entries if p.is_dir()), key=lambda p: p.name.lower())
    files = sorted((p for p in entries if p.is_file()), key=lambda p: p.name.lower())
    return folders + files


def format_browser_row(path: Path) -> tuple[str, str, str]:
    """Display row for the file manager: (display, size, mtime).

    Folders get a folder icon and a trailing slash, and no size
    or date: ``📁 docs/`` with empty size/mtime. Files keep the
    name / size / mtime format."""
    if path.is_dir():
        return f"📁 {path.name}/", "", ""
    name, size, mtime = format_file_row(path)
    return name, size, mtime


