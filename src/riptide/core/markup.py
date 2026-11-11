"""Escape names before they are inserted into Rich markup strings.

A peer-controlled or local name can contain ``[`` or ``]``, which
Rich would parse as a style tag, or a ``[/]`` that raises a
MarkupError and breaks the render, so a crafted device name, file
name, or host string could hide the real name, spoof a UI message,
or crash a widget. Escaping shows the literal text. Normal names,
with spaces, parentheses, and Unicode, are unchanged.
"""
from __future__ import annotations

from rich.markup import escape


def esc(text: str) -> str:
    """Escape a name (device, host, file, folder, status) for Rich markup."""
    return escape(str(text))
