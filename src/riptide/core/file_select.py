"""File selection: typed names, Tab completion, and drag-and-drop paste.

Drag and drop in a terminal is not a drop event. Most terminals paste the
path text into the input, so both methods feed the same Selected list.
This module is deliberately stdlib-only so it is easy to test.
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


def _split_pasted(text: str) -> list[str]:
    """Split pasted text, honouring quotes, Windows paths, and spaces."""
    text = text.strip()
    if not text:
        return []
    # shlex with posix=False keeps Windows backslashes intact.
    try:
        parts = shlex.split(text, posix=False)
    except ValueError:
        parts = re.findall(r'"([^"]+)"|\'([^\']+)\'|(\S+)', text)
        parts = [a or b or c for a, b, c in parts]  # type: ignore[assignment]
    cleaned: list[str] = []
    for part in parts:
        part = part.strip().strip(",")
        if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'":
            part = part[1:-1]
        if part:
            cleaned.append(part)
    return cleaned


def _resolve(token: str, cwd: Path) -> Path | None:
    token = token.strip()
    if not token:
        return None
    # Windows absolute path, e.g. C:\Users\... or C:/Users/...
    if re.match(r"^[A-Za-z]:[\\/]", token):
        candidate = Path(token)
    else:
        candidate = Path(token).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
    try:
        if candidate.is_file():
            return candidate
    except OSError:
        return None
    return None


def parse_dropped_text(text: str, cwd: Path) -> list[Path]:
    """Parse typed or dropped text into existing files, deduped, in order."""
    seen: set[Path] = set()
    out: list[Path] = []
    for token in _split_pasted(text):
        resolved = _resolve(token, cwd)
        if resolved is not None and resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def add_to_selection(selection: list[Path], new: list[Path]) -> list[Path]:
    seen = set(selection)
    for path in new:
        if path not in seen:
            seen.add(path)
            selection.append(path)
    return selection


def complete(prefix: str, cwd: Path) -> list[str]:
    """Tab completion candidates for a prefix, relative or absolute.

    Absolute paths used to be broken: the old code returned only
    the bare entry name for an absolute prefix, so completing
    ``/home/user/doc`` replaced the input with ``document.pdf``
    and lost the directory. Now the returned candidate keeps
    the full absolute prefix, including a trailing slash when
    the prefix itself ends in a separator.
    """
    prefix = prefix.strip()
    if not prefix:
        return []
    if prefix.startswith("~"):
        prefix = str(Path(prefix).expanduser())
    sep = "\\" if "\\" in prefix else "/"
    # Trailing separator: complete inside that directory.
    if prefix.endswith(("/", "\\")):
        directory = Path(prefix).expanduser()
        if re.match(r"^[A-Za-z]:[\\/]", prefix):
            directory = Path(prefix)
        stem = ""
        base = prefix
        if not directory.is_dir():
            return []
        return [f"{base}{e.name}{'/' if e.is_dir() else ''}"
                for e in sorted(directory.iterdir(), key=lambda p: p.name.lower())]
    raw = Path(prefix)
    is_win_abs = bool(re.match(r"^[A-Za-z]:[\\/]", prefix))
    if raw.is_absolute() or is_win_abs:
        directory = raw.parent
        stem = raw.name
        # Keep the absolute directory in the candidate, e.g.
        # /home/user/do -> /home/user/document.pdf
        base = str(directory)
        if not base.endswith(("/", "\\")):
            base += sep
    else:
        if "/" in prefix or "\\" in prefix:
            directory = cwd / raw.parent
            stem = raw.name
            base = str(raw.parent).replace("\\", "/") + "/"
        else:
            directory = cwd
            stem = prefix
            base = ""
    try:
        directory = directory.expanduser()
    except Exception:
        pass
    if not directory.is_dir():
        return []
    out: list[str] = []
    for entry in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.lower().startswith(stem.lower()):
            suffix = "/" if entry.is_dir() else ""
            out.append(f"{base}{entry.name}{suffix}")
    return out


def common_prefix(candidates: list[str]) -> str:
    """Longest common prefix of all candidates, or '' if none."""
    if not candidates:
        return ""
    prefix = candidates[0]
    for cand in candidates[1:]:
        while not cand.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def list_browser_entries(directory: Path) -> list[Path]:
    """File-manager entries for a directory: folders first, then
    files, each group alphabetical. Hidden entries are kept, as
    the old file list did."""
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
    old name / size / mtime format."""
    if path.is_dir():
        return f"📁 {path.name}/", "", ""
    name, size, mtime = format_file_row(path)
    return name, size, mtime


def list_cwd_files(cwd: Path) -> list[Path]:
    if not cwd.is_dir():
        return []
    return sorted(
        (p for p in cwd.iterdir() if p.is_file()),
        key=lambda p: p.name.lower(),
    )
