# Project structure

```
riptide/
├── src/riptide/
│   ├── app.py
│   ├── theme.py
│   ├── screens/
│   │   ├── menu.py
│   │   ├── create.py
│   │   ├── join.py
│   │   └── session_screen.py
│   └── core/
│       ├── session.py
│       ├── identity.py
│       ├── nat.py
│       ├── config.py
│       ├── file_select.py
│       ├── firewall.py
│       ├── focus.py
│       └── transfer.py
├── tests/
├── REMOVED.md
└── README.md
```

## Top level

- `src/riptide/app.py`: Textual app entry. Shows the menu on mount.
- `src/riptide/theme.py`: Colours, block-letter headers, and CSS. Dark grey background, soft red accent.
- `REMOVED.md`: Code removed in v0.14.0, with the full code for each removed function and file, so one entry can be restored without rolling back the whole commit.

## Screens

- `src/riptide/screens/menu.py`: Create Server, listener, on top, and Join Server, dialler, second. Handles menu selection and highlight prompts.
- `src/riptide/screens/create.py`: Create Server page, the listener (`CreateScreen`). Waiting card, incoming connection approval, public IP display, firewall watch, and listener worker.
- `src/riptide/screens/join.py`: Join Server page, the dialler (`JoinScreen`). Saved devices list, hostname input with label, fingerprint approval as a popup modal, and dialling logic.
- `src/riptide/screens/session_screen.py`: File manager, selection, send, download request, download approval queue, progress display, and keyboard handling for the transfer page. The session side is host (Create) or client (Join).

## Core

- `src/riptide/core/session.py`: One TLS connection, framing, sending, receiving, reader loop, heartbeat, send lock, download ask and deny, and session creation: `HostListener.wait_for_client` on the host side, `join_session` on the client side.
- `src/riptide/core/identity.py`: Per-machine self-signed key and certificate, SHA-256 fingerprint, and identity file handling in `~/.riptide/`.
- `src/riptide/core/nat.py`: STUN public IP and HTTPS public IP fallback, shown on the Create Server page.
- `src/riptide/core/config.py`: Saved peers, session port, and config file handling in `~/.riptide/config.toml`. A peer is name, host, and certificate fingerprint.
- `src/riptide/core/file_select.py`: Folder listing, folder-first order, folder formatting, and selection helpers.
- `src/riptide/core/firewall.py`: OS firewall check and automatic open for the session port, plus the manual command for the Create page banner.
- `src/riptide/core/focus.py`: Arrow-key focus navigation helpers.
- `src/riptide/core/transfer.py`: Transfer progress, speed EMA, remaining size, ETA, and byte formatting.

## Tests

- `tests/`: pytest and pytest-asyncio tests for protocol, progress, file selection, focus, menu, and screens. Screen tests use headless Textual pilots. Run with `pytest`. The async screen tests need `pytest-asyncio`.
