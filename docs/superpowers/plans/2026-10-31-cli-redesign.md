# Riptide CLI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the Riptide terminal interface into a sleek, transparent, UX-friendly CLI with an ANSI Shadow Block header, dynamic versioning, interactive unordered list navigation, prominent primary actions with footer keymaps, and a columnar file browser with dull timestamps formatted as `dd-mm-yyyy hh:mm am/pm`.

**Architecture:**
- `src/riptide/theme.py`: Replace solid `#1E1E1E`/`#2A2A2A` background fills with `transparent`, remove clunky 3-row button boxes, integrate the 6-line ANSI Shadow Block ASCII art header, and supply a reusable footer keymap styling.
- `src/riptide/__init__.py`: Dynamically resolve project version from `pyproject.toml` (using `tomllib` with fallback to `importlib.metadata`) instead of hardcoding.
- `src/riptide/core/file_select.py`: Implement `format_mtime` (`dd-mm-yyyy hh:mm am/pm`) and tabular row formatting starting with `>` and separate columns for size and date modified in dull font.
- `src/riptide/screens/menu.py`: Implement interactive unordered list navigation with `❯` cursor, ANSI Shadow Block header, dynamic `v{version}` tag, rewritten tagline, and remove the Exit button (mapped to `Esc`/`q`).
- `src/riptide/screens/session_screen.py`: Implement tabular file browser with dull size & date columns, prominent Send action, and `[Esc] Leave Session` in keymap.
- `src/riptide/screens/create.py` & `join.py`: Update past peers, input fields, approval buttons (Allow vs Deny hierarchy), and rewritten taglines.

**Tech Stack:** Python 3.11+, Textual 8.2.8, Rich, tomllib, pytest.

## Global Constraints
- Terminal background must be 100% transparent (`Screen { background: transparent; }`).
- Homepage header must use the 6-line ANSI Shadow Block ASCII art.
- Version string must be dynamically loaded from `pyproject.toml` (variable `__version__`).
- Date format in file browser must strictly be `dd-mm-yyyy hh:mm am/pm` in lowercase (e.g. `31-10-2026 02:15 pm`).
- File rows must start with `> ` on every line, with size and date rendered in dull grey (`#71717A`).
- All 17 existing tests must continue to pass throughout.

---

### Task 1: Version Resolution & File Metadata Formatting

**Files:**
- Modify: `src/riptide/__init__.py`
- Modify: `src/riptide/core/file_select.py`
- Test: `tests/test_file_select.py`

**Interfaces:**
- Consumes: `pyproject.toml`
- Produces:
  - `src.riptide.__version__`: dynamic version string (e.g. `"0.5.0"`)
  - `src.riptide.core.file_select.format_mtime(mtime: float) -> str`: returns `dd-mm-yyyy hh:mm am/pm`
  - `src.riptide.core.file_select.format_file_row(path: Path, width: int = 70) -> tuple[str, str, str]`: returns `(filename, formatted_size, formatted_mtime)`

- [ ] **Step 1: Write failing tests for format_mtime and dynamic versioning**

Add to `tests/test_file_select.py`:
```python
from datetime import datetime
from pathlib import Path
import riptide
from riptide.core.file_select import format_mtime, format_file_row

def test_dynamic_version_matches_pyproject():
    import tomllib
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert riptide.__version__ == data["project"]["version"]

def test_format_mtime_exact_format():
    dt = datetime(2026, 10, 31, 14, 25)
    ts = dt.timestamp()
    formatted = format_mtime(ts)
    assert formatted == "31-10-2026 02:25 pm"

    dt_am = datetime(2026, 5, 4, 9, 5)
    ts_am = dt_am.timestamp()
    assert format_mtime(ts_am) == "04-05-2026 09:05 am"

def test_format_file_row(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello world")
    name, size_str, mtime_str = format_file_row(f)
    assert name == "sample.txt"
    assert "B" in size_str
    assert "-" in mtime_str and ("am" in mtime_str or "pm" in mtime_str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_file_select.py -k "test_format_mtime"`
Expected: FAIL with `ImportError: cannot import name 'format_mtime'`

- [ ] **Step 3: Implement dynamic version in `src/riptide/__init__.py` and metadata formatting in `src/riptide/core/file_select.py`**

In `src/riptide/__init__.py`:
```python
"""Riptide: direct, encrypted PC-to-PC file transfer in the terminal."""
from __future__ import annotations

from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

def _load_version() -> str:
    try:
        from importlib.metadata import version
        return version("riptide")
    except Exception:
        pass
    try:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return str(data.get("project", {}).get("version", "0.5.0"))
    except Exception:
        pass
    return "0.5.0"

__version__ = _load_version()
__all__ = ["__version__"]
```

In `src/riptide/core/file_select.py`:
```python
from datetime import datetime

def format_mtime(mtime: float) -> str:
    """Format modification time as dd-mm-yyyy hh:mm am/pm in lowercase."""
    dt = datetime.fromtimestamp(mtime)
    return dt.strftime("%d-%m-%Y %I:%M %p").lower()

def format_file_row(path: Path) -> tuple[str, str, str]:
    """Return (filename, formatted_size, formatted_mtime) for a path."""
    try:
        stat = path.stat()
        size_str = format_bytes(stat.st_size)
        mtime_str = format_mtime(stat.st_mtime)
    except Exception:
        size_str = "-"
        mtime_str = "-"
    return path.name, size_str, mtime_str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_file_select.py`
Expected: PASS (all tests in test_file_select.py passing)

- [ ] **Step 5: Commit changes**

```bash
git add src/riptide/__init__.py src/riptide/core/file_select.py tests/test_file_select.py
git commit -m "feat: add dynamic versioning and dd-mm-yyyy hh:mm am/pm file metadata formatting"
```

---

### Task 2: Theme Transparency, ANSI Shadow Block Header & Keymap Bar

**Files:**
- Modify: `src/riptide/theme.py`
- Modify: `assets/trident.txt`
- Test: `tests/test_theme.py` (new test)

**Interfaces:**
- Produces:
  - `src.riptide.theme.HEADER_BANNER`: ANSI Shadow Block art string
  - `src.riptide.theme.HEADER_LINES`: ANSI art lines
  - `src.riptide.theme.TAGLINES`: dictionary of rewritten screen subheaders/taglines
  - `src.riptide.theme.CSS`: updated transparent CSS rules

- [ ] **Step 1: Write test for theme constants and transparent CSS**

Create `tests/test_theme.py`:
```python
from riptide.theme import CSS, HEADER_BANNER, TAGLINES

def test_css_is_transparent():
    assert "background: transparent" in CSS
    assert "#1E1E1E" not in CSS  # no solid dark fill on screen

def test_ansi_header_present():
    assert "██████╗" in HEADER_BANNER
    assert "RIPTIDE" in TAGLINES["home"] or "file transfer" in TAGLINES["home"]

def test_screen_taglines_defined():
    for key in ("home", "create", "join", "session", "setup"):
        assert key in TAGLINES
        assert len(TAGLINES[key]) > 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_theme.py`
Expected: FAIL with `ImportError` or assertion failure

- [ ] **Step 3: Update `src/riptide/theme.py` and `assets/trident.txt`**

In `src/riptide/theme.py`:
```python
"""Theme constants. Pure terminal transparency, coral accent, muted metadata."""

BACKGROUND = "transparent"
SURFACE = "transparent"
ACCENT = "#FF6B6B"
TEXT = "#E8E8E8"
DIM = "#71717A"
SUCCESS = "#78DC8C"
WARNING = "#FFD166"
ERROR = "#FF6B6B"

HEADER_BANNER = """\
██████╗ ██╗██████╗ ████████╗██╗██████╗ ███████╗
██╔══██╗██║██╔══██╗╚══██╔══╝██║██╔══██╗██╔════╝
██████╔╝██║██████╔╝   ██║   ██║██║  ██║█████╗  
██╔══██╗██║██╔═══╝    ██║   ██║██║  ██║██╔══╝  
██║  ██║██║██║        ██║   ██║██████╔╝███████╗
╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   ╚═╝╚═════╝ ╚══════╝\
"""

HEADER_LINES = HEADER_BANNER.splitlines()

TAGLINES = {
    "home": "Direct, encrypted PC-to-PC file transfer · Zero cloud storage, zero intermediate hops",
    "create": "Dial directly to peer · Outbound connection bypasses CGNAT and strict firewalls",
    "join": "Listening for peer handshake · Keep this screen open while creator dials in",
    "session": "Direct end-to-end encrypted channel · Select local files or drop paths to transfer",
    "setup": "Configure local SSH daemon and automated UPnP port forwarding for inbound connections",
}

CSS = """
Screen {
    background: transparent;
    color: #E8E8E8;
    layout: vertical;
    padding: 1 2;
}
Static, Label {
    background: transparent;
    color: #E8E8E8;
}
.header {
    color: #FF6B6B;
    text-style: bold;
    text-align: center;
    padding: 0 0 1 0;
}
.version-tag {
    color: #FF6B6B;
    text-style: bold;
    text-align: center;
}
.subheader {
    color: #71717A;
    text-align: center;
    padding: 0 0 1 0;
}
.screen-title {
    color: #FF6B6B;
    text-style: bold;
    padding: 1 0 0 0;
}
.screen-desc {
    color: #71717A;
    padding: 0 0 1 0;
}
.dim {
    color: #71717A;
}
.accent {
    color: #FF6B6B;
}
.success {
    color: #78DC8C;
}
.warning {
    color: #FFD166;
}
.error {
    color: #FF6B6B;
}
.keymap-bar {
    dock: bottom;
    height: 1;
    color: #71717A;
    background: transparent;
    padding: 0 1;
}
.keymap-key {
    color: #E8E8E8;
    text-style: bold;
}
/* Input fields */
Input {
    border: round #3F3F46;
    background: transparent;
    color: #E8E8E8;
    height: 3;
    padding: 0 1;
    margin: 1 0;
}
Input:focus {
    border: round #FF6B6B;
}
/* Buttons - streamlined, non-bulky */
Button {
    background: transparent;
    color: #E8E8E8;
    border: round #3F3F46;
    height: 3;
    margin: 0 1;
    text-style: bold;
}
Button:focus {
    background: transparent;
    color: #FF6B6B;
    border: round #FF6B6B;
}
Button.primary {
    border: round #FF6B6B;
    color: #FF6B6B;
}
Button.primary:focus {
    background: #FF6B6B;
    color: #121212;
}
Button.allow {
    border: round #78DC8C;
    color: #78DC8C;
}
Button.allow:focus {
    background: #78DC8C;
    color: #121212;
}
Button.deny {
    border: round #71717A;
    color: #71717A;
}
Button.deny:focus {
    border: round #FF6B6B;
    color: #FF6B6B;
}
ProgressBar {
    margin: 1 0;
}
ProgressBar > .bar--bar {
    background: #FF6B6B;
}
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_theme.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/riptide/theme.py assets/trident.txt tests/test_theme.py
git commit -m "style: add ANSI Shadow Block banner, transparent CSS, and screen taglines"
```

---

### Task 3: Interactive Unordered List Navigation & MenuScreen Overhaul

**Files:**
- Modify: `src/riptide/screens/menu.py`
- Modify: `src/riptide/core/focus.py`
- Test: `tests/test_focus.py`
- Test: `tests/test_menu.py` (new test)

**Interfaces:**
- Produces:
  - `src.riptide.screens.menu.MenuScreen`: displays ANSI Shadow Block header, `v{__version__}` pill, tagline, interactive list of options (`Create Server`, `Join Server`), and footer keymap bar (`[↑/↓] Navigate  [Enter] Select  [Esc/q] Quit`).

- [ ] **Step 1: Write test for MenuScreen options and key handling**

Create `tests/test_menu.py`:
```python
from textual.app import App
from riptide.screens.menu import MenuScreen
from riptide import __version__

class DummyApp(App):
    def on_mount(self):
        self.push_screen(MenuScreen())

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
        # Ensure create and join options exist
        assert len(screen.query("#menu_list")) > 0 or len(screen.query(".menu-item")) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_menu.py`
Expected: FAIL

- [ ] **Step 3: Implement interactive list navigation in `src/riptide/screens/menu.py` and update `src/riptide/core/focus.py`**

In `src/riptide/core/focus.py`: ensure `OptionList` or list items are queryable by `focusable_widgets`:
```python
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
```

In `src/riptide/screens/menu.py`:
```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .. import __version__
from ..core.focus import focus_first, handle_arrow_key
from ..theme import HEADER_BANNER, TAGLINES

class MenuScreen(Screen):
    def compose(self) -> ComposeResult:
        options = [
            Option("❯  Create Server      Dial out to peer · bypasses CGNAT", id="create"),
            Option("   Join Server        Wait for incoming session and authorize peer", id="join"),
        ]
        yield Vertical(
            Static(HEADER_BANNER, classes="header"),
            Static(f"v{__version__}", classes="version-tag"),
            Static(TAGLINES["home"], classes="subheader"),
            OptionList(*options, id="menu_list"),
            Static("[↑/↓] Navigate   [Enter] Select   [Esc/q] Quit", classes="keymap-bar"),
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from .create import CreateScreen
        from .join import JoinScreen

        opt_id = event.option_id
        if opt_id == "create":
            self.app.push_screen(CreateScreen())
        elif opt_id == "join":
            self.app.push_screen(JoinScreen())

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        # Dynamically set ❯ pointer on highlighted option
        opt_list = self.query_one("#menu_list", OptionList)
        prompts = [
            ("create", "Create Server", "Dial out to peer · bypasses CGNAT"),
            ("join", "Join Server", "Wait for incoming session and authorize peer"),
        ]
        for idx, (oid, title, desc) in enumerate(prompts):
            prefix = "❯  " if idx == event.option_index else "   "
            opt_list.replace_option_prompt_at_index(idx, f"{prefix}{title:<18} {desc}")

    def on_mount(self) -> None:
        focus_first(self)

    async def on_key(self, event) -> None:
        if event.key in ("escape", "q"):
            self.app.exit()
            event.stop()
            return
        if handle_arrow_key(self, event.key):
            event.stop()
```

Add CSS for `OptionList` in `src/riptide/theme.py`:
```css
OptionList {
    background: transparent;
    border: none;
    padding: 1 2;
    height: auto;
}
OptionList:focus {
    border: none;
}
OptionList > .option-list--option {
    padding: 0 1;
    background: transparent;
    color: #E8E8E8;
}
OptionList > .option-list--option-highlighted {
    background: transparent;
    color: #FF6B6B;
    text-style: bold;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_menu.py tests/test_focus.py`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/riptide/screens/menu.py src/riptide/core/focus.py src/riptide/theme.py tests/test_menu.py
git commit -m "feat: overhaul menu screen with ANSI header, dynamic version, and interactive option list"
```

---

### Task 4: File Browser Tabular Redesign in SessionScreen

**Files:**
- Modify: `src/riptide/screens/session_screen.py`
- Modify: `src/riptide/theme.py`
- Test: `tests/test_session_screen.py` (new test)

**Interfaces:**
- Produces:
  - Tabular file browser with row starting with `> `
  - Left-aligned filename in `#E8E8E8`, right-aligned size and modified date (`dd-mm-yyyy hh:mm am/pm`) in dull font (`#71717A`).
  - Active selection marker `>` highlighted with accent on focused item.
  - Keymap footer `[↑/↓] Navigate  [Space] Select  [Enter] Send  [Esc] Leave Session`.

- [ ] **Step 1: Write test for tabular file row rendering in SessionScreen**

Create `tests/test_session_screen.py`:
```python
from pathlib import Path
from riptide.core.file_select import format_file_row

def test_file_row_structure(tmp_path):
    p = tmp_path / "testfile.dat"
    p.write_bytes(b"x" * 2048)
    name, size, mtime = format_file_row(p)
    assert name == "testfile.dat"
    assert "KB" in size
    assert "-" in mtime and ("am" in mtime or "pm" in mtime)
```

- [ ] **Step 2: Run test to verify it passes baseline**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_session_screen.py`
Expected: PASS

- [ ] **Step 3: Update `src/riptide/screens/session_screen.py` with tabular layout and keymap**

In `src/riptide/screens/session_screen.py`:
- Use `format_file_row` to construct formatted rows for each file in `list_cwd_files(self.cwd)`:
```python
def make_file_label(path: Path, is_selected: bool = False) -> str:
    name, size, mtime = format_file_row(path)
    prefix = "> "
    # Right-aligned table columns with Rich text or aligned spacing
    return f"{prefix}{name:<32} {size:>10}   {mtime:>20}"
```
- Style file rows:
  - Add `.file-row` and `ListView` CSS in `theme.py` to keep transparent background.
  - Filename in `#E8E8E8`, size & date in `#71717A`.
- Update session headers with `TAGLINES["session"]`.
- Style primary action: `Button("Send selected", id="send", classes="primary")`.
- Remove `Button("Leave session")` and add `Static("[↑/↓] Move   [Space] Select   [Enter] Send   [Esc] Leave Session", classes="keymap-bar")`.
- Bind `escape` key to leave session.

- [ ] **Step 4: Run full test suite**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit changes**

```bash
git add src/riptide/screens/session_screen.py src/riptide/theme.py tests/test_session_screen.py
git commit -m "feat: implement tabular file browser with dull size and date columns"
```

---

### Task 5: Create, Join, and Setup Screens Redesign

**Files:**
- Modify: `src/riptide/screens/create.py`
- Modify: `src/riptide/screens/join.py`
- Modify: `src/riptide/screens/setup.py`
- Test: `tests/test_screens_smoke.py` (new smoke test)

**Interfaces:**
- Produces:
  - `CreateScreen`: past peers rendered as clean list/chips; prominent primary "Create Server" button; tagline; `[Esc] Back` in footer.
  - `JoinScreen`: live status indicator; prominent green "Allow" vs muted "Deny"; tagline; `[Esc] Back` in footer.
  - `SetupScreen`: clean transparent layout and tagline.

- [ ] **Step 1: Write headless smoke test for all screens**

Create `tests/test_screens_smoke.py`:
```python
from textual.app import App
from riptide.screens.menu import MenuScreen
from riptide.screens.create import CreateScreen
from riptide.screens.join import JoinScreen
from riptide.screens.setup import SetupScreen

class SmokeApp(App):
    def on_mount(self):
        self.push_screen(MenuScreen())

async def test_all_screens_mount():
    app = SmokeApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, MenuScreen)
        app.push_screen(CreateScreen())
        await pilot.pause()
        assert isinstance(app.screen, CreateScreen)
        app.pop_screen()
        app.push_screen(JoinScreen())
        await pilot.pause()
        assert isinstance(app.screen, JoinScreen)
        app.pop_screen()
        app.push_screen(SetupScreen())
        await pilot.pause()
        assert isinstance(app.screen, SetupScreen)
        app.pop_screen()
        assert isinstance(app.screen, MenuScreen)
```

- [ ] **Step 2: Run test to check current behavior**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_screens_smoke.py`
Expected: Check if existing screens pass or fail

- [ ] **Step 3: Update `CreateScreen`, `JoinScreen`, and `SetupScreen`**

- In `src/riptide/screens/create.py`:
  - Replace raw buttons with clean peer chip list or minimal buttons.
  - Use `TAGLINES["create"]` for subheader.
  - Primary button: `Button("Create Server", id="create", classes="primary")`.
  - Remove "Back" button; add `Static("[Enter] Connect   [Esc] Back", classes="keymap-bar")`.
- In `src/riptide/screens/join.py`:
  - Use `TAGLINES["join"]` for subheader.
  - Allow button: `Button("Allow", id="allow", classes="allow")`.
  - Deny button: `Button("Deny", id="deny", classes="deny")`.
  - Remove "Back" button; add `Static("[Esc] Back", classes="keymap-bar")`.
- In `src/riptide/screens/setup.py`:
  - Use `TAGLINES["setup"]` for subheader.
  - Remove "Back" button; add `Static("[Esc] Back", classes="keymap-bar")`.

- [ ] **Step 4: Run smoke test and full test suite**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit changes**

```bash
git add src/riptide/screens/create.py src/riptide/screens/join.py src/riptide/screens/setup.py tests/test_screens_smoke.py
git commit -m "feat: overhaul Create, Join, and Setup screens with keymaps and rewritten taglines"
```

---

### Task 6: Final Verification & Smoke Proof

**Files:**
- Modify: `README.md` (if updating screenshots or CLI description)
- Test: All unit and integration test files

- [ ] **Step 1: Run complete test suite**

Run: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe -v`
Expected: 100% tests passing

- [ ] **Step 2: Execute CLI smoke verification**

Run: `"C:/Users/MpSingh/.venv-tools/Scripts/python.exe" -m riptide --version`
Expected: `riptide 0.5.0`

- [ ] **Step 3: Verify git tree clean**

Run: `git status`
Expected: Clean working tree

- [ ] **Step 4: Final commit and summary**

```bash
git commit --allow-empty -m "chore: complete CLI redesign and UX overhaul"
```
