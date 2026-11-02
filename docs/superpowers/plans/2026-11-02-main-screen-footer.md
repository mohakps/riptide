# Main Screen Footer Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the main menu screen footer to match the docked horizontal footer bar used on other screens.

**Architecture:** Replace the inline `Static(..., classes="keymap-bar")` widget in `MenuScreen` with a root-level `Horizontal(id="footer_bar")` containing three `Label` widgets (`.keymap-item`) representing `[↑/↓] Navigate`, `[Enter] Select`, and `[Esc] Quit`. Styling reuses existing global CSS in `src/riptide/theme.py`.

**Tech Stack:** Python 3.11+, Textual 0.86+, pytest, pytest-asyncio, uv

## Global Constraints

- True terminal transparency: no background fills (`background: transparent`).
- Consistent footer structure: `Horizontal(..., id="footer_bar")` docked to bottom.
- Key item styling: `[bold #E8E8E8]\[KEY][/] [dim #FFFFFF]LABEL[/]`.
- Key alignments: First item has `classes="keymap-item keymap-left"`, middle item `classes="keymap-item"`, last item `classes="keymap-item keymap-right"`.
- Keyboard bindings: `MenuScreen.on_key` must retain both `escape` and `q` exits.
- No regressions: all 74+ test cases must pass.

---

### Task 1: Update MenuScreen Unit Tests for Footer Redesign

**Files:**
- Modify: `tests/test_menu.py:11-26`

**Interfaces:**
- Consumes: `DummyApp` from `tests/test_menu.py`
- Produces: Test assertions validating `#footer_bar`, `.keymap-item` elements, and absence of `.keymap-bar`.

- [ ] **Step 1: Write the failing test assertions in `tests/test_menu.py`**

Update `test_menu_screen_composition` in `tests/test_menu.py` to assert that `#footer_bar` is present with 3 `.keymap-item` labels and that `.keymap-bar` is absent:

```python
@pytest.mark.asyncio
async def test_menu_screen_composition():
    app = DummyApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, MenuScreen)
        # Check version is rendered
        labels = [node.render().plain for node in screen.query("Static, Label")]
        full_text = " ".join(labels)
        assert f"v{__version__}" in full_text
        assert "Zero cloud storage" in full_text
        # Ensure Exit button is removed
        assert len(screen.query("#exit")) == 0
        # Ensure option list exists
        assert len(screen.query("#menu_list")) == 1
        # Ensure new footer_bar exists with 3 keymap-items
        footer = screen.query_one("#footer_bar")
        footer_items = footer.query(".keymap-item")
        assert len(footer_items) == 3
        footer_text = " ".join(node.render().plain for node in footer_items)
        assert "[↑/↓]" in footer_text
        assert "Navigate" in footer_text
        assert "[Enter]" in footer_text
        assert "Select" in footer_text
        assert "[Esc]" in footer_text
        assert "Quit" in footer_text
        # Ensure old keymap-bar class is gone
        assert len(screen.query(".keymap-bar")) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_menu.py::test_menu_screen_composition
```
Expected: FAIL with `NoMatches: No nodes match '#footer_bar'`

- [ ] **Step 3: Commit test change**

```bash
git add tests/test_menu.py
git commit -m "test: add assertions for main screen footer bar"
```

---

### Task 2: Implement Docked Footer on MenuScreen

**Files:**
- Modify: `src/riptide/screens/menu.py:1-32`

**Interfaces:**
- Consumes: `Horizontal` from `textual.containers`, `Label` from `textual.widgets`, `#footer_bar` CSS from `src/riptide/theme.py`.
- Produces: `MenuScreen.compose` yielding `Horizontal(..., id="footer_bar")`.

- [ ] **Step 1: Update `src/riptide/screens/menu.py`**

Import `Horizontal` from `textual.containers` and `Label` from `textual.widgets`. Remove `Static(..., classes="keymap-bar")` from inside `Vertical(...)`, and yield `Horizontal(..., id="footer_bar")` after `Vertical(...)`:

```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from .. import __version__
from ..core.focus import focus_first, handle_arrow_key
from ..theme import HEADER_BANNER, TAGLINES


class MenuScreen(Screen):
    def compose(self) -> ComposeResult:
        options = [
            Option("❯  Create Server      Wait for incoming session (Requires Port Forwarding)", id="create"),
            Option("   Join Server        Dial out to peer (Required for CGNAT)", id="join"),
        ]
        yield Vertical(
            Static(HEADER_BANNER, classes="header"),
            Static(f"v{__version__}", classes="version-tag"),
            Static(TAGLINES["home"], classes="subheader"),
            OptionList(*options, id="menu_list"),
        )
        yield Horizontal(
            Label(r"[bold #E8E8E8]\[↑/↓][/] [dim #FFFFFF]Navigate[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Select[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Esc][/] [dim #FFFFFF]Quit[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
        )
```

- [ ] **Step 2: Run test to verify it passes**

Run:
```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_menu.py
```
Expected: PASS (all 3 tests pass)

- [ ] **Step 3: Run full test suite for regression verification**

Run:
```bash
uv run --with pytest --with pytest-asyncio pytest
```
Expected: PASS (all 74 tests pass)

- [ ] **Step 4: Commit implementation**

```bash
git add src/riptide/screens/menu.py
git commit -m "feat: redesign main screen footer to match other screens"
```
