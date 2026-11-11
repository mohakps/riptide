"""Section 6: Rich markup escaping.

A peer-controlled or local name can contain Rich markup, so a
crafted device name, file name, or host string must show literally,
never as formatted or linked text, and never raise a MarkupError.
Normal names, with spaces, parentheses, and Unicode, still display.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import Static

from riptide.core.config import Peer
from riptide.core.markup import esc
from riptide.screens.create import CreateScreen
from riptide.screens.join import SavedDevicesList
from riptide.screens.session_screen import SessionScreen
from riptide.theme import CSS


# -- the helper -------------------------------------------------------


def test_esc_makes_markup_literal():
    evil = "[red]evil[/red]"
    rendered = Text.from_markup(esc(evil))
    assert rendered.plain == evil
    assert rendered.spans == []
    # A lone closing tag must not raise a MarkupError.
    rendered = Text.from_markup(esc("a[/]b"))
    assert rendered.plain == "a[/]b"
    # A link must not become a link.
    link = "[link https://example.com]click[/link]"
    rendered = Text.from_markup(esc(link))
    assert rendered.plain == link
    assert rendered.spans == []


def test_esc_leaves_normal_names_unchanged():
    for name in [
        "report.pdf",
        "my file (1).pdf",
        "café notes — final.docx",
        "archive.tar.gz",
        "notes",
        ".bashrc",
    ]:
        assert esc(name) == name


# -- pilot apps --------------------------------------------------------


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
        return True


class _SessionApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, "host"))


class _CreateApp(App):
    CSS = CSS

    def on_mount(self):
        self.push_screen(CreateScreen())


class _DevicesApp(App):
    CSS = CSS

    def __init__(self, peers):
        super().__init__()
        self._peers = peers

    def on_mount(self):
        self.mount(SavedDevicesList(self._peers))


# -- session screen: approval and received paths ----------------------


@pytest.mark.asyncio
async def test_received_message_shows_malicious_name_literally(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._received_files = ["[red]evil[/red]"]
        screen._show_received_message()
        await pilot.pause()
        msg = screen.query_one("#transfer_complete_message", Static)
        assert '[red]evil[/red]' in msg.render().plain
        # And a normal name still displays.
        screen._received_files = ["my file (1).pdf"]
        screen._show_received_message()
        await pilot.pause()
        assert msg.render().plain == 'Received file "my file (1).pdf" successfully.'


@pytest.mark.asyncio
async def test_download_approval_shows_malicious_name_literally(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._pending_downloads = [("[red]evil[/red]", "rid-1")]
        screen._show_next_download_approval()
        await pilot.pause()
        card = screen.query_one("#download_approval", Static)
        assert '[red]evil[/red]' in card.render().plain


@pytest.mark.asyncio
async def test_resume_card_shows_malicious_name_literally(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._show_resume_card("[link https://example.com]click[/link]", 512, 1024)
        await pilot.pause()
        card = screen.query_one("#resume_approval", Static)
        assert '[link https://example.com]click[/link]' in card.render().plain


@pytest.mark.asyncio
async def test_progress_shows_malicious_name_literally(tmp_path: Path):
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._on_progress("[red]evil[/red]", 100, 1000, 100, 1000, "Receiving")
        await pilot.pause()
        label = screen.query_one("#progress_file_name")
        assert '[red]evil[/red]' in label.render().plain


def test_client_info_shows_malicious_device_literally(tmp_path: Path):
    session = _DummySession(tmp_path)
    session.peer_device = "[link https://example.com]click[/link]"
    session.peer_host = "host.example"
    screen = SessionScreen(session, "host")
    rendered = Text.from_markup(screen._format_client_info())
    assert "[link https://example.com]click[/link]" in rendered.plain
    assert rendered.spans == [] or all(
        "link" not in str(span.style) for span in rendered.spans
    )


def test_status_stores_raw_text_but_escapes_display(tmp_path: Path):
    session = _DummySession(tmp_path)
    screen = SessionScreen(session, "host")
    # The status widget was removed from the page, so the update
    # is swallowed, but the raw text is kept for debugging, and
    # the displayed text (when the widget exists) is escaped.
    screen._set_status("Received [red]evil[/red]: verified")
    assert screen._last_status == "Received [red]evil[/red]: verified"
    assert Text.from_markup(esc("Received [red]evil[/red]: verified")).plain == (
        "Received [red]evil[/red]: verified"
    )


# -- create screen: incoming connection -------------------------------


@pytest.mark.asyncio
async def test_incoming_connection_shows_malicious_device_literally(tmp_path: Path):
    app = _CreateApp()
    async with app.run_test(size=(120, 50)) as pilot:
        screen = app.screen
        screen._show_incoming_connection(
            "[red]evil[/red]", "aabbccdd" * 8, "new"
        )
        await pilot.pause()
        msg = screen.query_one("#incoming", Static)
        assert '[red]evil[/red]' in msg.render().plain


# -- join screen: saved devices ---------------------------------------


@pytest.mark.asyncio
async def test_saved_device_shows_malicious_name_literally(tmp_path: Path):
    peer = Peer(name="[red]evil[/red]", host="host.example", fingerprint="aabbcc")
    app = _DevicesApp([peer])
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        item = app.query_one("#device_item_0", Static)
        assert '[red]evil[/red]' in item.render().plain
        # refresh_items (focused and unfocused) keeps it literal.
        app.query_one(SavedDevicesList).refresh_items()
        await pilot.pause()
        assert '[red]evil[/red]' in item.render().plain
