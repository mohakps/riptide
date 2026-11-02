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
│   │   ├── session_screen.py
│   │   └── setup.py
│   └── core/
│       ├── session.py
│       ├── identity.py
│       ├── nat.py
│       ├── config.py
│       ├── file_select.py
│       └── transfer.py
├── tests/
└── README.md
```

## Top level

- `src/riptide/app.py`: Textual app entry. Shows the menu on mount.
- `src/riptide/theme.py`: Colours, block-letter headers, and CSS. Dark grey background, soft red accent.

## Screens

- `src/riptide/screens/menu.py`: Create Server, listener, on top, and Join Server, dialler, second. Handles menu selection and highlight prompts.
- `src/riptide/screens/create.py`: Join Server page, the dialler. Saved devices list, hostname input with label, fingerprint approval, and dialling logic. The filename is historical, from before the v0.6.0 name swap.
- `src/riptide/screens/join.py`: Create Server page, the listener. Waiting card, incoming connection approval, public IP display, and listener worker. The filename is historical, from before the v0.6.0 name swap.
- `src/riptide/screens/session_screen.py`: File manager, selection, send, download request, download approval queue, progress display, and keyboard handling for the transfer page.
- `src/riptide/screens/setup.py`: Earlier setup and UPnP helper screen. Checks firewall rules and tries UPnP discovery, with manual forwarding instructions as fallback.

## Core

- `src/riptide/core/session.py`: One TLS connection, framing, sending, receiving, reader loop, heartbeat, send lock, download ask and deny, and listener and dialler session creation.
- `src/riptide/core/identity.py`: Per-machine self-signed key and certificate, SHA-256 fingerprint, and identity file handling in `~/.riptide/`.
- `src/riptide/core/nat.py`: CGNAT detection, UPnP WAN lookup, STUN public IP, HTTPS public IP fallback, local IP, and manual forwarding text.
- `src/riptide/core/config.py`: Saved peers, session port, and config file handling in `~/.riptide/config.toml`. Includes migration from the old default port 49872 to 50000.
- `src/riptide/core/file_select.py`: Folder listing, folder-first order, folder formatting, Tab completion for absolute paths, common prefix, and selection helpers.
- `src/riptide/core/transfer.py`: Transfer progress, speed EMA, remaining size, ETA, byte formatting, and SHA-256 file helpers.

## Tests

- `tests/`: pytest and pytest-asyncio tests for protocol, progress, file selection, focus, menu, and screens. Screen tests use headless Textual pilots. Run with `pytest`. The async screen tests need `pytest-asyncio`.

## Historical naming note

`screens/create.py` is the dialler and `screens/join.py` is the listener, from before the v0.6.0 name swap. The UI names are correct. The filenames are not yet renamed, to avoid breaking layout tests and CSS selectors tied to them. If you rename them, rename the tests and the `#create_*` and `#join_*` CSS selectors with them.
