from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Input, Label, Static

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


class _SessionApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, "creator"))


class _CreateApp(App):
    CSS = CSS

    def __init__(self, screen):
        super().__init__()
        self._screen = screen

    def on_mount(self):
        self.push_screen(self._screen)


@pytest.mark.asyncio
async def test_session_colors_download_space_and_metrics(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        hdr = screen.query_one("#selected_header", Static)
        text = hdr.render().plain
        spans = {text[s.start:s.end]: str(s.style) for s in hdr.render().spans}
        assert spans.get("[Space]") == "#FFFFFF"
        assert spans.get(" to select file") == "#D7D7D7"
        dl_label = screen.query_one("#download_composer .composer-label", Static)
        assert dl_label.styles.color.hex.upper() == "#D7D7D7"
        dl_input = screen.query_one("#download_input", Input)
        assert dl_input.styles.color.hex.upper() == "#D7D7D7"
        # Overall metrics are theme red, file metrics are unchanged.
        for mid in ("#metric_speed", "#metric_transferred", "#metric_remaining", "#metric_eta"):
            assert screen.query_one(mid, Label).styles.color.hex.upper() == "#FF6B6B"
        assert screen.query_one("#progress_file_name", Label).styles.color.hex.upper() == "#E8E8E8"
        assert screen.query_one("#progress_file_size", Label).styles.color.hex.upper() == "#71717A"
        overlay = screen.query_one("#download_modal_overlay")
        assert overlay.styles.background.a == 0.5


@pytest.mark.asyncio
async def test_fingerprint_modal_overlay():
    app = _CreateApp(CreateScreen())
    async with app.run_test(size=(100, 40)) as pilot:
        screen = app.screen
        overlay = screen.query_one("#fingerprint_modal_overlay")
        assert overlay.styles.display == "none"
        assert overlay.styles.background.a == 0.5
        # Old inline prompt is gone, modal body is the prompt now.
        assert not screen.query("#fingerprint")
        screen._set_allow_visible(True)
        await pilot.pause()
        assert overlay.styles.display == "block"
        assert "active" in overlay.classes
        assert screen.focused is not None and screen.focused.id == "allow"
        screen._awaiting_approval = True
        screen._approved = False
        await pilot.press("enter")
        await pilot.pause()
        assert screen._approved is True
        assert overlay.styles.display == "none"
