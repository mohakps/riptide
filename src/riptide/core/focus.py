"""Arrow-key focus navigation.

Root cause of the reported bug: Textual moves focus with Tab by
default. Plain Buttons in a Vertical container do not move focus on
Up/Down, and no widget was focused on mount, so pressing an arrow key
did nothing visible at all.

These helpers make Up/Down work explicitly, in DOM order, wrapping
around, on every screen. They are deliberately small and unit-testable:
they only need a screen-like object with ``focused``, ``query`` and
``app.set_focus``.
"""
from __future__ import annotations


def focusable_widgets(screen):
    """Return focusable widgets in DOM order, skipping disabled ones."""
    try:
        widgets = list(screen.query("OptionList, ListView, Button, Input"))
    except Exception:
        return []
    result = []
    for widget in widgets:
        try:
            if getattr(widget, "disabled", False):
                continue
        except Exception:
            pass
        result.append(widget)
    return result


def focus_first(screen) -> bool:
    """Focus the first focusable widget. Return True if one was focused."""
    widgets = focusable_widgets(screen)
    if not widgets:
        return False
    _set_focus(screen, widgets[0])
    return True


def move_focus(screen, direction: int) -> bool:
    """Move focus by direction (+1 down, -1 up), wrapping. Return True if moved."""
    widgets = focusable_widgets(screen)
    if not widgets:
        return False
    focused = getattr(screen, "focused", None)
    if focused not in widgets:
        target = widgets[0] if direction >= 0 else widgets[-1]
        _set_focus(screen, target)
        return True
    index = widgets.index(focused)
    target = widgets[(index + direction) % len(widgets)]
    _set_focus(screen, target)
    return True


def handle_arrow_key(screen, key: str) -> bool:
    """Handle an Up/Down key for a screen. Return True if handled."""
    try:
        from textual.widgets import OptionList, ListView
        focused = getattr(screen, "focused", None)
        if isinstance(focused, (OptionList, ListView)):
            return False
    except Exception:
        pass
    if key == "down":
        return move_focus(screen, +1)
    if key == "up":
        return move_focus(screen, -1)
    return False


def _set_focus(screen, widget) -> None:
    app = getattr(screen, "app", None)
    set_focus = getattr(app, "set_focus", None) if app is not None else None
    if callable(set_focus):
        set_focus(widget)
    else:
        focus = getattr(widget, "focus", None)
        if callable(focus):
            focus()
