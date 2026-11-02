from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.containers import Vertical
from textual.widgets import Label, ProgressBar, Static

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
        if on_progress:
            on_progress(path.name, path.stat().st_size, path.stat().st_size)
        return True

    def request_download(self, name, request_id=""):
        return True


class _SessionApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, "host"))


@pytest.mark.asyncio
async def test_download_hidden_during_progress_and_sent_message(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        composer = screen.query_one("#download_composer", Vertical)
        assert composer.styles.display == "block"
        # Progress visible (sending or receiving) hides the composer.
        screen._set_progress_visible(True)
        await pilot.pause()
        assert composer.styles.display == "none"
        screen._set_progress_visible(False)
        await pilot.pause()
        assert composer.styles.display == "block"
        # A completed send shows a green statement in place of the bar.
        screen._finish_send(2, 0)
        await pilot.pause()
        msg = screen.query_one("#transfer_complete_message", Static)
        assert msg.render().plain == "Sent 2 files successfully."
        assert msg.styles.display == "block"
        assert msg.styles.color.hex.upper() == "#78DC8C"
        section = screen.query_one("#progress_section", Vertical)
        assert section.styles.display == "block"
        assert screen.query_one("#bar", ProgressBar).styles.display == "none"
        assert screen.query_one("#progress_metrics_row").styles.display == "none"
        # Composer returns after the transfer, with no selection.
        assert composer.styles.display == "block"
        # Singular form.
        screen._finish_send(1, 0)
        await pilot.pause()
        assert screen.query_one("#transfer_complete_message", Static).render().plain == "Sent 1 file successfully."
        # A new transfer replaces the message with the progress bar.
        screen._set_progress_visible(True)
        await pilot.pause()
        assert screen.query_one("#transfer_complete_message", Static).styles.display == "none"
        assert screen.query_one("#bar", ProgressBar).styles.display == "block"
        assert composer.styles.display == "none"


@pytest.mark.asyncio
async def test_send_hides_composer_and_shows_sent_message(tmp_path: Path):
    # End-to-end through _send with a dummy session that reports success.
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hi")
        f2.write_text("hello")
        screen.selection = [f1, f2]
        screen._refresh_selected()
        await pilot.pause()
        assert screen.query_one("#download_composer", Vertical).styles.display == "none"
        screen._send()
        # Wait for the worker thread to finish and the UI to update.
        for _ in range(50):
            await pilot.pause()
            msg = screen.query_one("#transfer_complete_message", Static)
            if msg.styles.display == "block":
                break
        assert screen.query_one("#transfer_complete_message", Static).render().plain == "Sent 2 files successfully."
        assert screen.query_one("#download_composer", Vertical).styles.display == "block"
