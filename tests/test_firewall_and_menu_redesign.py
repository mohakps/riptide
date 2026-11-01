from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import OptionList, Static

from riptide.core.config import Config, load_config, save_config
from riptide.core.firewall import check_firewall_port, get_os, open_firewall_port
from riptide.screens.join import JoinScreen
from riptide.screens.menu import MenuScreen, _build_option_prompt
from riptide.theme import BANNER_CLIENT, BANNER_CREATE, BANNER_HOST, BANNER_JOIN, CSS


class _MenuTestApp(App):
    CSS = CSS

    def compose(self):
        yield MenuScreen()


class _JoinTestApp(App):
    CSS = CSS

    def __init__(self, port_was_closed: bool = False):
        super().__init__()
        self.port_was_closed = port_was_closed

    def on_mount(self):
        self.push_screen(JoinScreen(port_was_closed=self.port_was_closed))


def test_small_slant_banners_structure():
    """Verify small slant banners are non-empty and have correct slant lines."""
    for banner in (BANNER_HOST, BANNER_CLIENT, BANNER_CREATE, BANNER_JOIN):
        assert banner.strip() != ""
        assert "/" in banner or "\\" in banner
        lines = banner.strip().splitlines()
        assert len(lines) == 4


def test_config_firewall_port_open_persistence(tmp_path: Path):
    """Verify firewall_port_open flag persists in config.toml."""
    cfg = Config(session_port=50000, firewall_port_open=True)
    save_config(cfg, home=tmp_path)

    loaded = load_config(home=tmp_path)
    assert loaded.session_port == 50000
    assert loaded.firewall_port_open is True

    cfg.firewall_port_open = False
    save_config(cfg, home=tmp_path)
    loaded2 = load_config(home=tmp_path)
    assert loaded2.firewall_port_open is False


def test_firewall_check_windows_parsing():
    """Test Windows netsh output parsing for open vs closed ports."""
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        fake_netsh_output = """
Rule Name:                            Riptide Test
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Allow
Protocol:                             TCP
LocalPort:                            50000

Rule Name:                            Disabled Rule
----------------------------------------------------------------------
Enabled:                              No
Direction:                            In
Action:                               Allow
Protocol:                             TCP
LocalPort:                            50001

Rule Name:                            Blocked Rule
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Block
Protocol:                             TCP
LocalPort:                            50002
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_netsh_output)
            assert check_firewall_port(50000) is True
            assert check_firewall_port(50001) is False
            assert check_firewall_port(50002) is False
            assert check_firewall_port(9999) is False


def test_firewall_check_linux_ufw_and_firewalld():
    """Test Linux firewall checks."""
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        # Test UFW active with port allowed
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="Status: active\n50000/tcp ALLOW Anywhere")
                assert check_firewall_port(50000) is True

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="Status: active\n22/tcp ALLOW Anywhere")
                assert check_firewall_port(50000) is False

        # Test firewalld
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/firewall-cmd" if cmd == "firewall-cmd" else None):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    MagicMock(returncode=0, stdout="running"),
                    MagicMock(returncode=0, stdout="yes"),
                ]
                assert check_firewall_port(50000) is True


def test_firewall_open_port_invokes_os_command():
    """Verify open_firewall_port runs the OS-specific firewall rule command."""
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            success = open_firewall_port(50000)
            assert success is True
            assert mock_run.called
            cmd = mock_run.call_args[0][0]
            assert "netsh" in cmd
            assert any("50000" in str(arg) for arg in cmd)


def test_menu_option_prompts_styling():
    """Verify home page options distinguish actual option title from subtitle."""
    active_prompt = _build_option_prompt("Create Server", "Wait for incoming session", True)
    inactive_prompt = _build_option_prompt("Join Server", "Dial out to peer", False)

    assert isinstance(active_prompt, Text)
    assert isinstance(inactive_prompt, Text)

    # Active option has bold white title and prefix
    assert str(active_prompt).startswith("❯  Create Server")
    assert "Wait for incoming session" in str(active_prompt)

    # Inactive option has subdued styling
    assert str(inactive_prompt).startswith("   Join Server")
    assert "Dial out to peer" in str(inactive_prompt)


@pytest.mark.asyncio
async def test_menu_clicking_create_server_firewall_flow(tmp_path: Path):
    """When clicking create server, check port in firewall, save to config, open if closed."""
    app = _MenuTestApp()
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        with patch("riptide.core.firewall.check_firewall_port", return_value=False) as mock_check:
            with patch("riptide.core.firewall.open_firewall_port", return_value=True) as mock_open:
                async with app.run_test() as pilot:
                    opt_list = app.screen.query_one("#menu_list", OptionList)
                    opt_list.highlighted = 0
                    await pilot.press("enter")
                    await pilot.pause()

                    assert mock_check.called
                    assert mock_open.called

                    # Verify config was saved with firewall_port_open = False (since it was closed)
                    cfg = load_config(home=tmp_path)
                    assert cfg.firewall_port_open is False


@pytest.mark.asyncio
async def test_join_screen_router_banner_shown_only_when_closed():
    """Router banner is shown only if port was closed; hidden when port was open."""
    # 1. Port was closed: banner is displayed with router instructions
    app_closed = _JoinTestApp(port_was_closed=True)
    async with app_closed.run_test(size=(100, 40)) as pilot:
        screen = app_closed.screen
        router_banner = screen.query_one("#router_banner", Static)
        text = router_banner.render().plain
        assert "closed in your firewall" in text
        assert "router settings" in text
        assert router_banner.styles.display == "block"

    # 2. Port was open: banner remains hidden
    app_open = _JoinTestApp(port_was_closed=False)
    async with app_open.run_test(size=(100, 40)) as pilot:
        screen = app_open.screen
        router_banner = screen.query_one("#router_banner", Static)
        assert router_banner.styles.display == "none"


class _DummySessionForModal:
    def __init__(self, cwd: Path):
        self.peer_host = "192.168.1.50"
        self.peer_device = "peer-box"
        self.cwd = cwd
        self.on_progress = None
        self.on_file_received = None
        self.on_ack = None
        self.on_error = None
        self.on_download_ask = None
        self.on_download_denied = None
        self.responded: list[tuple[str, str, bool]] = []

    def start(self):
        pass

    def send_file(self, *args, **kwargs):
        return True

    def request_download(self, *args, **kwargs):
        return True

    def respond_download(self, name: str, request_id: str, allow: bool):
        self.responded.append((name, request_id, allow))
        return True


class _SessionModalApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        from riptide.screens.session_screen import SessionScreen
        self.push_screen(SessionScreen(self._session, role="creator"))


@pytest.mark.asyncio
async def test_download_approval_popup_workflow(tmp_path: Path):
    """Download approval request triggers a centered modal overlay, Enter accepts, Backspace denies."""
    session = _DummySessionForModal(tmp_path)
    app = _SessionModalApp(session)
    async with app.run_test(size=(100, 35)) as pilot:
        screen = app.screen
        overlay = screen.query_one("#download_modal_overlay")
        assert overlay.styles.display == "none"

        # Trigger download ask
        screen._on_download_ask("report_2026.pdf", "req-123")
        await pilot.pause()

        # Modal popup is now active and displayed
        assert overlay.styles.display == "block"
        assert overlay.has_class("active")

        # Check modal card contents
        title = screen.query_one("#download_modal_title", Static).render().plain
        assert "DOWNLOAD REQUEST" in title

        body = screen.query_one("#download_approval", Static).render().plain
        assert "report_2026.pdf" in body

        footer = screen.query_one("#download_modal_footer", Static).render().plain
        assert "Enter" in footer and "Accept" in footer
        assert "Backspace" in footer and "Deny" in footer

        # Accept via Enter key
        await pilot.press("enter")
        await pilot.pause()

        # Verified response was sent with allow=True and modal closed
        assert len(session.responded) == 1
        assert session.responded[0] == ("report_2026.pdf", "req-123", True)
        assert overlay.styles.display == "none"

        # Trigger second download ask and deny via Backspace
        screen._on_download_ask("secret_data.zip", "req-456")
        await pilot.pause()
        assert overlay.styles.display == "block"

        await pilot.press("backspace")
        await pilot.pause()

        assert len(session.responded) == 2
        assert session.responded[1] == ("secret_data.zip", "req-456", False)
        assert overlay.styles.display == "none"


@pytest.mark.asyncio
async def test_download_denied_message_shown_below_input(tmp_path: Path):
    """When peer denies download, requester sees a red message directly below download input."""
    session = _DummySessionForModal(tmp_path)
    app = _SessionModalApp(session)
    async with app.run_test(size=(100, 35)) as pilot:
        screen = app.screen
        denied_msg = screen.query_one("#download_denied_message", Static)
        assert denied_msg.styles.display == "none"

        # Trigger denial notification
        screen._on_download_denied("confidential.docx", "req-789")
        await pilot.pause()

        assert denied_msg.styles.display == "block"
        text = denied_msg.render().plain
        assert "Peer denied download" in text
        assert "confidential.docx" in text

        # Typing in download input clears the message
        dl_input = screen.query_one("#download_input")
        dl_input.focus()
        await pilot.press("a")
        await pilot.pause()
        assert denied_msg.styles.display == "none"
