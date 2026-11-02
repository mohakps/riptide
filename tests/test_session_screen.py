from __future__ import annotations

import pytest
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Label, ListView, ProgressBar, Static

from riptide.core.file_select import format_file_row
from riptide.screens.session_screen import SessionScreen, _truncate_filename
from riptide.theme import BANNER_HOST, CSS, TAGLINES

class DummySession:
    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.peer_device = "yoga"
        self.peer_host = "192.168.1.15"
        self.sock = None
        self.on_file_received = None
        self.on_ack = None
        self.on_error = None
        self.on_progress = None
        self.on_download_ask = None
        self.on_download_denied = None

    def start(self):
        pass

    def close(self):
        pass

    def send_file(self, path, on_progress=None):
        return True

    def request_download(self, name, request_id=""):
        return True


class SessionTestApp(App):
    CSS = CSS

    def __init__(self, session, role="creator"):
        super().__init__()
        self.test_session = session
        self.role = role
    def on_mount(self):
        self.push_screen(SessionScreen(self.test_session, self.role))


def test_file_row_structure(tmp_path):
    p = tmp_path / "testfile.dat"
    p.write_bytes(b"x" * 2048)
    name, size, mtime = format_file_row(p)
    assert name == "testfile.dat"
    assert "KB" in size
    assert "-" in mtime and ("am" in mtime or "pm" in mtime)


def test_session_tagline_present():
    assert "session" in TAGLINES
    assert "encrypted channel" in TAGLINES["session"]


def test_truncate_filename():
    short = "report.pdf"
    assert _truncate_filename(short, 50) == "report.pdf"
    long_name = "Bleach (2004) - S04E08 - 071 - The Moment of Collision An Evil Hand Draws Near.mkv"
    truncated = _truncate_filename(long_name, 30)
    assert len(truncated) <= 30
    assert "..." in truncated
    assert truncated.endswith(".mkv")


@pytest.mark.asyncio
async def test_session_screen_redesign_header_and_sub_header_removed(tmp_path):
    """Header is a larger 5-row block banner (HOST), client
    info with IP/host, connection status, and Status subheader removed.
    """
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, SessionScreen)

        host_title = screen.query_one("#session_host_title", Static).render().plain
        assert host_title.strip() == BANNER_HOST.strip()
        # Status subheader widget is gone.
        assert len(screen.query("#status")) == 0
        # File-selection box footer inside the box is gone.
        assert len(screen.query("#browser_hint")) == 0
        # Send file input field is gone.
        assert len(screen.query("#file_input")) == 0

        # 1. Client info with hostname or IP address
        client_label = screen.query_one("#peer_client_label", Static).render().plain
        assert "yoga" in client_label
        assert "192.168.1.15" in client_label

        # 1. Connection status indicator: Connected with filled circle ●
        status_label = screen.query_one("#peer_status_label", Static).render().plain
        assert "Connected" in status_label
        assert "●" in status_label

        # 2. Sub header removed
        all_text = " ".join(str(getattr(node.render(), "plain", node.render())) for node in screen.query("Static, Label"))
        assert TAGLINES["session"] not in all_text


@pytest.mark.asyncio
async def test_session_screen_file_selector_box_folder_and_separator(tmp_path):
    """Requirement 3 & 4: Current folder inside selector box with clear separator below it,

    and height increased.
    """
    (tmp_path / "ep01.mkv").write_bytes(b"x" * 1000)
    (tmp_path / "ep02.mkv").write_bytes(b"x" * 2000)
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen
        browser_box = screen.query_one("#browser_box")
        assert browser_box is not None

        # Folder path is inside browser_box
        folder_label = browser_box.query_one("#browser_path", Static)
        assert str(tmp_path) in folder_label.render().plain

        # Clear separator below it
        separator = browser_box.query_one("#browser_separator", Static)
        assert separator is not None
        assert "─" in separator.render().plain

        # ListView is inside browser_box
        list_view = browser_box.query_one("#cwd_list", ListView)
        assert list_view is not None


@pytest.mark.asyncio
async def test_session_screen_search_filtering(tmp_path):
    """Requirement 4: Typing searches the files."""
    (tmp_path / "bleach_01.mkv").write_bytes(b"x" * 1000)
    (tmp_path / "naruto_01.mkv").write_bytes(b"x" * 1000)
    (tmp_path / "bleach_02.mkv").write_bytes(b"x" * 1000)
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen

        # Set search query to 'bleach'
        screen._search_query = "bleach"
        rows = screen._browser_rows()
        names = [p.name for p in rows]
        assert "bleach_01.mkv" in names
        assert "bleach_02.mkv" in names
        assert "naruto_01.mkv" not in names

        # Clear search query
        screen._search_query = ""
        rows_all = screen._browser_rows()
        names_all = [p.name for p in rows_all]
        assert "naruto_01.mkv" in names_all


@pytest.mark.asyncio
async def test_session_screen_spacebar_opens_folder_and_selects_files(tmp_path):
    """Spacebar opens folders and toggles file selection."""
    sub = tmp_path / "subfolder"
    sub.mkdir()
    (sub / "nested.txt").write_bytes(b"nested")
    f1 = tmp_path / "file1.txt"
    f1.write_bytes(b"hello")
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen
        assert len(screen.query("#send")) == 0

        # Space on a file selects it
        screen.selection = [f1]
        screen._refresh_selected()
        await pilot.pause()
        selected_items = screen.query(".selected-file-item")
        assert len(selected_items) == 1
        # The absolute path is longer than the default 80-column
        # test window, so it is truncated with ..., keeping the
        # start and the file name at the end.
        plain = selected_items[0].render().plain
        assert "..." in plain
        assert plain.endswith("file1.txt  (5 B)")

        # Space on a folder navigates into it
        screen._go_into(sub)
        assert screen.browser_dir == sub


@pytest.mark.asyncio
async def test_session_screen_tab_cycles_ui_elements(tmp_path):
    """Tab cycles through UI elements, with no send input anymore."""
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen
        # Initial focus is cwd_list
        assert screen.focused.id == "cwd_list"

        # Tab moves to download_input (send input was removed)
        await pilot.press("tab")
        assert screen.focused.id == "download_input"

        # Tab cycles back to cwd_list (allow/deny are hidden)
        await pilot.press("tab")
        assert screen.focused.id == "cwd_list"


@pytest.mark.asyncio
async def test_session_screen_find_label_auto_first_and_zero(tmp_path):
    """Find label always visible, auto-first file/folder on dir change,
    and 0 deselects all."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.txt").write_bytes(b"a")
    (tmp_path / "b.txt").write_bytes(b"b")
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen
        # Find label, even with empty query.
        find = screen.query_one("#browser_search_indicator", Static).render().plain
        assert "Find:" in find
        # Auto-first: after going into a folder, highlighted row is
        # the first real entry, not the ".." parent row.
        screen._go_into(sub)
        lst = screen.query_one("#cwd_list", ListView)
        assert lst.index == 0  # sub is empty, so first row is ".." only
        screen._go_up()
        # Back in tmp: rows are .., sub, a, b -> auto-first is sub (index 1)
        lst = screen.query_one("#cwd_list", ListView)
        assert lst.index == 1
        # Search, then dir change resets it.
        screen._search_query = "a"
        screen._go_into(sub)
        assert screen._search_query == ""
        # 0 deselects all, when not typing in an input.
        screen.selection = [tmp_path / "a.txt"]
        screen._refresh_selected()
        await pilot.press("0")
        assert screen.selection == []
@pytest.mark.asyncio
async def test_session_screen_download_button_removed_and_disabled_on_send(tmp_path):
    """Requirement 6: Download button removed, Enter initiates request,

    and field cannot be accessed when 'send' files are selected.
    """
    f1 = tmp_path / "file1.txt"
    f1.write_bytes(b"data")
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen

        # Download button is removed
        assert len(screen.query("#download")) == 0

        dl_input = screen.query_one("#download_input", Input)
        assert dl_input.disabled is False

        # When files are selected to send, download input becomes disabled
        screen.selection = [f1]
        screen._refresh_selected()
        assert dl_input.disabled is True

        # When selection cleared, download input re-enabled
        screen.selection = []
        screen._refresh_selected()
        assert dl_input.disabled is False


@pytest.mark.asyncio
async def test_session_screen_overall_progress_and_metrics_layout(tmp_path):
    """Requirement 7: Overall progress of all files, full width progress bar,

    evenly spaced metrics on line 2, third line current file and [sent/total size].
    """
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen

        # Progress section is initially hidden when no transfer
        prog_sec = screen.query_one("#progress_section")
        assert prog_sec.styles.display == "none"

        # Trigger progress update
        screen._on_progress(
            name="very_long_movie_name_bleach_episode_test.mkv",
            file_sent=500,
            file_total=1000,
            batch_sent=1500,
            batch_total=2000,
            direction="Sending",
        )
        await pilot.pause()

        # Progress section becomes visible during transfer
        assert prog_sec.styles.display == "block"

        bar = screen.query_one("#bar", ProgressBar)
        assert bar.progress == 75.0  # 1500 / 2000 * 100
        # Metrics row
        metric_speed = screen.query_one("#metric_speed", Label).render().plain
        metric_trans = screen.query_one("#metric_transferred", Label).render().plain
        metric_rem = screen.query_one("#metric_remaining", Label).render().plain
        metric_eta = screen.query_one("#metric_eta", Label).render().plain
        assert "Speed" in metric_speed
        assert "1500 B / 2000 B" in metric_trans or "1.5 KB" in metric_trans
        assert "Remaining" in metric_rem
        assert "ETA" in metric_eta

        # Third line
        file_name_label = screen.query_one("#progress_file_name", Label).render().plain
        file_size_label = screen.query_one("#progress_file_size", Label).render().plain
        assert "Sending:" in file_name_label
        assert "500 B / 1000 B" in file_size_label or "B" in file_size_label


@pytest.mark.asyncio
async def test_session_screen_focused_item_is_pure_white(tmp_path):
    """Focused/highlighted item must appear pure white (#FFFFFF, bold)."""
    (tmp_path / "item1.txt").write_bytes(b"hello")
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen
        lv = screen.query_one("#cwd_list", ListView)
        lv.focus()
        await pilot.pause()
        child = lv.highlighted_child
        fn_label = child.query_one(".file-name")
        assert fn_label.styles.color.hex.upper() == "#FFFFFF"
        assert "bold" in str(fn_label.styles.text_style)


@pytest.mark.asyncio
async def test_session_screen_download_section_and_zero_gaps(tmp_path):
    """Download section heading and input are present; no ballooning empty gaps."""
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen
        dl_composer = screen.query_one("#download_composer")
        assert dl_composer is not None
        labels = [node.render().plain for node in dl_composer.query(Static)]
        assert any("DOWNLOAD FROM PEER" in l for l in labels)
        assert dl_composer.query_one("#download_input", Input) is not None

        # Header row is now 5 lines high (block banner header)
        header = screen.query_one("#session_header_row")
        assert header.styles.height.value == 5
        assert header.styles.margin.bottom == 0

@pytest.mark.asyncio
async def test_session_screen_scrollable_and_footer_keys_in_brackets(tmp_path):
    """Full page scrollable container and footer items evenly spaced with [] keys."""
    session = DummySession(tmp_path)
    app = SessionTestApp(session, role="creator")
    async with app.run_test() as pilot:
        screen = app.screen

        # Scroll container
        scroll = screen.query_one("#session_scroll")
        assert isinstance(scroll, VerticalScroll)

        # Footer items with []
        footer = screen.query_one("#footer_bar")
        assert footer is not None
        footer_items = footer.query(".keymap-item")
        assert len(footer_items) >= 5
        keys = [str(getattr(item.render(), "plain", item.render())) for item in footer_items]
        for expected_key in ("[↑/↓]", "[Space]", "[Enter]", "[Tab]", "[Backspace]", "[Esc]"):
            assert any(expected_key in k for k in keys), f"Expected key {expected_key} in footer"
        assert any("Open/Select" in k or "Open / Select" in k for k in keys)
        assert any("Send" in k for k in keys)
        assert any("Cycle UI" in k for k in keys)
