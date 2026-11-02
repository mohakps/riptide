# Main Screen Footer Redesign Specification

**Date:** 2026-11-02  
**Status:** Approved  
**Topic:** Main Screen (MenuScreen) Footer Redesign  

---

## 1. Overview & Goals

In Riptide, secondary screens (`CreateScreen`, `JoinScreen`, and `SessionScreen`) use a modern, docked `#footer_bar` layout with evenly spaced `.keymap-item` columns displaying shortcut keys in brackets (e.g., `[bold #E8E8E8]\[Key][/] [dim #FFFFFF]Action[/]`).

The main screen (`MenuScreen`) currently renders an inline `Static` widget with class `.keymap-bar` placed inside the main `Vertical` container:
```python
Static(r"[↑/↓] Navigate   \[Enter] Select   [Esc/q] Quit", classes="keymap-bar")
```

The goal of this redesign is to bring visual consistency and architectural uniformity across the application by updating `MenuScreen` to use the same docked `#footer_bar` component and styling as the other screens.

---

## 2. Component Structure & Architecture (`src/riptide/screens/menu.py`)

### 2.1 Container & Layout
- Remove the inline `Static(..., classes="keymap-bar")` from inside the `Vertical` container in `MenuScreen.compose`.
- Add a root-level `Horizontal(id="footer_bar")` yielded immediately after the `Vertical` layout.
- Use Textual's standard `dock: bottom` rule configured globally for `#footer_bar` in `src/riptide/theme.py`.

### 2.2 Footer Elements
The `#footer_bar` will contain three `Label` widgets spanning the full terminal width:
1. **Left column (`classes="keymap-item keymap-left"`)**:
   `Label(r"[bold #E8E8E8]\[↑/↓][/] [dim #FFFFFF]Navigate[/]", classes="keymap-item keymap-left")`
2. **Center column (`classes="keymap-item"`)**:
   `Label(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Select[/]", classes="keymap-item")`
3. **Right column (`classes="keymap-item keymap-right"`)**:
   `Label(r"[bold #E8E8E8]\[Esc][/] [dim #FFFFFF]Quit[/]", classes="keymap-item keymap-right")`

### 2.3 Imports
- Ensure `Horizontal` is imported from `textual.containers`.
- Ensure `Label` is imported from `textual.widgets`.

---

## 3. Keyboard Interactions & Event Handling

- Keep existing key bindings in `MenuScreen.on_key`:
  - `escape` and `q`: calls `self.app.exit()`.
  - `up` and `down`: navigates the `OptionList`.
  - `enter`: selects the highlighted option via `OptionList.OptionSelected`.
- Displaying `[Esc]` in the footer aligns with other screens (`CreateScreen`, `JoinScreen`, `SessionScreen`), while preserving `"q"` as a quick-quit shortcut in code.

---

## 4. Theme & CSS (`src/riptide/theme.py`)

Existing CSS definitions in `src/riptide/theme.py` fully support this structure without modification:
```css
#footer_bar {
    dock: bottom;
    width: 100%;
    height: 1;
    layout: horizontal;
    background: transparent;
    padding: 0 1;
    margin: 0;
}
.keymap-item {
    width: 1fr;
    text-align: center;
    color: #71717A;
}
.keymap-left {
    text-align: left;
}
.keymap-right {
    text-align: right;
}
```

---

## 5. Testing & Verification

1. **Unit & Smoke Tests (`tests/test_menu.py`)**:
   - Verify `MenuScreen` composes `#footer_bar` with `.keymap-item` children.
   - Assert presence of `[↑/↓]`, `[Enter]`, and `[Esc]` formatted keys in `#footer_bar`.
   - Ensure `MenuScreen` no longer renders any `.keymap-bar` widget.
2. **Regression Testing**:
   - Run complete test suite (`uv run --with pytest --with pytest-asyncio pytest`) ensuring all tests pass without regressions.
