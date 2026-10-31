# Graph Report - riptide  (2026-11-01)

## Corpus Check
- 39 files · ~15,430 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: .diff 2, (none) 1)

## Summary
- 420 nodes · 798 edges · 18 communities (15 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 57 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `14b10a76`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- session.py
- session_screen.py
- file_select.py
- TransferProgress
- JoinScreen
- MenuScreen
- SetupScreen
- CreateScreen
- SessionScreen
- ssh_client.py
- setup_linux.py
- Steps
- riptide
- JoinListener
- nat.py
- screens/__init__.py
- progress.md
- riptide

## God Nodes (most connected - your core abstractions)
1. `SessionScreen` - 24 edges
2. `CreateScreen` - 21 edges
3. `JoinScreen` - 19 edges
4. `MenuScreen` - 19 edges
5. `Session` - 18 edges
6. `focus_first()` - 16 edges
7. `handle_arrow_key()` - 16 edges
8. `create_session()` - 16 edges
9. `_send_header()` - 14 edges
10. `JoinListener` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Task 4: File Browser Tabular Redesign in SessionScreen` --references--> `format_file_row()`  [INFERRED]
  docs/superpowers/plans/2026-10-31-cli-redesign.md → src/riptide/core/file_select.py
- `4.2 Focus & Navigation (`src/riptide/core/focus.py`)` --references--> `focusable_widgets()`  [INFERRED]
  docs/superpowers/specs/2026-10-31-cli-redesign-design.md → src/riptide/core/focus.py
- `Riptide CLI Redesign Implementation Plan` --references--> `format_mtime()`  [INFERRED]
  docs/superpowers/plans/2026-10-31-cli-redesign.md → src/riptide/core/file_select.py
- `5. Verification & Testing Plan` --references--> `format_mtime()`  [INFERRED]
  docs/superpowers/specs/2026-10-31-cli-redesign-design.md → src/riptide/core/file_select.py
- `5. Verification & Testing Plan` --references--> `format_file_row()`  [INFERRED]
  docs/superpowers/specs/2026-10-31-cli-redesign-design.md → src/riptide/core/file_select.py

## Import Cycles
- None detected.

## Communities (18 total, 3 thin omitted)

### Community 0 - "session.py"
Cohesion: 0.07
Nodes (44): base64, datetime, hashlib, json, os, cert_fingerprint(), ensure_identity(), fingerprint_of_cert_file() (+36 more)

### Community 1 - "session_screen.py"
Cohesion: 0.10
Nodes (31): pathlib, socket, focus_first(), focusable_widgets(), handle_arrow_key(), move_focus(), Arrow-key focus navigation. Root cause of the reported bug: Textual moves focus…, Return focusable widgets in DOM order, skipping disabled ones. (+23 more)

### Community 2 - "file_select.py"
Cohesion: 0.07
Nodes (38): re, shlex, complete(), format_bytes(), format_file_row(), format_mtime(), parse_dropped_text(), Path (+30 more)

### Community 3 - "TransferProgress"
Cohesion: 0.06
Nodes (22): download_file(), format_bytes(), format_eta(), Path, Transfer progress, hashing, and resumable SFTP upload. No invented crypto: SFTP…, Download one file via SFTP, writing .part then renaming after size check.…, Upload files resumably, writing .part then renaming after verification.…, EMA speed, remaining size, and ETA for one whole transfer. (+14 more)

### Community 4 - "JoinScreen"
Cohesion: 0.10
Nodes (18): dataclasses, OptionSelected, add_peer(), Config, config_dir(), config_path(), _contains_private_key(), _escape() (+10 more)

### Community 5 - "MenuScreen"
Cohesion: 0.09
Nodes (20): argparse, ArgumentParser, OptionHighlighted, pytest, build_parser(), main(), App, Riptide Textual app. Entry point: riptide = riptide.app:main (+12 more)

### Community 6 - "SetupScreen"
Cohesion: 0.08
Nodes (20): 1. Overview & Goals, 2.1 CSS & Transparency, 2.2 Header, Dynamic Version & Taglines, 2.3 Keymap Footer Bar, 2. Visual Theme & Styling (`src/riptide/theme.py`), 3.1 Homepage Menu (`src/riptide/screens/menu.py`), 3.2 File Browser & Session Screen (`src/riptide/screens/session_screen.py`), 3.3 Create Server Screen (`src/riptide/screens/create.py`) (+12 more)

### Community 7 - "CreateScreen"
Cohesion: 0.10
Nodes (16): Global Constraints, Riptide CLI Redesign Implementation Plan, Task 1: Version Resolution & File Metadata Formatting, Task 2: Theme Transparency, ANSI Shadow Block Header & Keymap Bar, Task 3: Interactive Unordered List Navigation & MenuScreen Overhaul, Task 4: File Browser Tabular Redesign in SessionScreen, Task 5: Create, Join, and Setup Screens Redesign, Task 6: Final Verification & Smoke Proof (+8 more)

### Community 8 - "SessionScreen"
Cohesion: 0.14
Nodes (11): ListItem, Selected, add_to_selection(), list_cwd_files(), _build_file_item(), ComposeResult, Path, Pressed (+3 more)

### Community 9 - "ssh_client.py"
Cohesion: 0.15
Nodes (10): Exception, _fingerprint_from_key(), FingerprintChangedError, parse_peer(), Path, SSH client with staged status and strict fingerprint handling., Parse user@host. Raises ValueError for anything else., Thin Paramiko wrapper. The caller owns stage reporting. (+2 more)

### Community 10 - "setup_linux.py"
Cohesion: 0.16
Nodes (14): platform, shutil, is_linux(), package_manager(), Linux / Arch SSH setup helpers. No port numbers in user-facing text., run_setup(), steps(), is_windows() (+6 more)

### Community 11 - "Steps"
Cohesion: 0.20
Nodes (11): Global Constraints, Objective, Steps, Task 2 Brief: Theme Transparency, ANSI Shadow Block Header & Keymap Bar, Review Finding Fix, Status, Summary of Changes, Task 2 Report: Theme Transparency, ANSI Shadow Block Header & Keymap Bar (+3 more)

### Community 12 - "riptide"
Cohesion: 0.17
Nodes (11): Create Server (CGNAT side, if one side is CGNAT), Development, In a session, Install (GitHub only, no PyPI), Join Server (public side, if one side is CGNAT), Limitations in v4, One-time network step for the public side, riptide (+3 more)

### Community 13 - "JoinListener"
Cohesion: 0.32
Nodes (9): JoinListener, Join side: listen for one creator, approve it in the UI, return a Session.…, _free_port(), test_both_directions_and_download(), join_worker(), test_fingerprint_change_aborts(), join_worker(), test_receiver_progress_and_no_idle_timeout() (+1 more)

### Community 14 - "nat.py"
Cohesion: 0.22
Nodes (8): ipaddress, detect_cgnat(), is_cgnat_ip(), is_private_ip(), NAT / CGNAT helpers. User-facing text never contains a port number., True when the router WAN address is CGNAT, or differs from public IP while…, Best-effort UPnP. Returns (ok, message) without ever promising success., upnp_attempt()

## Knowledge Gaps
- **30 isolated node(s):** `riptide`, `SDD Progress Ledger`, `Global Constraints`, `Status`, `Commit Hash` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 160 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SessionScreen` connect `SessionScreen` to `session.py`, `session_screen.py`, `TransferProgress`, `JoinScreen`, `SetupScreen`, `CreateScreen`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `5. Verification & Testing Plan` connect `SetupScreen` to `file_select.py`, `JoinScreen`, `MenuScreen`, `CreateScreen`, `SessionScreen`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `CreateScreen` connect `CreateScreen` to `session_screen.py`, `JoinScreen`, `MenuScreen`, `SetupScreen`, `SessionScreen`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `SessionScreen` (e.g. with `5. Verification & Testing Plan` and `CreateScreen`) actually correct?**
  _`SessionScreen` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `CreateScreen` (e.g. with `Task 5: Create, Join, and Setup Screens Redesign` and `5. Verification & Testing Plan`) actually correct?**
  _`CreateScreen` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `JoinScreen` (e.g. with `Task 5: Create, Join, and Setup Screens Redesign` and `5. Verification & Testing Plan`) actually correct?**
  _`JoinScreen` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `MenuScreen` (e.g. with `Task 3: Interactive Unordered List Navigation & MenuScreen Overhaul` and `5. Verification & Testing Plan`) actually correct?**
  _`MenuScreen` has 8 INFERRED edges - model-reasoned connections that need verification._