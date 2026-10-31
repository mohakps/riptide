"""Shared session screen, v5 file-manager rework.

After Create / Join, both sides land here. File direction is
chosen here, not by role: Send pushes a local file, Download
requests a remote file. Both actions work over the same TLS
session connection.

v5 changes, all in this screen plus core/file_select and
core/session:
- Send input: Tab completion now works for absolute paths
  (the old code dropped the directory for absolute prefixes),
  completing to the common prefix when several matches exist.
- Select box is a file manager: folders first, ``📁 name/``
  with no size or date, files with size and date. Enter on a
  folder goes into it, ``..`` or Backspace (in the list) goes
  up, Enter on a file toggles its selection.
- Colours: remaining files grey, selected files accent,
  hovered (highlighted) row pure white, even if selected.
- Download: the input accepts absolute paths on the peer,
  and nothing is sent until the peer presses Allow. Deny
  sends a download_denied message and no file bytes.
- Inputs are antigravity-cli style composers: a dim label
  above a bordered input box, with a hint below it, instead
  of a bare input with no context.
"""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, ProgressBar, Static

from ..core.file_select import (
    add_to_selection,
    common_prefix,
    complete,
    format_browser_row,
    format_bytes,
    list_browser_entries,
    list_cwd_files,
    parse_dropped_text,
    total_size,
)
from ..core.focus import focus_first, handle_arrow_key
from ..core.session import Session
from ..core.transfer import TransferProgress, format_bytes as fmt_bytes, format_eta
from ..theme import TAGLINES


def _build_file_item(path: Path, selected: bool) -> ListItem:
    display, size, mtime = format_browser_row(path)
    item = ListItem(
        Horizontal(
            Label(display, classes="file-name"),
            Label(size, classes="file-size"),
            Label(mtime, classes="file-mtime"),
            classes="file-row",
        ),
        classes="selected" if selected else "",
    )
    # Store the path on the item so selection does not depend on
    # list order after a refresh.
    item._riptide_path = path  # type: ignore[attr-defined]
    return item


class SessionScreen(Screen):
    def __init__(self, session: Session, role: str) -> None:
        super().__init__()
        self.session = session
        self.role = role
        self.cwd = session.cwd
        self.browser_dir = Path(session.cwd)
        self.selection: list[Path] = []
        self._transfer = TransferProgress(0)
        self._transfer_name = ""
        self._pending_downloads: list[tuple[str, str]] = []
        self._approve_btn: Button | None = None
        self._deny_btn: Button | None = None

    # -- file manager -------------------------------------------------
    def _browser_rows(self) -> list[Path]:
        rows: list[Path] = []
        if self.browser_dir.parent != self.browser_dir:
            rows.append(self.browser_dir.parent)
        rows.extend(list_browser_entries(self.browser_dir))
        return rows

    def _refresh_browser(self, keep_index: int | None = None) -> None:
        try:
            lst = self.query_one("#cwd_list", ListView)
        except Exception:
            return
        index = keep_index
        if index is None:
            try:
                index = lst.index
            except Exception:
                index = 0
        selected = set(self.selection)
        rows = self._browser_rows()
        lst.clear()
        for path in rows:
            is_parent = path == self.browser_dir.parent and path not in list_browser_entries(self.browser_dir)
            if is_parent:
                # The ".." row: folder icon, trailing slash, no size/date.
                item = ListItem(
                    Horizontal(
                        Label("📁 ../", classes="file-name"),
                        Label("", classes="file-size"),
                        Label("", classes="file-mtime"),
                        classes="file-row",
                    )
                )
                item._riptide_path = path  # type: ignore[attr-defined]
                item._riptide_parent = True  # type: ignore[attr-defined]
                lst.append(item)
            else:
                lst.append(_build_file_item(path, path in selected))
        try:
            if rows and index is not None:
                lst.index = max(0, min(index, len(rows) - 1))
        except Exception:
            pass
        try:
            self.query_one("#browser_path", Static).update(f"Folder: {self.browser_dir}")
        except Exception:
            pass

    def _go_up(self) -> None:
        if self.browser_dir.parent != self.browser_dir:
            self.browser_dir = self.browser_dir.parent
            self._refresh_browser(keep_index=0)

    def _go_into(self, path: Path) -> None:
        if path.is_dir():
            self.browser_dir = path
            self._refresh_browser(keep_index=0)

    # -- compose ------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"SESSION ({self.role.upper()}) with {self.session.peer_device or 'peer'}", classes="screen-title"),
            Static(TAGLINES["session"], classes="screen-desc"),
            Static("Status: connected", id="status"),
            Static(f"Folder: {self.browser_dir}", id="browser_path"),
            Horizontal(
                Label("NAME", classes="file-header-name"),
                Label("SIZE", classes="file-header-size"),
                Label("MODIFIED", classes="file-header-mtime"),
                classes="file-header-row",
            ),
            ListView(id="cwd_list"),
            Static("↑ Enter a folder to open it  •  Backspace in the list to go up  •  Enter a file to select it", classes="dim"),
            Vertical(
                Static("SEND FILE  ·  local path", classes="composer-label"),
                Input(placeholder="Type an absolute path, e.g. /home/user/notes.pdf, or a name in this folder…", id="file_input"),
                Static("Tab completes (including absolute paths)  •  Enter adds to selection", classes="composer-hint"),
                classes="composer",
            ),
            Static("Selected: none", id="selected"),
            Button("Send selected", id="send", classes="primary"),
            Vertical(
                Static("DOWNLOAD FROM PEER  ·  peer path", classes="composer-label"),
                Input(placeholder="Type a peer path, absolute or relative, e.g. /home/friend/report.pdf…", id="download_input"),
                Static("Enter asks the peer for approval  •  nothing is sent until they allow it", classes="composer-hint"),
                classes="composer",
            ),
            Static("", id="download_approval"),
            Button("Allow download", id="approve_download", classes="allow"),
            Button("Deny download", id="deny_download", classes="deny"),
            Button("Download remote file", id="download"),
            ProgressBar(total=100, id="bar"),
            Static("Speed: -  |  Transferred: -", id="stats"),
            Static("[↑/↓] Move   [Enter] Open folder / select file   [Tab] Complete path   [Backspace] Up a folder   [Esc] Leave session", classes="keymap-bar"),
        )

    def on_mount(self) -> None:
        self.session.on_file_received = lambda name, ok, reason: self.app.call_from_thread(self._on_received, name, ok, reason)
        self.session.on_ack = lambda name, ok, reason: self.app.call_from_thread(self._set_status, f"Received ack for {name}: {'verified' if ok else 'FAILED ' + reason}")
        self.session.on_error = lambda msg: self.app.call_from_thread(self._set_status, msg)
        self.session.on_progress = lambda name, received, total: self.app.call_from_thread(self._on_progress, name, received, total, "Receiving")
        self.session.on_download_ask = lambda name, rid: self.app.call_from_thread(self._on_download_ask, name, rid)
        self.session.on_download_denied = lambda name, rid: self.app.call_from_thread(self._set_status, f"Peer denied download of {name}")
        self.session.start()
        self._refresh_browser(keep_index=0)
        try:
            self._approve_btn = self.query_one("#approve_download", Button)
            self._deny_btn = self.query_one("#deny_download", Button)
        except Exception:
            pass
        self._set_download_approval_visible(False)
        focus_first(self)

    def _set_download_approval_visible(self, visible: bool) -> None:
        for btn in (self._approve_btn, self._deny_btn):
            if btn is not None:
                try:
                    btn.styles.display = "block" if visible else "none"
                except Exception:
                    pass

    def _show_next_download_approval(self) -> None:
        if not self._pending_downloads:
            try:
                self.query_one("#download_approval", Static).update("")
            except Exception:
                pass
            self._set_download_approval_visible(False)
            return
        name, _rid = self._pending_downloads[0]
        try:
            self.query_one("#download_approval", Static).update(f"Peer wants to download: {name}  —  Allow to send it, Deny to refuse.")
        except Exception:
            pass
        self._set_download_approval_visible(True)

    def _on_download_ask(self, name: str, request_id: str) -> None:
        self._pending_downloads.append((name, request_id))
        if len(self._pending_downloads) == 1:
            self._show_next_download_approval()
        else:
            self._set_status(f"Peer also wants to download: {name} (queued)")

    def _answer_download(self, allow: bool) -> None:
        if not self._pending_downloads:
            return
        name, rid = self._pending_downloads.pop(0)
        self._show_next_download_approval()
        # send_file runs in a thread so a large file does not block the UI.
        threading.Thread(target=lambda: self.session.respond_download(name, rid, allow), daemon=True).start()
        self._set_status(f"{'Allowed' if allow else 'Denied'} download of {name}")

    # -- status / progress --------------------------------------------
    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(f"Status: {text}")
        except Exception:
            pass

    def _on_received(self, name: str, ok: bool, reason: str) -> None:
        self._set_status(f"Received {name}: {'verified' if ok else 'FAILED ' + reason}")
        self._refresh_browser()

    def _on_progress(self, name: str, transferred: int, total: int, direction: str) -> None:
        if self._transfer.total != total or self._transfer_name != name:
            self._transfer = TransferProgress(total)
            self._transfer_name = name
        self._transfer.update(transferred)
        try:
            bar = self.query_one("#bar", ProgressBar)
            bar.progress = (transferred / total * 100) if total else 100
            speed = fmt_bytes(self._transfer.speed_ema) if self._transfer.speed_ema else "-"
            self.query_one("#stats", Static).update(
                f"Speed: {speed}/s  |  {direction}: {format_bytes(transferred)} / {format_bytes(total)}  ({name})  |  Remaining: {format_bytes(self._transfer.remaining)}  |  ETA: {format_eta(self._transfer.eta_seconds)}"
            )
        except Exception:
            pass

    def _refresh_selected(self) -> None:
        total = total_size(self.selection)
        names = ", ".join(p.name for p in self.selection) or "none"
        try:
            self.query_one("#selected", Static).update(f"Selected ({len(self.selection)}): {names}  |  Total: {format_bytes(total)}")
        except Exception:
            pass

    # -- input handling ------------------------------------------------
    def _apply_tab_completion(self, inp: Input) -> None:
        value = inp.value
        candidates = complete(value, self.browser_dir)
        if not candidates:
            self._set_status("No completion found.")
            return
        if len(candidates) == 1:
            inp.value = candidates[0]
            return
        prefix = common_prefix(candidates)
        if prefix and prefix != value and len(prefix) > len(value):
            inp.value = prefix
            return
        self._set_status(f"Completions: {', '.join(candidates[:10])}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "file_input":
            text = event.value.strip(); event.input.value = ""
            if text:
                # Resolve relative to the folder currently browsed,
                # not just the session start folder, so a typed name
                # matches what the file manager is showing.
                add_to_selection(self.selection, parse_dropped_text(text, self.browser_dir)); self._refresh_selected(); self._refresh_browser()
        elif event.input.id == "download_input":
            name = event.value.strip(); event.input.value = ""
            if name:
                self._download(name)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        try:
            item = event.list_view.highlighted_child
            path = getattr(item, "_riptide_path", None)
        except Exception:
            path = None
        if path is None:
            return
        if getattr(item, "_riptide_parent", False):
            self._go_up()
            return
        if path.is_dir():
            self._go_into(path)
            return
        # File: toggle selection, so a mistaken tap can be undone.
        if path in self.selection:
            self.selection.remove(path)
        else:
            add_to_selection(self.selection, [path])
        self._refresh_selected(); self._refresh_browser()

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
        elif event.button.id == "approve_download":
            self._answer_download(True)
        elif event.button.id == "deny_download":
            self._answer_download(False)
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
        files = list(self.selection); self.selection = []; self._refresh_selected(); self._refresh_browser()

        def worker():
            for path in files:
                self.app.call_from_thread(self._set_status, f"Sending {path.name}...")
                ok = self.session.send_file(path, on_progress=lambda n, s, t: self.app.call_from_thread(self._on_progress, n, s, t, "Sending"))
                self.app.call_from_thread(self._set_status, f"Sent {path.name}" if ok else f"Failed to send {path.name}")

        threading.Thread(target=worker, daemon=True).start()

    def _download(self, name: str) -> None:
        self._set_status(f"Waiting for peer approval for {name}...")
        ok = self.session.request_download(name, request_id=str(uuid.uuid4()))
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
        focused = self.focused
        if event.key == "backspace" and isinstance(focused, ListView):
            event.stop()
            self._go_up()
            return
        if event.key in ("up", "down") and not isinstance(focused, ListView):
            if handle_arrow_key(self, event.key):
                event.stop(); return
        if event.key == "tab" and isinstance(focused, Input) and focused.id == "file_input":
            event.stop()
            self._apply_tab_completion(focused)
