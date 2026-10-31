"""Shared session screen, used by both creator and joiner.

After Create / Join, both sides land here. File direction is chosen
here, not by role: Send pushes a local file, Download requests a
remote file. Both actions work over the same session connection.
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
from ..theme import HEADER_LINES


class SessionScreen(Screen):
    def __init__(self, session: Session, role: str) -> None:
        super().__init__()
        self.session = session
        self.role = role
        self.cwd = session.cwd
        self.selection: list[Path] = []

    def compose(self) -> ComposeResult:
        files = list_cwd_files(self.cwd)
        items = [ListItem(Label(f"{p.name}  ({format_bytes(p.stat().st_size)})")) for p in files]
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static(f"SESSION  ({self.role})  with {self.session.peer_device or 'peer'}", classes="accent"),
            Static("Status: connected", id="status"),
            ListView(*items, id="cwd_list"),
            Input(
                placeholder="Type a file name, Tab to complete, Enter to add. Paste dropped paths here.",
                id="file_input",
            ),
            Static("Selected: none", id="selected"),
            Button("Send selected", id="send"),
            Input(placeholder="Remote file name to download", id="download_input"),
            Button("Download remote file", id="download"),
            ProgressBar(total=100, id="bar"),
            Static("Speed: -  |  Sent: -", id="stats"),
            Button("Leave session", id="leave"),
            Static("Files you receive land in this folder. Files the other side requests come from this folder.", classes="dim"),
        )

    def on_mount(self) -> None:
        self.session.on_file_received = lambda name, ok, reason: self.app.call_from_thread(self._on_received, name, ok, reason)
        self.session.on_ack = lambda name, ok, reason: self.app.call_from_thread(self._set_status, f"Received ack for {name}: {'verified' if ok else 'FAILED ' + reason}")
        self.session.on_error = lambda msg: self.app.call_from_thread(self._set_status, msg)
        self.session.start()
        focus_first(self)

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(f"Status: {text}")
        except Exception:
            pass

    def _on_received(self, name: str, ok: bool, reason: str) -> None:
        self._set_status(f"Received {name}: {'verified' if ok else 'FAILED ' + reason}")
        # Refresh the local file list so a received file shows up.
        try:
            lst = self.query_one("#cwd_list", ListView)
            lst.clear()
            for p in list_cwd_files(self.cwd):
                lst.append(ListItem(Label(f"{p.name}  ({format_bytes(p.stat().st_size)})")))
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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "file_input":
            text = event.value.strip()
            event.input.value = ""
            if text:
                found = parse_dropped_text(text, self.cwd)
                add_to_selection(self.selection, found)
                self._refresh_selected()
        elif event.input.id == "download_input":
            name = event.value.strip()
            event.input.value = ""
            if name:
                self._download(name)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        files = list_cwd_files(self.cwd)
        try:
            chosen = files[event.list_view.index]
        except Exception:
            return
        add_to_selection(self.selection, [chosen])
        self._refresh_selected()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            self._send()
        elif event.button.id == "download":
            try:
                name = self.query_one("#download_input", Input).value.strip()
            except Exception:
                name = ""
            if name:
                self._download(name)
        elif event.button.id == "leave":
            try:
                self.session.close()
            except Exception:
                pass
            self.app.pop_screen()

    def _send(self) -> None:
        if not self.selection:
            self._set_status("Failed: select at least one file first.")
            return
        files = list(self.selection)
        self.selection = []
        self._refresh_selected()

        def worker():
            for path in files:
                self.app.call_from_thread(self._set_status, f"Sending {path.name}...")
                ok = self.session.send_file(path, on_progress=lambda n, s, t: self.app.call_from_thread(self._set_progress, n, s, t))
                self.app.call_from_thread(self._set_status, f"Sent {path.name}" if ok else f"Failed to send {path.name}")

        threading.Thread(target=worker, daemon=True).start()

    def _set_progress(self, name: str, sent: int, total: int) -> None:
        try:
            bar = self.query_one("#bar", ProgressBar)
            bar.progress = (sent / total * 100) if total else 100
            self.query_one("#stats", Static).update(f"Speed: -  |  Sent: {format_bytes(sent)} / {format_bytes(total)}  ({name})")
        except Exception:
            pass

    def _download(self, name: str) -> None:
        self._set_status(f"Requesting {name}...")
        ok = self.session.request_file(name)
        if not ok:
            self._set_status(f"Failed to request {name}")

    async def on_key(self, event) -> None:
        if event.key == "escape":
            try:
                self.session.close()
            except Exception:
                pass
            self.app.pop_screen()
            return
        if event.key in ("up", "down") and not isinstance(self.focused, ListView):
            if handle_arrow_key(self, event.key):
                event.stop()
                return
        focused = self.focused
        if event.key == "tab" and isinstance(focused, Input) and focused.id == "file_input":
            event.stop()
            candidates = complete(focused.value, self.cwd)
            if len(candidates) == 1:
                focused.value = candidates[0]
            elif candidates:
                self._set_status(f"Completions: {', '.join(candidates[:10])}")
