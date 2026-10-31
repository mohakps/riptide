from __future__ import annotations

import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from ..core.config import Peer, add_peer, load_config
from ..core.file_select import (
    add_to_selection,
    complete,
    format_bytes,
    list_cwd_files,
    parse_dropped_text,
    total_size,
)
from ..core.keys import ensure_keypair
from ..core.ssh_client import FingerprintChangedError, RiptideSSH, UnknownHostError, parse_peer
from ..theme import HEADER_LINES


class SendScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.selection: list[Path] = []
        self.config = load_config()
        self.ssh: RiptideSSH | None = None
        self._trust_pending = False
        self._connecting = False

    def compose(self) -> ComposeResult:
        known = ", ".join(p.label() for p in self.config.peers) or "No saved peers yet."
        files = list_cwd_files(self.cwd)
        items = [ListItem(Label(f"{p.name}  ({format_bytes(p.stat().st_size)})")) for p in files]
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static("SEND", classes="accent"),
            Static(f"Known peers: {known}", classes="dim"),
            Input(placeholder="Peer: user@host", id="peer"),
            Static("Connecting status: idle", id="status"),
            ListView(*items, id="cwd_list"),
            Input(
                placeholder="Type a file name, Tab to complete, Enter to add. Blank Enter to send. Paste dropped paths here.",
                id="file_input",
            ),
            Static("Selected: none", id="selected"),
            Button("Connect in background", id="connect"),
            Button("Start transfer", id="start"),
            Button("Back", id="back"),
            Static("Tip: drag and drop files into this terminal and they are pasted as paths here.", classes="dim"),
        )

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(f"Connecting status: {text}")
        except Exception:
            pass

    def _refresh_selected(self) -> None:
        total = total_size(self.selection)
        names = ", ".join(p.name for p in self.selection) or "none"
        try:
            self.query_one("#selected", Static).update(
                f"Selected ({len(self.selection)}): {names}  |  Total: {format_bytes(total)}"
            )
        except Exception:
            pass

    def _add_from_text(self, text: str) -> None:
        found = parse_dropped_text(text, self.cwd)
        if not found:
            self._set_status(f"No file found for: {text}")
            return
        add_to_selection(self.selection, found)
        self._refresh_selected()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "peer":
            self._start_connect()
        elif event.input.id == "file_input":
            text = event.value.strip()
            event.input.value = ""
            if not text:
                self._start_transfer()
            else:
                self._add_from_text(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect":
            self._start_connect()
        elif event.button.id == "start":
            self._start_transfer()
        elif event.button.id == "back":
            self._close_ssh()
            self.app.pop_screen()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        files = list_cwd_files(self.cwd)
        try:
            chosen = files[event.list_view.index]
        except Exception:
            return
        add_to_selection(self.selection, [chosen])
        self._refresh_selected()

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self._close_ssh()
            self.app.pop_screen()
            return
        focused = self.focused
        if event.key == "tab" and isinstance(focused, Input) and focused.id == "file_input":
            event.stop()
            candidates = complete(focused.value, self.cwd)
            if len(candidates) == 1:
                focused.value = candidates[0]
            elif candidates:
                common = candidates[0]
                for other in candidates[1:]:
                    while not other.startswith(common) and common:
                        common = common[:-1]
                if common and common != focused.value:
                    focused.value = common
                self._set_status(f"Completions: {', '.join(candidates[:10])}")

    def _close_ssh(self) -> None:
        if self.ssh is not None:
            try:
                self.ssh.close()
            except Exception:
                pass
            self.ssh = None

    def _start_connect(self) -> None:
        if self._connecting:
            return
        try:
            peer_input = self.query_one("#peer", Input)
            user, host = parse_peer(peer_input.value)
        except Exception as exc:
            self._set_status(f"Failed: {exc}")
            return
        self._connecting = True
        self._set_status("Starting background connection...")
        thread = threading.Thread(target=self._connect_worker, args=(user, host), daemon=True)
        thread.start()

    def _connect_worker(self, user: str, host: str) -> None:
        try:
            known = self.config.peer_for(user, host)
            private, _public = ensure_keypair()
            ssh = RiptideSSH(user, host, port=self.config.ssh_port, key_path=private,
                            known_fingerprint=known.fingerprint if known else "")
            allow_new = self._trust_pending or known is not None
            try:
                ssh.connect(on_stage=lambda m: self.app.call_from_thread(self._set_status, m),
                            allow_new_host=allow_new)
            except UnknownHostError:
                self.app.call_from_thread(
                    self._set_status,
                    f"Unknown host fingerprint: {ssh.fingerprint}. Press Connect again to trust it.",
                )
                self._trust_pending = True
                self._connecting = False
                return
            self.ssh = ssh
            self._connecting = False
            self.app.call_from_thread(self._set_status, f"Authenticated as {user}@{host}")
            if known is None and ssh.fingerprint:
                add_peer(self.config, Peer(name=host, user=user, host=host, fingerprint=ssh.fingerprint))
        except FingerprintChangedError as exc:
            self._connecting = False
            self.app.call_from_thread(self._set_status, f"Failed: {exc}")
        except Exception as exc:
            self._connecting = False
            self.app.call_from_thread(self._set_status, f"Failed: {exc}")

    def _start_transfer(self) -> None:
        if not self.selection:
            self._set_status("Failed: select at least one file first.")
            return
        try:
            peer_input = self.query_one("#peer", Input)
            user, host = parse_peer(peer_input.value)
        except Exception as exc:
            self._set_status(f"Failed: {exc}")
            return
        from .transfer import TransferScreen

        self.app.push_screen(TransferScreen(f"{user}@{host}", list(self.selection), self.config))
