from __future__ import annotations

import time
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Input, Static

from riptide.core import nat as nat_mod
from riptide.core.session import Session
from riptide.core.transfer import TransferProgress
from riptide.screens.create import CreateScreen
from riptide.screens.join import JoinScreen
from riptide.screens.menu import MenuScreen
from riptide.theme import BANNER_CREATE, BANNER_JOIN, CSS


class _App(App):
    CSS = CSS
    def __init__(self, screen):
        super().__init__()
        self._screen = screen
    def on_mount(self):
        self.push_screen(self._screen)


@pytest.mark.asyncio
async def test_menu_swapped_names_create_on_top():
    from riptide.app import RiptideApp
    from textual.widgets import OptionList
    app = RiptideApp()
    async with app.run_test() as pilot:
        opt_list = app.screen.query_one("#menu_list", OptionList)
        prompts = [str(o.prompt) for o in opt_list._options]
        assert prompts[0].startswith("❯  Create Server")
        assert "Wait for incoming" in prompts[0]
        assert prompts[1].startswith("   Join Server")
        assert "Dial out" in prompts[1]


def test_swapped_page_titles():
    assert BANNER_CREATE.strip() != ""
    assert BANNER_JOIN.strip() != ""
    assert BANNER_CREATE != BANNER_JOIN


@pytest.mark.asyncio
async def test_listener_page_title_and_cgnat_banner():
    app = _App(JoinScreen())
    async with app.run_test(size=(100, 40)) as pilot:
        screen = app.screen
        title = screen.query_one("#session_host_title", Static).render().plain
        assert title.strip() == BANNER_CREATE.strip()
        # Banner starts empty/hidden, then shows on a positive check.
        banner = screen.query_one("#cgnat_banner", Static)
        assert banner.render().plain.strip() == ""
        screen._show_cgnat_banner()
        assert "CGNAT detected" in banner.render().plain
        assert "Join Server" in banner.render().plain


@pytest.mark.asyncio
async def test_dialler_page_title_and_hostname_input():
    app = _App(CreateScreen())
    async with app.run_test(size=(100, 40)) as pilot:
        screen = app.screen
        title = screen.query_one("#session_host_title", Static).render().plain
        assert title.strip() == BANNER_JOIN.strip()
        host = screen.query_one("#host", Input)
        # Larger than the old 60-wide input, centred, with a label above.
        assert host.styles.width.value == 80
        assert 5 <= host.region.x <= 15
        labels = [n.render().plain for n in screen.query(Static) if "HOSTNAME" in n.render().plain]
        assert labels


def test_nat_detect_cgnat_cases():
    assert nat_mod.detect_cgnat("100.64.1.10", "203.0.113.10") is True
    assert nat_mod.detect_cgnat("192.168.1.1", "203.0.113.10") is True
    assert nat_mod.detect_cgnat("203.0.113.10", "203.0.113.10") is False
    assert nat_mod.detect_cgnat("", "203.0.113.10") is False
    assert nat_mod.is_cgnat_ip("100.64.0.1") is True
    assert nat_mod.is_cgnat_ip("192.168.1.1") is False


class _FakeSock:
    def __init__(self):
        self.sent = bytearray()
    def sendall(self, data):
        self.sent.extend(data)


def test_sender_progress_throttled(tmp_path):
    # A 1 MB file sent over a fake socket: sender must not report
    # on every 128KB chunk, otherwise the UI speed inflates.
    path = tmp_path / "big.bin"
    path.write_bytes(b"x" * (1024 * 1024))
    session = Session(_FakeSock(), tmp_path)
    reports: list[int] = []
    session.send_file(path, on_progress=lambda name, sent, total: reports.append(sent))
    # 8 chunks would be 8 reports unthrottled; throttled to ~0.1s
    # intervals, a fast fake socket should report far fewer, plus final.
    assert reports
    assert reports[-1] == 1024 * 1024
    assert len(reports) < 8


def test_transfer_progress_burst_guard():
    progress = TransferProgress(1000000)
    progress.update(0)
    # A burst of updates with almost no time between them must not
    # create a huge speed; the guard keeps speed at 0 until a
    # properly spaced update arrives.
    for sent in (128000, 256000, 384000):
        progress.update(sent)
    assert progress.speed_ema == 0.0
    assert progress.sent == 384000
