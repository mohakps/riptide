"""SSH session screen, v3.

File data travels over SSH/SFTP (port 22), not over TLS.
TLS is only the control channel that already established the
session and exchanged SSH keys, with Allow buttons and no code.

Creator side: this screen owns an SFTP client to the joiner.
- Send: SFTP upload to the joiner.
- Download: SFTP download from the joiner.
- When the joiner presses Send on their side, they send a TLS
  control message asking the creator to download that file via
  SFTP. That request is handled here, automatically.

Joiner side: this screen owns only the TLS control channel.
- Send: send a TLS control message asking the creator to
  download the named file via SFTP. No file bytes go over TLS.
- Files the creator uploads arrive via the joiner's SSH server,
  in the joiner's home folder, and the creator notifies the
  joiner over TLS when an upload finishes.
"""
from __future__ import annotations

import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, ProgressBar, Static

from ..core.file_select import (
    add_to_selection,
    complete,
    format_bytes,
    list_cwd_files,
    parse_dropped_text,
    total_size,
)
from ..core.focus import focus_first, handle_arrow_key
from ..core.session import Session
from ..core.transfer import download_file, sha256_file, upload_files, TransferProgress, format_bytes as fmt, remote_sha256
from ..theme import HEADER_LINES


class SSHSessionScreen(Screen):
    def __init__(self, tls_session: Session, role: str, ssh=None, sftp=None):
        super().__init__()
        self.tls = tls_session
        self.role = role
        self.ssh = ssh
        self.sftp = sftp
        self.cwd = tls_session.cwd
        self.selection: list[Path] = []

    def compose(self) -> ComposeResult:
        files = list_cwd_files(self.cwd)
        items = [ListItem(Label(f"{p.name}  ({format_bytes(p.stat().st_size)})")) for p in files]
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static(f"SSH SESSION  ({self.role})  with {self.tls.peer_device or 'peer'}", classes="accent"),
            Static("Status: connected over SSH", id="status"),
            ListView(*items, id="cwd_list"),
            Input(placeholder="Type a file name, Tab to complete, Enter to add. Paste dropped paths here.", id="file_input"),
            Static("Selected: none", id="selected"),
            Button("Send selected (SSH)", id="send"),
            Input(placeholder="Remote file name to download (SSH)", id="download_input"),
            Button("Download remote file (SSH)", id="download"),
            ProgressBar(total=100, id="bar"),
            Static("Sent: -", id="stats"),
            Button("Leave session", id="leave"),
            Static("File data goes over SSH. The TLS session is only control + key exchange.", classes="dim"),
        )

    def on_mount(self) -> None:
        self.tls.on_status = lambda msg: self.app.call_from_thread(self._set_status, msg)
        self.tls.on_error = lambda msg: self.app.call_from_thread(self._set_status, msg)
        if self.role == "creator":
            self.tls.on_ssh_download_request = lambda name: threading.Thread(target=self._handle_ssh_download_request, args=(name,), daemon=True).start()
        self.tls.start()
        focus_first(self)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(f"Status: {text}")
        except Exception:
            pass

    def _refresh_selected(self) -> None:
        total = total_size(self.selection)
        names = ", ".join(p.name for p in self.selection) or "none"
        try:
            self.query_one("#selected", Static).update(f"Selected ({len(self.selection)}): {names}  |  Total: {format_bytes(total)}")
        except Exception:
            pass

    def _refresh_files(self) -> None:
        try:
            lst = self.query_one("#cwd_list", ListView)
            lst.clear()
            for p in list_cwd_files(self.cwd):
                lst.append(ListItem(Label(f"{p.name}  ({format_bytes(p.stat().st_size)})")))
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "file_input":
            text = event.value.strip(); event.input.value = ""
            if text:
                add_to_selection(self.selection, parse_dropped_text(text, self.cwd)); self._refresh_selected()
        elif event.input.id == "download_input":
            name = event.value.strip(); event.input.value = ""
            if name:
                self._download(name)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        files = list_cwd_files(self.cwd)
        try:
            chosen = files[event.list_view.index]
        except Exception:
            return
        add_to_selection(self.selection, [chosen]); self._refresh_selected()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            if self.role == "creator":
                self._send_ssh()
            else:
                # Joiner Send: ask creator to download via SSH.
                if not self.selection:
                    self._set_status("Failed: select at least one file first.")
                    return
                for path in list(self.selection):
                    self.tls.send_ssh_download_request(path.name)
                    self._set_status(f"Asked creator to download {path.name} via SSH...")
                self.selection = []; self._refresh_selected()
        elif event.button.id == "download":
            try:
                name = self.query_one("#download_input", Input).value.strip()
            except Exception:
                name = ""
            if name:
                if self.role == "creator":
                    self._download(name)
                else:
                    self._set_status("Joiner download: select a file and press Send, creator will download it via SSH.")
        elif event.button.id == "leave":
            try:
                self.tls.close()
            except Exception:
                pass
            try:
                if self.sftp is not None:
                    self.sftp.close()
            except Exception:
                pass
            try:
                if self.ssh is not None:
                    self.ssh.close()
            except Exception:
                pass
            self.app.pop_screen()

    def _send_ssh(self) -> None:
        if self.sftp is None:
            self._set_status("Failed: no SSH connection.")
            return
        if not self.selection:
            self._set_status("Failed: select at least one file first.")
            return
        files = list(self.selection); self.selection = []; self._refresh_selected()

        def worker():
            try:
                progress = TransferProgress(total_size(files))
                uploaded = upload_files(self.sftp, files, ".", progress, on_file=lambda n, s, t: self.app.call_from_thread(self._set_progress, n, s, t))
                # Verify via SSH exec, when available.
                results = []
                for local, remote in zip(files, uploaded):
                    remote_hash = remote_sha256(self.ssh, remote) if self.ssh is not None else None
                    local_hash = sha256_file(local)
                    if remote_hash is None:
                        results.append(f"{local.name}: uploaded, remote hash unavailable")
                    elif remote_hash == local_hash:
                        results.append(f"{local.name}: verified")
                    else:
                        results.append(f"{local.name}: HASH MISMATCH, re-transfer")
                self.app.call_from_thread(self._set_status, "Done: " + "; ".join(results))
                try:
                    self.tls.send_info("Creator uploaded: " + ", ".join(p.name for p in files))
                except Exception:
                    pass
                self.app.call_from_thread(self._refresh_files)
            except Exception as exc:
                self.app.call_from_thread(self._set_status, f"Failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _set_progress(self, name: str, sent: int, total: int) -> None:
        try:
            bar = self.query_one("#bar", ProgressBar)
            bar.progress = (sent / total * 100) if total else 100
            self.query_one("#stats", Static).update(f"Sent: {format_bytes(sent)} / {format_bytes(total)}  ({name})")
        except Exception:
            pass

    def _download(self, name: str) -> None:
        if self.sftp is None:
            self._set_status("Failed: no SSH connection.")
            return

        def worker():
            try:
                self.app.call_from_thread(self._set_status, f"Downloading {name} via SSH...")
                path = download_file(self.sftp, name, self.cwd, on_progress=lambda n, s, t: self.app.call_from_thread(self._set_progress, n, s, t))
                self.app.call_from_thread(self._set_status, f"Downloaded {path.name}: verified by size")
                self.app.call_from_thread(self._refresh_files)
            except Exception as exc:
                self.app.call_from_thread(self._set_status, f"Failed to download {name}: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _handle_ssh_download_request(self, name: str) -> None:
        # Joiner asked creator to download this file from the joiner,
        # via the creator's SFTP connection to the joiner.
        self.app.call_from_thread(self._set_status, f"Joiner asked to send {name}, downloading via SSH...")
        self._download(name)

    async def on_key(self, event) -> None:
        if event.key == "escape":
            try:
                self.tls.close()
            except Exception:
                pass
            self.app.pop_screen()
            return
        if event.key in ("up", "down") and not isinstance(self.focused, ListView):
            if handle_arrow_key(self, event.key):
                event.stop(); return
        focused = self.focused
        if event.key == "tab" and isinstance(focused, Input) and focused.id == "file_input":
            event.stop()
            candidates = complete(focused.value, self.cwd)
            if len(candidates) == 1:
                focused.value = candidates[0]
            elif candidates:
                self._set_status(f"Completions: {', '.join(candidates[:10])}")
