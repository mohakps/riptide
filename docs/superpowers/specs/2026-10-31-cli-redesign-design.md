# Riptide CLI Redesign Specification

**Date:** 2026-10-31  
**Status:** Approved  
**Topic:** CLI Redesign & UX Overhaul  

---

## 1. Overview & Goals

Riptide is a terminal-based peer-to-peer file transfer tool built with Textual. The goal of this redesign is to replace the heavy, boxed, 1990s-button interface with a sleek, modern, transparent CLI inspired by premier developer tools (`gum`, `gh`, `lazygit`, `fzf`).

### Key Design Pillars
1. **True Terminal Transparency:** Eliminate solid dark grey background blocks (`#1E1E1E` and `#2A2A2A`). Keep backgrounds transparent so the user's terminal theme, wallpaper, and blur shine through.
2. **Interactive Unordered List Navigation:** Replace full-width 3-row button boxes with a fluid list selection widget displaying active cursor pointers (`❯`), clean titles, and muted contextual descriptions.
3. **Visual Hierarchy:** Primary actions (`Create Server`, `Join Server`, `Send Selected`, `Allow`) are prominent, bold, and accented. Secondary/utility actions (`Back`, `Exit`, `Leave Session`, `Deny`) are de-emphasized into a persistent keymap footer bar (`[Esc] Back   [q] Quit`) or muted controls.
4. **Clean Homepage:** Remove the redundant "Exit" menu option from the main menu; rely on standard keyboard shortcuts (`Esc`, `q`).
5. **Columnar File Browser:** Every file entry starts with `> `. Filename is clear white; file size and date modified are formatted in separate right-aligned columns using dull font (`#71717A`).
6. **Date Format:** Exact format specified as `dd-mm-yyyy hh:mm am/pm` (e.g. `31-10-2026 02:30 pm`).

---

## 2. Visual Theme & Styling (`src/riptide/theme.py`)

### 2.1 CSS & Transparency
- `Screen`: `background: transparent; color: #E8E8E8;`
- Remove solid fills on widgets; containers, lists, and screens have transparent backgrounds.
- Minimal borders: Thin rounded (`border: round #3F3F46;`) or borderless elements where appropriate.
- Accent color: Bright soft coral (`#FF6B6B`) for pointers, active cursor highlights, focused inputs, and brand elements.
- Muted color: Dull grey (`#71717A`) for metadata, column headers, secondary descriptions, and keymap text.
- Success color: Green (`#78DC8C`) for verified status, connected peers, and "Allow" action.
- Warning color: Yellow/amber (`#FFD166`) for incoming requests.

### 2.2 Header & Brand
- Refined ASCII header:
  ```text
    Ψ  R I P T I D E  Ψ
  ~~~  direct file transfer  ~~~
  ```
  Rendered in soft coral with center alignment, without heavy bounding boxes.

### 2.3 Keymap Footer Bar
- Context-aware footer bar displayed at the bottom of screens:
  ```text
  [↑/↓] Navigate   [Enter] Select   [Space] Mark   [Esc] Back   [q] Quit
  ```
  Keys enclosed in bright brackets, action descriptions in muted grey.

---

## 3. Screen Designs & Components

### 3.1 Homepage Menu (`src/riptide/screens/menu.py`)
- Removed `Button("Exit")`.
- Replaced buttons with interactive list navigation (`OptionList` or clean `ListView`):
  - **Option 1:** `Create Server` — `Dial out to peer (CGNAT-friendly)`
  - **Option 2:** `Join Server` — `Wait for incoming session and authorize peer`
- Selection indicator: `❯` in accent color for active item; inactive items indented.
- Keyboard bindings: `Up`/`Down` to navigate, `Enter` to select, `Esc` or `q` to quit cleanly.

### 3.2 File Browser & Session Screen (`src/riptide/screens/session_screen.py`)
- **Row Format:** Every row starts with `> ` followed by aligned columns:
  ```text
  > archive_v2.tar.gz                          1.42 GB   31-10-2026 02:15 pm
  > dataset_train.csv                          45.8 MB   30-10-2026 09:40 am
  > firmware_build.bin                          8.2 MB   28-10-2026 05:22 pm
  > README.md                                   2.1 KB   25-10-2026 11:05 am
  ```
- **Styling Rules:**
  - Prefix `> `: Accented when row is focused, muted when unfocused.
  - Filename: Crisp `#E8E8E8`, left-aligned.
  - File Size: Right-aligned column, formatted in B / KB / MB / GB, dull `#71717A`.
  - Date Modified: Right-aligned column, formatted as `dd-mm-yyyy hh:mm am/pm`, dull `#71717A`.
- **Action Hierarchy:**
  - Primary action: Prominent `Send Selected` button/prompt.
  - Secondary action: `Leave session` mapped to footer keymap `[Esc] Leave Session`.
  - Drag-and-drop / path paste input styled cleanly with transparent background and round border.
  - Transfer progress bar styled with thin accent fill and speed/ETA indicators.

### 3.3 Create Server Screen (`src/riptide/screens/create.py`)
- Past hosts rendered as clean, selectable chips or list items rather than stacked full-width button boxes.
- Address input with thin rounded border and clear placeholder text.
- Prominent "Create Server" primary action triggered by `Enter`.
- "Back" handled via `[Esc] Back` in footer.

### 3.4 Join Server Screen (`src/riptide/screens/join.py`)
- Live status indicator with pulse symbol: `○ Waiting for incoming connection...`.
- Approval modal/prompt:
  - Prominent "Allow" action in bold green (`#78DC8C`).
  - Subtle "Deny" action in muted grey.
- "Back" handled via `[Esc] Back`.

---

## 4. Helper & Core Updates

### 4.1 File Metadata Formatting (`src/riptide/core/file_select.py`)
- Add helper function `format_mtime(mtime: float) -> str` returning `dd-mm-yyyy hh:mm am/pm` in lowercase:
  ```python
  def format_mtime(mtime: float) -> str:
      dt = datetime.fromtimestamp(mtime)
      return dt.strftime("%d-%m-%Y %I:%M %p").lower()
  ```
- Add helper function `format_file_row(path: Path, width: int = 80) -> tuple[str, str, str]` or Rich-formatted line to cleanly split filename, size, and date modified into columns.

### 4.2 Focus & Navigation (`src/riptide/core/focus.py`)
- Update `focusable_widgets` to support `OptionList` or the new list selection widgets while maintaining full backward compatibility.
- Ensure all arrow key navigation tests pass without regressions.

---

## 5. Verification & Testing Plan

1. **Unit Tests:**
   - Run `pytest` on `tests/test_file_select.py`, `tests/test_focus.py`, `tests/test_progress.py`, `tests/test_session.py`.
   - Add unit tests for `format_mtime` verifying exact `dd-mm-yyyy hh:mm am/pm` output across timestamps.
   - Add unit tests for `format_file_row` verifying column alignment and dull metadata styling.
2. **Visual & Headless Smoke Tests:**
   - Run Textual headless driver to verify all screens (`MenuScreen`, `CreateScreen`, `JoinScreen`, `SessionScreen`, `SetupScreen`) compose cleanly without rendering exceptions.
   - Verify keyboard interactions (`Up`/`Down`, `Enter`, `Esc`, `q`) transition between screens properly.
