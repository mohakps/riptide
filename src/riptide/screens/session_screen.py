"""Redesigned session screen for user-friendly PC-to-PC file transfer.

Features:
- Header: HOST banner in larger block font; client name with hostname/IP
  and connection indicator (Connected ● green, Connecting ○, Disconnected ⊗ red).
- File Manager: Current folder at top of box with clear separator below it;
  expanded height (16 rows); live typing search filter; spacebar selection;
  pure white focused row highlight.
- Send Flow: Enter sends selected files immediately without a button;
  selected files listed line-by-line with full absolute path in accent red;
  summary header in shades of white and accent colors.
- Download Flow: Download button removed; Enter initiates request from input;
  download input disabled while files are selected to send.
- Progress: Full-width progress bar showing overall batch progress;
  evenly spaced metrics on line 2; current file and [sent / total size] on line 3,
  with file name truncated to fit in one line.
- Layout: Full page vertical scroll container with footer docked at bottom,
  footer items evenly spaced with shortcut keys in [].
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, ProgressBar, Static

from ..core.file_select import (
    add_to_selection,
    format_browser_row,
    format_bytes,
    list_browser_entries,
    total_size,
)
from ..core.focus import focus_first, handle_arrow_key
from ..core.session import Session
from ..core.transfer import TransferProgress, format_bytes as fmt_bytes, format_eta
from ..theme import BANNER_CLIENT, BANNER_HOST


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
    item._riptide_path = path  # type: ignore[attr-defined]
    return item


def _truncate_filename(name: str, max_chars: int = 50) -> str:
    if len(name) <= max_chars:
        return name
    if max_chars <= 6:
        return name[:max_chars]
    prefix_len = (max_chars - 3) * 2 // 3
    suffix_len = (max_chars - 3) - prefix_len
    return f"{name[:prefix_len]}...{name[-suffix_len:]}"


class SessionScreen(Screen):
    def __init__(self, session: Session, role: str) -> None:
        super().__init__()
        self.session = session
        self.role = role
        self.cwd = session.cwd
        self.browser_dir = Path(session.cwd)
        self.selection: list[Path] = []
        self._search_query: str = ""
        self._connection_state: str = "connected"
        self._transfer = TransferProgress(0)
        self._overall_transfer = TransferProgress(0)
        self._overall_total: int = 0
        self._transfer_name = ""
        self._pending_downloads: list[tuple[str, str]] = []
        self._approve_btn: Button | None = None
        self._deny_btn: Button | None = None

    # -- header & connection display ----------------------------------
    def _get_peer_address(self) -> str:
        try:
            if self.session and self.session.sock:
                peername = self.session.sock.getpeername()
                if peername and isinstance(peername, tuple):
                    return str(peername[0])
        except Exception:
            pass
        return getattr(self.session, "peer_host", "") or ""

    def _format_client_info(self) -> str:
        peer_name = self.session.peer_device or "peer"
        peer_addr = self._get_peer_address()
        peer_label = "Client" if self.role in ("creator", "host") else "Host"
        if peer_addr and peer_addr != peer_name:
            return f"{peer_label}: [bold #FFFFFF]{peer_name}[/] [dim]({peer_addr})[/]"
        return f"{peer_label}: [bold #FFFFFF]{peer_name}[/]"

    def _format_status_indicator(self) -> str:
        if self._connection_state == "connected":
            return "[#E8E8E8]Connected[/] [bold #78DC8C]●[/]"
        elif self._connection_state == "connecting":
            return "[#E8E8E8]Connecting[/] [bold #FFD166]○[/]"
        else:
            return "[#E8E8E8]Disconnected[/] [bold #FF6B6B]⊗[/]"

    def _update_header(self) -> None:
        try:
            self.query_one("#peer_client_label", Static).update(self._format_client_info())
            self.query_one("#peer_status_label", Static).update(self._format_status_indicator())
        except Exception:
            pass

    # -- file manager -------------------------------------------------
    def _browser_rows(self) -> list[Path]:
        all_entries = list_browser_entries(self.browser_dir)
        if self._search_query:
            q = self._search_query.lower()
            return [p for p in all_entries if q in p.name.lower()]

        rows: list[Path] = []
        if self.browser_dir.parent != self.browser_dir:
            rows.append(self.browser_dir.parent)
        rows.extend(all_entries)
        return rows

    def _refresh_browser(self, keep_index: int | None = None, auto_first: bool = False) -> None:
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
        # Auto-select the first real file/folder on directory change,
        # not the ".." parent row. When searching, there is no parent
        # row, so the first filtered row is index 0.
        if auto_first and rows:
            if self._search_query:
                index = 0
            elif rows[0] == self.browser_dir.parent and len(rows) > 1:
                index = 1
            else:
                index = 0
        lst.clear()
        for path in rows:
            is_parent = path == self.browser_dir.parent and path not in list_browser_entries(self.browser_dir)
            if is_parent:
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
        self._update_folder_header()

    def _update_folder_header(self) -> None:
        try:
            self.query_one("#browser_path", Static).update(f"📁 {self.browser_dir}")
            # Find label is always visible at the right corner of the
            # file-selection box header, with the typed text in white
            # and a blinking cursor, even when the query is empty.
            cursor = "▌" if getattr(self, "_find_cursor_visible", True) else " "
            self.query_one("#browser_search_indicator", Static).update(
                f"[#E8E8E8]Find:[/] [bold #FFFFFF]{self._search_query}[/][bold #FF6B6B]{cursor}[/]"
            )
        except Exception:
            pass

    def _toggle_find_cursor(self) -> None:
        self._find_cursor_visible = not getattr(self, "_find_cursor_visible", True)
        self._update_folder_header()

    def _go_up(self) -> None:
        if self.browser_dir.parent != self.browser_dir:
            self.browser_dir = self.browser_dir.parent
            self._search_query = ""
            self._refresh_browser(auto_first=True)

    def _go_into(self, path: Path) -> None:
        if path.is_dir():
            self.browser_dir = path
            self._search_query = ""
            self._refresh_browser(auto_first=True)

    # -- compose ------------------------------------------------------
    def compose(self) -> ComposeResult:
        banner = BANNER_HOST if self.role in ("creator", "host") else BANNER_CLIENT
        yield VerticalScroll(
            Horizontal(
                Static(banner, classes="session-header-text", id="session_host_title"),
                Vertical(
                    Static(self._format_client_info(), id="peer_client_label"),
                    Static(self._format_status_indicator(), id="peer_status_label"),
                    id="session_peer_info",
                ),
                id="session_header_row",
            ),
            Vertical(
                Horizontal(
                    Static(f"📁 {self.browser_dir}", id="browser_path"),
                    Static("Find: ▌", id="browser_search_indicator"),
                    id="browser_header_row",
                ),
                Static("─" * 200, id="browser_separator"),
                Horizontal(
                    Label("NAME", classes="file-header-name"),
                    Label("SIZE", classes="file-header-size"),
                    Label("MODIFIED", classes="file-header-mtime"),
                    classes="file-header-row",
                ),
                ListView(id="cwd_list"),
                id="browser_box",
            ),
            Vertical(
                Static(self._format_selected_header(), id="selected_header"),
                Vertical(id="selected_files_list"),
                id="selected_files_section",
            ),
            Vertical(
                Static("DOWNLOAD FROM PEER  ·  peer path", classes="composer-label"),
                Input(
                    placeholder="Type a peer path, absolute or relative, e.g. /home/friend/report.pdf…",
                    id="download_input",
                ),
                Static("Enter asks peer for approval  •  Disabled when files are selected to send", classes="composer-hint"),
                classes="composer",
                id="download_composer",
            ),
            Static("", id="download_approval"),
            Button("Allow download", id="approve_download", classes="allow"),
            Button("Deny download", id="deny_download", classes="deny"),
            Vertical(
                ProgressBar(total=100, id="bar"),
                Horizontal(
                    Label("Speed: -", id="metric_speed", classes="progress-metric progress-metric-left"),
                    Label("Transferred: 0 B / 0 B", id="metric_transferred", classes="progress-metric"),
                    Label("Remaining: 0 B", id="metric_remaining", classes="progress-metric"),
                    Label("ETA: -", id="metric_eta", classes="progress-metric progress-metric-right"),
                    id="progress_metrics_row",
                ),
                Horizontal(
                    Label("", id="progress_file_name"),
                    Label("", id="progress_file_size"),
                    id="progress_file_row",
                ),
                id="progress_section",
            ),
            id="session_scroll",
            can_focus=False,
        )
        yield Horizontal(
            Label(r"[bold #E8E8E8]\[↑/↓][/] [dim #FFFFFF]Move[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E8E8E8]\[Space][/] [dim #FFFFFF]Open/Select[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[0][/] [dim #FFFFFF]Deselect all[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Send[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Backspace][/] [dim #FFFFFF]Erase/Prev.Directory[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Tab][/] [dim #FFFFFF]Cycle UI[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Esc][/] [dim #FFFFFF]Leave[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
        )

    def on_mount(self) -> None:
        self.session.on_file_received = lambda name, ok, reason: self.app.call_from_thread(self._on_received, name, ok, reason)
        self.session.on_ack = lambda name, ok, reason: self.app.call_from_thread(
            self._set_status, f"Received ack for {name}: {'verified' if ok else 'FAILED ' + reason}"
        )
        self.session.on_error = lambda msg: self.app.call_from_thread(self._on_session_error, msg)
        self.session.on_progress = lambda name, received, total: self.app.call_from_thread(
            self._on_progress, name, received, total, received, total, "Receiving"
        )
        self.session.on_download_ask = lambda name, rid: self.app.call_from_thread(self._on_download_ask, name, rid)
        self.session.on_download_denied = lambda name, rid: self.app.call_from_thread(self._set_status, f"Peer denied download of {name}")
        self.session.start()
        self._find_cursor_visible = True
        try:
            self.set_interval(0.5, self._toggle_find_cursor)
        except Exception:
            pass
        self._refresh_browser(auto_first=True)
        self._refresh_selected()
        try:
            self._approve_btn = self.query_one("#approve_download", Button)
            self._deny_btn = self.query_one("#deny_download", Button)
        except Exception:
            pass
        self._set_download_approval_visible(False)
        self._set_progress_visible(False)
        self._update_header()
        focus_first(self)

    def _on_session_error(self, msg: str) -> None:
        self._connection_state = "disconnected"
        self._set_status(msg)
        self._update_header()

    def _set_download_approval_visible(self, visible: bool) -> None:
        for btn in (self._approve_btn, self._deny_btn):
            if btn is not None:
                try:
                    btn.styles.display = "block" if visible else "none"
                except Exception:
                    pass

    def _set_progress_visible(self, visible: bool) -> None:
        try:
            self.query_one("#progress_section", Vertical).styles.display = "block" if visible else "none"
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
            self.query_one("#download_approval", Static).update(
                f"Peer wants to download: {name}  —  Allow to send it, Deny to refuse."
            )
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
        threading.Thread(target=lambda: self.session.respond_download(name, rid, allow), daemon=True).start()
        self._set_status(f"{'Allowed' if allow else 'Denied'} download of {name}")

    # -- status / progress --------------------------------------------
    def _set_status(self, text: str) -> None:
        # The Status subheader was removed from the page. Connection
        # state is still shown in the header (Connected ● / etc.),
        # and transfer progress is shown in the progress section.
        # Keep the last message in memory for debugging/tests, and
        # do not crash if the old #status widget is gone.
        self._last_status = text
        try:
            self.query_one("#status", Static).update(f"Status: {text}")
        except Exception:
            pass

    def _on_received(self, name: str, ok: bool, reason: str) -> None:
        self._set_progress_visible(False)
        self._set_status(f"Received {name}: {'verified' if ok else 'FAILED ' + reason}")
        self._refresh_browser()
    def _on_progress(
        self,
        name: str,
        file_sent: int,
        file_total: int,
        batch_sent: int,
        batch_total: int,
        direction: str,
    ) -> None:
        self._set_progress_visible(True)
        if self._overall_transfer.total != batch_total:
            self._overall_transfer = TransferProgress(batch_total)
        self._overall_transfer.update(batch_sent)

        try:
            bar = self.query_one("#bar", ProgressBar)
            bar.progress = (batch_sent / batch_total * 100) if batch_total else 100

            speed = fmt_bytes(self._overall_transfer.speed_ema) if self._overall_transfer.speed_ema else "-"
            remaining = fmt_bytes(self._overall_transfer.remaining)
            eta = format_eta(self._overall_transfer.eta_seconds)

            self.query_one("#metric_speed", Label).update(f"Speed: {speed}/s")
            self.query_one("#metric_transferred", Label).update(
                f"{direction}: {format_bytes(batch_sent)} / {format_bytes(batch_total)}"
            )
            self.query_one("#metric_remaining", Label).update(f"Remaining: {remaining}")
            self.query_one("#metric_eta", Label).update(f"ETA: {eta}")

            trunc_name = _truncate_filename(name, 50)
            self.query_one("#progress_file_name", Label).update(f"{direction}: {trunc_name}")
            self.query_one("#progress_file_size", Label).update(
                f"[{format_bytes(file_sent)} / {format_bytes(file_total)}]"
            )
        except Exception:
            pass

    def _format_selected_header(self) -> str:
        if not self.selection:
            return "[#71717A]Selected Files (0): None[/]  [dim]·  [Space] to select file  ·  [Enter] to send[/]"
        total = total_size(self.selection)
        return (
            f"[bold #FFFFFF]Selected Files ({len(self.selection)})[/]  "
            f"[#71717A]·[/]  [#E8E8E8]Total: {format_bytes(total)}[/]  "
        )

    def _refresh_selected(self) -> None:
        try:
            self.query_one("#selected_header", Static).update(self._format_selected_header())
            selected_container = self.query_one("#selected_files_list", Vertical)
            selected_container.remove_children()
            for p in self.selection:
                size_str = format_bytes(p.stat().st_size) if p.is_file() else ""
                dim_size = f"  [dim #FFFFFF]({size_str})[/]" if size_str else ""
                selected_container.mount(
                    Static(f"[bold #FF6B6B]• {p.resolve()}[/]{dim_size}", classes="selected-file-item")
                )
        except Exception:
            pass

        # Requirement 6: download input cannot be accessed when 'send' files are selected
        is_sending = bool(self.selection)
        try:
            dl_input = self.query_one("#download_input", Input)
            dl_input.disabled = is_sending
            dl_composer = self.query_one("#download_composer", Vertical)
            if is_sending:
                dl_composer.add_class("disabled")
                if self.focused == dl_input:
                    self.query_one("#cwd_list", ListView).focus()
            else:
                dl_composer.remove_class("disabled")
        except Exception:
            pass

    # -- input handling ------------------------------------------------
    # The send file input field was removed: files are now selected
    # only from the file manager box, with Space, and sent with Enter.
    # Tab completion for absolute paths remains in core/file_select
    # for any future input, but is not wired to a send input here.
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "download_input":
            # Requirement 6: Enter key initiates the request
            name = event.value.strip()
            event.input.value = ""
            if name:
                self._download(name)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.selection:
            self._send()
        else:
            self._set_status("Select files first with Space, then press Enter to send.")
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve_download":
            self._answer_download(True)
        elif event.button.id == "deny_download":
            self._answer_download(False)
        elif event.button.id == "leave":
            self._leave_session()

    def _leave_session(self) -> None:
        self._connection_state = "disconnected"
        self._update_header()
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
        self._refresh_browser()

        total_batch_size = sum(p.stat().st_size for p in files if p.is_file())
        self._overall_total = total_batch_size
        self._overall_transfer = TransferProgress(total_batch_size)

        def worker():
            self.app.call_from_thread(self._set_progress_visible, True)
            completed_bytes = 0
            for path in files:
                file_size = path.stat().st_size if path.is_file() else 0
                self.app.call_from_thread(self._set_status, f"Sending {path.name}...")
                def on_file_prog(name, sent, single_total):
                    batch_sent = completed_bytes + sent
                    self.app.call_from_thread(
                        self._on_progress,
                        name, sent, single_total, batch_sent, total_batch_size, "Sending"
                    )

                ok = self.session.send_file(path, on_progress=on_file_prog)
                completed_bytes += file_size
                self.app.call_from_thread(
                    self._set_status,
                    f"Sent {path.name}" if ok else f"Failed to send {path.name}",
                )
            self.app.call_from_thread(self._set_progress_visible, False)

        threading.Thread(target=worker, daemon=True).start()
    def _download(self, name: str) -> None:
        if self.selection:
            self._set_status("Cannot download while files are selected to send. Send or unselect them first.")
            return
        self._set_status(f"Waiting for peer approval for {name}...")
        ok = self.session.request_download(name, request_id=str(uuid.uuid4()))
        if not ok:
            self._set_status(f"Failed to request {name}")

    async def on_key(self, event) -> None:
        if event.key == "escape":
            if self._search_query:
                event.stop()
                self._search_query = ""
                self._refresh_browser(keep_index=0)
                return
            self._leave_session()
            return

        focused = self.focused

        # 0: deselect all files. Not when typing in an input, where
        # 0 is a digit in the path.
        if event.key == "0" and not isinstance(focused, Input):
            event.stop()
            self.selection = []
            self._refresh_selected()
            self._refresh_browser()
            return

        # Spacebar: open folders (or parent ..) or select/toggle files
        if event.key == "space" and isinstance(focused, ListView):
            event.stop()
            try:
                item = self.query_one("#cwd_list", ListView).highlighted_child
                path = getattr(item, "_riptide_path", None)
            except Exception:
                path = None
            if path is not None:
                if getattr(item, "_riptide_parent", False):
                    self._search_query = ""
                    self._go_up()
                    return
                if path.is_dir():
                    self._search_query = ""
                    self._go_into(path)
                    return
                if path in self.selection:
                    self.selection.remove(path)
                else:
                    add_to_selection(self.selection, [path])
                self._refresh_selected()
                self._refresh_browser()
            return

        # Enter key sends files
        if event.key == "enter":
            if isinstance(focused, Input) and focused.value.strip():
                return
            event.stop()
            if self.selection:
                self._send()
            else:
                self._set_status("Select files first with Space, then press Enter to send.")
            return

        # Tab cycles between UI elements
        if event.key == "tab":
            event.stop()
            self.focus_next()
            return
        if event.key == "shift+tab":
            event.stop()
            self.focus_previous()
            return
        # Backspace handling in ListView: search backspace or go up
        if event.key == "backspace" and isinstance(focused, ListView):
            event.stop()
            if self._search_query:
                self._search_query = self._search_query[:-1]
                self._refresh_browser(keep_index=0)
            else:
                self._go_up()
            return

        # Requirement 4: Typing searches the files when focused on ListView
        if isinstance(focused, ListView):
            if event.character and event.character.isprintable() and event.key not in ("space", "enter", "tab"):
                event.stop()
                self._search_query += event.character
                self._refresh_browser(keep_index=0)
                return

        # Arrow key navigation between widgets
        if event.key in ("up", "down") and not isinstance(focused, ListView):
            if handle_arrow_key(self, event.key):
                event.stop()
                return

