from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input

from riptide import __version__
from riptide.screens.create import CreateScreen
from riptide.screens.session_screen import SessionScreen
from riptide.theme import CSS


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

    def start(self):
        pass

    def close(self):
        pass

    def send_file(self, path, on_progress=None):
        return True

    def request_download(self, name, request_id=""):
        return True


class _JoinApp(App):
    CSS = CSS

    def on_mount(self):
        self.push_screen(CreateScreen())


class _SessionApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, "host"))


def test_version_is_0_14_1():
    assert __version__ == "0.14.1"


@pytest.mark.asyncio
async def test_create_page_has_no_scroll_container():
    """Create page must not contain a VerticalScroll at all, so no
    vertical scrollbar can appear no matter the terminal height."""
    app = _JoinApp()
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        assert not screen.query("VerticalScroll")
        content = screen.query_one("#create_content", Vertical)
        assert content.styles.height is not None
        # Header and waiting card are still present.
        assert screen.query_one("#session_host_title")
        assert screen.query_one("#incoming_card")


@pytest.mark.asyncio
async def test_download_composer_hidden_when_file_selected(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        composer = screen.query_one("#download_composer", Vertical)
        dl_input = screen.query_one("#download_input", Input)
        assert composer.styles.display == "block"
        # Select a file through the screen's own refresh path.
        f = tmp_path / "a.txt"
        f.write_text("hi")
        screen.selection = [f]
        screen._refresh_selected()
        await pilot.pause()
        assert composer.styles.display == "none"
        assert dl_input.disabled is True
        # Deselecting restores it.
        screen.selection = []
        screen._refresh_selected()
        await pilot.pause()
        assert composer.styles.display == "block"
        assert dl_input.disabled is False
