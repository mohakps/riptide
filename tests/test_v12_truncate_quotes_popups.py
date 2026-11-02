from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Label, Static

from riptide.screens.create import CreateScreen
from riptide.screens.session_screen import (
    SessionScreen,
    _strip_surrounding_quotes,
    _truncate_filename,
)
from riptide.theme import CSS


def test_strip_surrounding_quotes():
    assert _strip_surrounding_quotes('"C:\\Users\\mp\\file.pdf"') == "C:\\Users\\mp\\file.pdf"
    assert _strip_surrounding_quotes('"/home/mp/file.pdf"') == "/home/mp/file.pdf"
    assert _strip_surrounding_quotes('  "file.pdf"  ') == "file.pdf"
    assert _strip_surrounding_quotes('""file.pdf""') == "file.pdf"
    assert _strip_surrounding_quotes('"file.pdf') == "file.pdf"
    assert _strip_surrounding_quotes("file.pdf") == "file.pdf"
    assert _strip_surrounding_quotes("") == ""


def test_truncate_filename_keeps_start_and_end():
    name = "Tenki_no_Ko_Weathering_With_You_BDRip_4K_2160p_HEVC_HDR10_DTS-HD_Master_Audio.mkv"
    truncated = _truncate_filename(name, 30)
    assert len(truncated) == 30
    assert "..." in truncated
    assert truncated.startswith("Tenki_no_Ko")
    assert truncated.endswith(".mkv")
    # Short names are unchanged.
    assert _truncate_filename("short.txt", 30) == "short.txt"


class _DummySession:
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
        self.requested: list[str] = []

    def start(self):
        pass

    def close(self):
        pass

    def send_file(self, path, on_progress=None):
        return True

    def request_download(self, name, request_id=""):
        self.requested.append(name)
        return True

    def respond_download(self, name, request_id, allow, on_progress=None):
        return True


class _SessionApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, "creator"))


class _CreateApp(App):
    CSS = CSS

    def on_mount(self):
        self.push_screen(CreateScreen())


@pytest.mark.asyncio
async def test_download_input_strips_quotes(tmp_path: Path):
    session = _DummySession(tmp_path)
    app = _SessionApp(session)
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._download('"/home/peer/report.pdf"')
        await pilot.pause()
        assert session.requested == ["/home/peer/report.pdf"]


@pytest.mark.asyncio
async def test_long_names_truncate_dynamically(tmp_path: Path):
    longname = "Tenki_no_Ko_Weathering_With_You_BDRip_4K_2160p_HEVC_HDR10_DTS-HD_Master_Audio.mkv"
    (tmp_path / longname).write_text("x" * 10)
    app = _SessionApp(_DummySession(tmp_path))
    # Narrow window: 60 columns. Progress name must fit in it,
    # with ..., not the fixed 50 chars from before.
    async with app.run_test(size=(60, 40)) as pilot:
        screen = app.screen
        screen._on_progress(longname, 100, 1000, 100, 1000, "Sending")
        await pilot.pause()
        text = screen.query_one("#progress_file_name", Label).render().plain
        assert "..." in text
        assert len(text) <= 60
        assert text.endswith(".mkv")
        # Received message: same name, truncated to window width.
        screen._on_received(longname, True, "")
        await pilot.pause()
        msg = screen.query_one("#transfer_complete_message", Static).render().plain
        assert "..." in msg
        assert all(len(line) <= 60 for line in msg.splitlines())
        # Selected files: absolute path truncated to window width.
        screen.selection = [tmp_path / longname]
        screen._refresh_selected()
        await pilot.pause()
        for item in screen.query_one("#selected_files_list").children:
            plain = item.render().plain
            assert len(plain) <= 60
            assert "..." in plain


@pytest.mark.asyncio
async def test_popup_cards_are_dark_grey(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        card = app.screen.query_one("#download_modal_card")
        assert card.styles.background.hex.upper() == "#3F3F46"
    app2 = _CreateApp()
    async with app2.run_test(size=(100, 40)) as pilot:
        card = app2.screen.query_one("#fingerprint_modal_card")
        assert card.styles.background.hex.upper() == "#3F3F46"
