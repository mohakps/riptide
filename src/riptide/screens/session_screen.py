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

import ipaddress
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


def _build_file_item(path: Path, selected: bool, is_focused: bool = False, max_name_chars: int | None = None) -> ListItem:
    display, size, mtime = format_browser_row(path)
    if max_name_chars is not None:
        display = _truncate_filename(display, max_name_chars)
    item = ListItem(
        Horizontal(
            Label("❯ " if is_focused else "  ", classes="file-pointer"),
            Label(display, classes="file-name"),
            Label(size, classes="file-size"),
            Label(mtime, classes="file-mtime"),
            classes="file-row",
        ),
        classes="selected" if selected else "",
    )
    item._riptide_path = path  # type: ignore[attr-defined]
    return item


def _cell_len(text: str) -> int:
    # Terminal cell width, not character count. 📁 is 1 character
    # but 2 cells wide, which is exactly why folder names broke:
    # a folder display truncated to 32 characters was 33 cells
    # wide, wrapped to a second line, and the 1-line file row
    # clipped that line. Rich is already a Textual dependency.
    try:
        from rich.cells import cell_len

        return cell_len(text)
    except Exception:
        return len(text)


def _take_cells(text: str, max_cells: int, from_end: bool = False) -> str:
    # Take characters whose total cell width fits in max_cells,
    # without splitting a wide character in half.
    if not from_end:
        out: list[str] = []
        used = 0
        for ch in text:
            width = _cell_len(ch)
            if used + width > max_cells:
                break
            out.append(ch)
            used += width
        return "".join(out)
    out_rev: list[str] = []
    used = 0
    for ch in reversed(text):
        width = _cell_len(ch)
        if used + width > max_cells:
            break
        out_rev.append(ch)
        used += width
    return "".join(reversed(out_rev))


def _truncate_filename(name: str, max_chars: int = 50) -> str:
    # max_chars is really max terminal cells, not characters.
    # Every caller passes a column width in cells, so a wide
    # character such as 📁 must count as 2, or the truncated
    # name still overflows its column and wraps or clips.
    if _cell_len(name) <= max_chars:
        return name
    if max_chars <= 6:
        return _take_cells(name, max_chars)
    prefix_cells = (max_chars - 3) * 2 // 3
    suffix_cells = (max_chars - 3) - prefix_cells
    return f"{_take_cells(name, prefix_cells)}...{_take_cells(name, suffix_cells, from_end=True)}"


def _strip_surrounding_quotes(text: str) -> str:
    """Strip double quotes at the start and end of a pasted path.

    Terminals and file managers often paste a path as
    "C:\\Users\\...\\file.pdf" or "/home/user/file.pdf", quotes
    included. A path with those quotes would not be found, so
    remove paired quotes, and also a lone leading or trailing
    quote, then any surrounding whitespace again."""
    text = text.strip()
    while len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1].strip()
    return text.strip('"').strip()

def is_ip_address(text: str) -> bool:
    if not text:
        return False
    cleaned = text.strip("[]").split("%")[0]
    try:
        ipaddress.ip_address(cleaned)
        return True
    except ValueError:
        return False


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
        self._transfer_active: bool = False
        self._progress_visible: bool = False
        self._complete_timer = None
        self._complete_message_kind: str | None = None
        self._received_files: list[str] = []
        self._last_received_at: float = 0.0

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
        peer_name = getattr(self.session, "peer_device", "") or ""
        peer_addr = self._get_peer_address()
        peer_label = "Client" if self.role in ("creator", "host") else "Host"
        peer_host = getattr(self.session, "peer_host", "") or ""

        # Display hostname if connection was made using hostname, else show IP
        if peer_host and not is_ip_address(peer_host):
            display_target = peer_host
        else:
            display_target = peer_addr or peer_host or "unknown"

        if peer_name and peer_name != display_target:
            return f"{peer_label}: [bold #FFFFFF]{peer_name}[/] [dim]({display_target})[/]"
        return f"{peer_label}: [bold #FFFFFF]{display_target}[/]"

    def _format_status_indicator(self) -> str:
        if self._connection_state == "connected":
            return "[bold #78DC8C]●[/] [#E8E8E8]Connected[/]"
        elif self._connection_state == "connecting":
            return "[bold #FFD166]○[/] [#E8E8E8]Connecting[/]"
        else:
            return "[bold #FF6B6B]⊗[/] [#E8E8E8]Disconnected[/] "

    def _update_header(self) -> None:
        try:
            self.query_one("#peer_client_label", Static).update(self._format_client_info())
            self.query_one("#peer_status_label", Static).update(self._format_status_indicator())
        except Exception:
            pass

    def _screen_width(self) -> int:
        # Full terminal width. Screen padding is 1 2, so content
        # width is screen width minus 4. Fall back to 80 when the
        # screen is not mounted yet, for example in unit tests
        # that call helpers before mounting.
        try:
            width = self.size.width
            if width:
                return int(width)
        except Exception:
            pass
        try:
            width = self.app.screen.size.width
            if width:
                return int(width)
        except Exception:
            pass
        return 80

    def _content_width(self) -> int:
        return max(20, self._screen_width() - 4)

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
        resolved_idx = max(0, min(index, len(rows) - 1)) if (rows and index is not None) else 0
        # File row: pointer 2 + name 1fr + size 12 + mtime 22, inside
        # the browser box (border 2 + padding 2). If the name is
        # left at full length, the 1fr column collapses to 0 on a
        # narrow window and the name is hidden completely. Truncate
        # it to the width that is actually available, with ... .
        name_max = max(12, self._content_width() - 4 - 36)
        for idx, path in enumerate(rows):
            is_parent = path == self.browser_dir.parent and path not in list_browser_entries(self.browser_dir)
            is_focused = (idx == resolved_idx)
            if is_parent:
                item = ListItem(
                    Horizontal(
                        Label("❯ " if is_focused else "  ", classes="file-pointer"),
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
                lst.append(_build_file_item(path, path in selected, is_focused=is_focused, max_name_chars=name_max))
        try:
            if rows and index is not None:
                lst.index = max(0, min(index, len(rows) - 1))
        except Exception:
            pass
        self._update_folder_header()

    def _update_folder_header(self) -> None:
        try:
            # Reserve room for the Find label at the right end, so
            # a long folder path is truncated with ... instead of
            # pushing the Find label off, or collapsing to nothing.
            find_width = len(f"Find: {self._search_query}▌") + 1
            path_max = max(12, self._content_width() - find_width - 3)
            trunc_dir = _truncate_filename(str(self.browser_dir), path_max)
            self.query_one("#browser_path", Static).update(f"📁 {trunc_dir}")
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
                    Label("  ", classes="file-header-pointer"),
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
                Static("DOWNLOAD FROM PEER", classes="composer-label"),
                Input(
                    placeholder="Peer file path to download, e.g. /home/friend/report.pdf…",
                    id="download_input",
                ),
                Static("", id="download_denied_message", classes="download-denied-message"),
                classes="composer",
                id="download_composer",
            ),
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
                Static("", id="transfer_complete_message"),
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
        yield Vertical(
            Vertical(
                Static("📥  DOWNLOAD REQUEST", id="download_modal_title"),
                Static("", id="download_approval"),
                Horizontal(
                    Button("Accept", id="approve_download", classes="allow"),
                    Button("Deny", id="deny_download", classes="deny"),
                    id="download_modal_actions",
                ),
                Static(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Accept[/]    [bold #E8E8E8]\[Backspace][/] [dim #FFFFFF]Deny[/]", id="download_modal_footer"),
                id="download_modal_card",
            ),
            id="download_modal_overlay",
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
        self.session.on_download_denied = lambda name, rid: self.app.call_from_thread(self._on_download_denied, name, rid)
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
        try:
            overlay = self.query_one("#download_modal_overlay", Vertical)
            if visible:
                overlay.add_class("active")
                overlay.styles.display = "block"
                if self._approve_btn:
                    self._approve_btn.focus()
            else:
                overlay.remove_class("active")
                overlay.styles.display = "none"
        except Exception:
            pass
        for btn in (self._approve_btn, self._deny_btn):
            if btn is not None:
                try:
                    btn.styles.display = "block" if visible else "none"
                except Exception:
                    pass

    def _update_download_composer(self) -> None:
        # Download composer is hidden completely while any file is
        # selected to send, or while a transfer is in progress
        # (progress bar visible, sending or receiving). It returns
        # when neither applies.
        hidden = bool(self.selection) or self._transfer_active or self._progress_visible
        try:
            dl_input = self.query_one("#download_input", Input)
            dl_input.disabled = hidden
            dl_composer = self.query_one("#download_composer", Vertical)
            if hidden:
                dl_composer.add_class("disabled")
                dl_composer.styles.display = "none"
                if self.focused == dl_input:
                    self.query_one("#cwd_list", ListView).focus()
            else:
                dl_composer.remove_class("disabled")
                dl_composer.styles.display = "block"
        except Exception:
            pass

    def _cancel_complete_timer(self) -> None:
        try:
            if self._complete_timer is not None:
                self._complete_timer.stop()
        except Exception:
            pass
        self._complete_timer = None

    def _hide_transfer_complete(self) -> None:
        # Only the Sent message auto-hides. A Received message stays
        # until the next transfer, so a list of files can be read.
        if self._complete_message_kind != "sent":
            return
        if self._transfer_active or self._progress_visible:
            return
        self._complete_timer = None
        self._complete_message_kind = None
        try:
            self.query_one("#transfer_complete_message", Static).styles.display = "none"
            self.query_one("#progress_section", Vertical).styles.display = "none"
        except Exception:
            pass

    def _set_progress_visible(self, visible: bool) -> None:
        self._progress_visible = visible
        if visible:
            # A new transfer replaces any previous completion message,
            # and must not be hidden by an old Sent-message timer.
            self._cancel_complete_timer()
            self._complete_message_kind = None
        try:
            section = self.query_one("#progress_section", Vertical)
            section.styles.display = "block" if visible else "none"
            if visible:
                self.query_one("#transfer_complete_message", Static).styles.display = "none"
                self.query_one("#bar", ProgressBar).styles.display = "block"
                self.query_one("#progress_metrics_row", Horizontal).styles.display = "block"
                self.query_one("#progress_file_row", Horizontal).styles.display = "block"
        except Exception:
            pass
        self._update_download_composer()

    def _show_transfer_complete(self, sent_count: int, failed_count: int = 0) -> None:
        # In place of the progress bar, at the bottom of the page:
        # the progress section stays visible, but the bar, metrics
        # and file row are hidden and only the green statement shows.
        # It goes away after 5 seconds.
        try:
            section = self.query_one("#progress_section", Vertical)
            section.styles.display = "block"
            self.query_one("#bar", ProgressBar).styles.display = "none"
            self.query_one("#progress_metrics_row", Horizontal).styles.display = "none"
            self.query_one("#progress_file_row", Horizontal).styles.display = "none"
            noun = "file" if sent_count == 1 else "files"
            text = f"Sent {sent_count} {noun} successfully."
            if failed_count:
                failed_noun = "file" if failed_count == 1 else "files"
                text = f"Sent {sent_count} {noun} successfully, {failed_count} {failed_noun} failed."
            msg = self.query_one("#transfer_complete_message", Static)
            msg.update(text)
            msg.styles.display = "block"
        except Exception:
            pass
        self._complete_message_kind = "sent"
        self._cancel_complete_timer()
        try:
            self._complete_timer = self.set_timer(5, self._hide_transfer_complete)
        except Exception:
            self._complete_timer = None

    def _show_received_message(self) -> None:
        # Receiver side, in the same place as the Sent message.
        # One file: Received file "name" successfully.
        # Several files: Received N files, then one file per line.
        # No 5-second timer here, so a list can be read and scrolled.
        # The message lives inside the page's VerticalScroll, so a
        # long list scrolls with the page.
        if not self._received_files:
            return
        try:
            section = self.query_one("#progress_section", Vertical)
            section.styles.display = "block"
            self.query_one("#bar", ProgressBar).styles.display = "none"
            self.query_one("#progress_metrics_row", Horizontal).styles.display = "none"
            self.query_one("#progress_file_row", Horizontal).styles.display = "none"
            content_width = self._content_width()
            if len(self._received_files) == 1:
                # 'Received file "' + '" successfully.' = 30 chars
                # around the name, so the name itself must fit in
                # the rest, with ... if it does not.
                trunc_name = _truncate_filename(self._received_files[0], max(12, content_width - 30))
                text = f'Received file "{trunc_name}" successfully.'
            else:
                lines = [f"Received {len(self._received_files)} files:"]
                for name in self._received_files:
                    trunc_name = _truncate_filename(name, max(12, content_width - 2))
                    lines.append(f"• {trunc_name}")
                text = "\n".join(lines)
            msg = self.query_one("#transfer_complete_message", Static)
            msg.update(text)
            msg.styles.display = "block"
        except Exception:
            pass
        self._complete_message_kind = "received"
        self._cancel_complete_timer()
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
            # Modal card is 60 wide with padding 1 2, so its content
            # is 56 wide, or less on a window narrower than the card.
            card_content = max(12, min(56, self._screen_width() - 8))
            trunc_name = _truncate_filename(name, card_content)
            self.query_one("#download_approval", Static).update(
                f"Peer wants to download:\n[bold #FFFFFF]{trunc_name}[/]\n\n"
                f"[dim #A1A1AA]Allow to send it, Deny to refuse.[/]"
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
        if allow:
            # Approved download, sent in a worker thread with progress,
            # so the approver side gets the same progress bar and
            # Sent message as a normal send. Previously respond_download
            # sent with no progress callback, so the approver saw nothing.
            self._received_files = []
            threading.Thread(target=lambda: self._send_approved_download(name, rid), daemon=True).start()
        else:
            threading.Thread(target=lambda: self.session.respond_download(name, rid, False), daemon=True).start()
        self._set_status(f"{'Allowed' if allow else 'Denied'} download of {name}")

    def _send_approved_download(self, name: str, request_id: str) -> None:
        # Resolve the path the same way Session.respond_download does,
        # so the progress batch total matches the file being sent.
        path = Path(name).expanduser()
        if not path.is_absolute():
            path = self.session.cwd / path
        total = path.stat().st_size if path.is_file() else 0
        self._transfer_active = True
        self.app.call_from_thread(self._set_progress_visible, True)

        def on_file_prog(sent_name: str, sent: int, single_total: int) -> None:
            self.app.call_from_thread(
                self._on_progress, sent_name, sent, single_total, sent, total, "Sending"
            )

        ok = self.session.respond_download(name, request_id, True, on_progress=on_file_prog)
        self.app.call_from_thread(self._finish_send, 1 if ok else 0, 0 if ok else 1)

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
        if not ok:
            return
        # Batch received files together: a sender sends files
        # back to back, so a new batch is a gap of 10 seconds or
        # more since the last received file, or a user-started
        # send or download request, which clears the list below.
        now = time.monotonic()
        if self._last_received_at and now - self._last_received_at > 10:
            self._received_files = []
        self._last_received_at = now
        if name not in self._received_files:
            self._received_files.append(name)
        self._show_received_message()
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

            size_text = f"[{format_bytes(file_sent)} / {format_bytes(file_total)}]"
            # Dynamic, not a fixed 50: the name label is 1fr and
            # the size label is auto, so the name must fit in
            # content width minus the size label, or it is clipped
            # or, on a narrow window, collapses to nothing.
            prefix = f"{direction}: "
            name_max = max(12, self._content_width() - len(prefix) - len(size_text))
            trunc_name = _truncate_filename(name, name_max)
            self.query_one("#progress_file_name", Label).update(f"{prefix}{trunc_name}")
            self.query_one("#progress_file_size", Label).update(size_text)
        except Exception:
            pass

    def _format_selected_header(self) -> str:
        if not self.selection:
            return r"[#D7D7D7]Selected Files (0)[/] [dim]·[/] [#FFFFFF]\[Space][/][#D7D7D7] to select file[/]"
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
                # Full absolute paths are the longest strings on the
                # page. Truncate them to the width available, with
                # ..., keeping the start and the file name at the end.
                size_plain_len = len(size_str) + 4 if size_str else 0
                path_max = max(12, self._content_width() - 2 - size_plain_len)
                trunc_path = _truncate_filename(str(p.resolve()), path_max)
                selected_container.mount(
                    Static(f"[bold #FF6B6B]• {trunc_path}[/]{dim_size}", classes="selected-file-item")
                )
        except Exception:
            pass

        # Requirement 6: download input cannot be accessed when 'send' files are selected.
        # It is hidden completely, not just dimmed, while any file is selected,
        # and also while a transfer is in progress (see _update_download_composer).
        self._update_download_composer()

    # -- input handling ------------------------------------------------
    # The send file input field was removed: files are now selected
    # only from the file manager box, with Space, and sent with Enter.
    # Tab completion for absolute paths remains in core/file_select
    # for any future input, but is not wired to a send input here.
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "download_input":
            # Requirement 6: Enter key initiates the request
            name = _strip_surrounding_quotes(event.value)
            event.input.value = ""
            if name:
                self._download(name)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "download_input":
            self._clear_download_denied()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.selection:
            self._send()
        else:
            self._set_status("Select files first with Space, then press Enter to send.")
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        try:
            lst = self.query_one("#cwd_list", ListView)
            for child in lst.children:
                try:
                    ptr = child.query_one(".file-pointer", Label)
                    ptr.update("❯ " if child == event.item else "  ")
                except Exception:
                    pass
        except Exception:
            pass

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
        # A new user-started send ends any previous received batch.
        self._received_files = []
        files = list(self.selection)
        self.selection = []
        # Set transfer-active before refreshing, so the download
        # composer stays hidden even though the selection is now empty.
        self._transfer_active = True
        self._refresh_selected()
        self._refresh_browser()

        total_batch_size = sum(p.stat().st_size for p in files if p.is_file())
        self._overall_total = total_batch_size
        self._overall_transfer = TransferProgress(total_batch_size)

        def worker():
            self.app.call_from_thread(self._set_progress_visible, True)
            completed_bytes = 0
            sent_count = 0
            failed_count = 0
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
                if ok:
                    sent_count += 1
                else:
                    failed_count += 1
                self.app.call_from_thread(
                    self._set_status,
                    f"Sent {path.name}" if ok else f"Failed to send {path.name}",
                )
            self.app.call_from_thread(self._finish_send, sent_count, failed_count)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_send(self, sent_count: int, failed_count: int) -> None:
        self._transfer_active = False
        self._progress_visible = False
        self._show_transfer_complete(sent_count, failed_count)
        self._update_download_composer()
    def _download(self, name: str) -> None:
        name = _strip_surrounding_quotes(name)
        self._clear_download_denied()
        if self.selection:
            self._set_status("Cannot download while files are selected to send. Send or unselect them first.")
            return
        # A new download request ends any previous received batch.
        self._received_files = []
        self._set_status(f"Waiting for peer approval for {name}...")
        ok = self.session.request_download(name, request_id=str(uuid.uuid4()))
        if not ok:
            self._set_status(f"Failed to request {name}")
    def _on_download_denied(self, name: str, request_id: str) -> None:
        self._set_status(f"Peer denied download of {name}")
        try:
            msg = self.query_one("#download_denied_message", Static)
            # "✗ Peer denied download request for " is 36 chars.
            trunc_name = _truncate_filename(name, max(12, self._content_width() - 36))
            msg.update(f"✗ Peer denied download request for {trunc_name}")
            msg.add_class("active")
            msg.styles.display = "block"
        except Exception:
            pass

    def _clear_download_denied(self) -> None:
        try:
            msg = self.query_one("#download_denied_message", Static)
            msg.update("")
            msg.remove_class("active")
            msg.styles.display = "none"
        except Exception:
            pass


    def _is_download_modal_active(self) -> bool:
        return bool(self._pending_downloads)

    async def on_key(self, event) -> None:
        if self._is_download_modal_active():
            if event.key == "enter":
                event.stop()
                self._answer_download(True)
                return
            if event.key in ("backspace", "delete"):
                event.stop()
                self._answer_download(False)
                return
            if event.key in ("left", "right", "tab"):
                event.stop()
                if self.focused == self._deny_btn and self._approve_btn:
                    self._approve_btn.focus()
                elif self._deny_btn:
                    self._deny_btn.focus()
                return
            if event.key == "escape":
                event.stop()
                self._answer_download(False)
                return
            event.stop()
            return

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

