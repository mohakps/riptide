# Task 2 Brief: Theme Transparency, ANSI Shadow Block Header & Keymap Bar

## Objective
Update `src/riptide/theme.py` to:
1. Make terminal background 100% transparent (`Screen { background: transparent; }`, no `#1E1E1E` or `#2A2A2A` screen/container background fills).
2. Integrate the 6-line ANSI Shadow Block art `HEADER_BANNER` and `HEADER_LINES`.
3. Define `TAGLINES` dictionary for all screens: `home`, `create`, `join`, `session`, `setup`.
4. Style inputs, streamlined buttons (`round` border, transparent background, primary/allow/deny classes), progress bar, and `.keymap-bar`.
5. Update `assets/trident.txt` to contain the ANSI Shadow Block header.

## Global Constraints
- Terminal background must be 100% transparent (`Screen { background: transparent; }`).
- Header banner must be the 6-line ANSI Shadow Block:
```text
██████╗ ██╗██████╗ ████████╗██╗██████╗ ███████╗
██╔══██╗██║██╔══██╗╚══██╔══╝██║██╔══██╗██╔════╝
██████╔╝██║██████╔╝   ██║   ██║██║  ██║█████╗  
██╔══██╗██║██╔═══╝    ██║   ██║██║  ██║██╔══╝  
██║  ██║██║██║        ██║   ██║██████╔╝███████╗
╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   ╚═╝╚═════╝ ╚══════╝
```
- Taglines:
  - `home`: "Direct, encrypted PC-to-PC file transfer · Zero cloud storage, zero intermediate hops"
  - `create`: "Dial directly to peer · Outbound connection bypasses CGNAT and strict firewalls"
  - `join`: "Listening for peer handshake · Keep this screen open while creator dials in"
  - `session`: "Direct end-to-end encrypted channel · Select local files or drop paths to transfer"
  - `setup`: "Configure local SSH daemon and automated UPnP port forwarding for inbound connections"
- All existing tests must pass: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe`.

## Steps
1. Write failing tests in `tests/test_theme.py` checking:
   - `test_css_is_transparent`: checks `background: transparent` in CSS and `#1E1E1E` not in CSS.
   - `test_ansi_header_present`: checks `██████╗` in `HEADER_BANNER`.
   - `test_screen_taglines_defined`: checks keys `home`, `create`, `join`, `session`, `setup` in `TAGLINES`.
2. Run test to verify failure: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_theme.py`.
3. Update `src/riptide/theme.py` with the updated constants and CSS (including rules for `OptionList` and `.keymap-bar`).
4. Update `assets/trident.txt`.
5. Run tests to verify pass: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe`.
6. Commit: `git add src/riptide/theme.py assets/trident.txt tests/test_theme.py && git commit -m "style: add ANSI Shadow Block banner, transparent CSS, and screen taglines"`.
7. Write summary report to `.superpowers/sdd/task-2-report.md`.
