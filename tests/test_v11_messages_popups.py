from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.containers import Vertical
from textual.widgets import ProgressBar, Static

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

    def respond_download(self, name, request_id, allow, on_progress=None):
        # Mirror the real Session.respond_download signature.
        if not allow:
            return True
        if on_progress:
            on_progress(Path(name).name, 10, 10)
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
async def test_sent_message_hides_after_timer_callback(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._finish_send(2, 0)
        await pilot.pause()
        msg = screen.query_one("#transfer_complete_message", Static)
        assert msg.render().plain == "Sent 2 files successfully."
        assert msg.styles.display == "block"
        assert screen._complete_timer is not None
        # The timer callback itself, without waiting 5 real seconds.
        screen._hide_transfer_complete()
        await pilot.pause()
        assert msg.styles.display == "none"
        assert screen.query_one("#progress_section", Vertical).styles.display == "none"


@pytest.mark.asyncio
async def test_received_message_single_and_list(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._on_received("report.pdf", True, "")
        await pilot.pause()
        msg = screen.query_one("#transfer_complete_message", Static)
        assert msg.render().plain == 'Received file "report.pdf" successfully.'
        assert msg.styles.color.hex.upper() == "#78DC8C"
        # A second file in the same batch appends to the list.
        screen._on_received("notes.txt", True, "")
        await pilot.pause()
        text = screen.query_one("#transfer_complete_message", Static).render().plain
        assert text == "Received 2 files:\n• report.pdf\n• notes.txt"
        # The message lives inside the page's VerticalScroll, so a
        # long list scrolls with the page.
        assert screen.query_one("#session_scroll")
        # Received messages are not on the 5-second Sent timer.
        assert screen._complete_timer is None
        assert screen._complete_message_kind == "received"


@pytest.mark.asyncio
async def test_approved_download_shows_progress_and_sent(tmp_path: Path):
    # Approver side: _answer_download with allow must drive progress
    # and finish with a Sent message, via respond_download's
    # on_progress callback.
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        # Fake a pending download approval.
        screen._pending_downloads = [("report.pdf", "rid-1")]
        # _answer_download pops and shows next approval (none left).
        screen._answer_download(True)
        # Wait for the worker thread to run and finish.
        for _ in range(50):
            await pilot.pause()
            msg = screen.query_one("#transfer_complete_message", Static)
            if msg.styles.display == "block" and "Sent 1 file" in msg.render().plain:
                break
        msg = screen.query_one("#transfer_complete_message", Static)
        assert msg.render().plain == "Sent 1 file successfully."
        # Progress bar was shown during the approved send, then replaced.
        assert screen.query_one("#bar", ProgressBar).styles.display == "none"


@pytest.mark.asyncio
async def test_popup_overlays_are_dark_grey(tmp_path: Path):
    # Session download modal overlay.
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        overlay = app.screen.query_one("#download_modal_overlay")
        assert overlay.styles.background.hex.upper() == "#27272A"
    # Join fingerprint modal overlay.
    app2 = _CreateApp()
    async with app2.run_test(size=(100, 40)) as pilot:
        overlay = app2.screen.query_one("#fingerprint_modal_overlay")
        assert overlay.styles.background.hex.upper() == "#27272A"
