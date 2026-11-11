from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.text import Text
from textual.app import App
from textual.widgets import Label, ListView, OptionList, Static

from riptide.core.config import Config, load_config, save_config
from riptide.core.firewall import (
    check_firewall_port,
    ensure_firewall_port,
    get_os,
    manual_firewall_command,
    open_firewall_port,
)
from riptide.screens.create import CreateScreen
from riptide.screens.menu import MenuScreen
from riptide.theme import BANNER_CLIENT, BANNER_CREATE, BANNER_HOST, BANNER_JOIN, CSS


class _MenuTestApp(App):
    CSS = CSS

    def compose(self):
        yield MenuScreen()


class _JoinTestApp(App):
    CSS = CSS

    def __init__(self, port_was_closed: bool = False, firewall_opened: bool = False):
        super().__init__()
        self.port_was_closed = port_was_closed
        self.firewall_opened = firewall_opened

    def on_mount(self):
        self.push_screen(
            CreateScreen(port_was_closed=self.port_was_closed, firewall_opened=self.firewall_opened)
        )


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



@pytest.mark.asyncio
async def test_menu_clicking_create_server_firewall_flow(tmp_path: Path):
    """When clicking create server, run the first-time setup and save it."""
    app = _MenuTestApp()
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        with patch(
            "riptide.core.firewall.setup_firewall_port", return_value="opened"
        ) as mock_setup:
            async with app.run_test() as pilot:
                opt_list = app.screen.query_one("#menu_list", OptionList)
                opt_list.highlighted = 0
                await pilot.press("enter")
                await pilot.pause()

                assert mock_setup.called
                # Setup succeeded, so the saved state is open.
                cfg = load_config(home=tmp_path)
                assert cfg.firewall_port_open is True


@pytest.mark.asyncio
async def test_menu_clicking_create_server_firewall_failed(tmp_path: Path):
    """When setup fails, the saved state stays closed."""
    app = _MenuTestApp()
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        with patch(
            "riptide.core.firewall.setup_firewall_port", return_value="failed"
        ):
            async with app.run_test() as pilot:
                opt_list = app.screen.query_one("#menu_list", OptionList)
                opt_list.highlighted = 0
                await pilot.press("enter")
                await pilot.pause()

                cfg = load_config(home=tmp_path)
                assert cfg.firewall_port_open is False


def test_ensure_firewall_port():
    """ensure re-checks after opening, it does not trust the open command alone."""
    with patch("riptide.core.firewall.check_firewall_port", return_value=True):
        assert ensure_firewall_port(50000) == (True, False, True)
    # Closed, open command runs, re-check finds it open.
    with patch("riptide.core.firewall.check_firewall_port", side_effect=[False, True]):
        with patch("riptide.core.firewall.open_firewall_port", return_value=True):
            assert ensure_firewall_port(50000) == (False, True, True)
    # Closed, open command claims success, but re-check still finds it
    # closed, for example when a block rule still exists.
    with patch("riptide.core.firewall.check_firewall_port", side_effect=[False, False]):
        with patch("riptide.core.firewall.open_firewall_port", return_value=True):
            assert ensure_firewall_port(50000) == (False, False, False)


def test_firewall_check_windows_block_wins_and_udp_ignored():
    """A block rule beats an allow rule, and a UDP rule is not a TCP open."""
    sep = "-" * 70
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        allow_block = f"""Rule Name:                            Riptide
{sep}
Enabled:                              Yes
Direction:                            In
Action:                               Allow
Protocol:                             TCP
LocalPort:                            50000

Rule Name:                            Block Riptide
{sep}
Enabled:                              Yes
Direction:                            In
Action:                               Block
Protocol:                             TCP
LocalPort:                            50000
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=allow_block)
            assert check_firewall_port(50000) is False
        udp_only = f"""Rule Name:                            Riptide UDP
{sep}
Enabled:                              Yes
Direction:                            In
Action:                               Allow
Protocol:                             UDP
LocalPort:                            50000
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=udp_only)
            assert check_firewall_port(50000) is False


def test_firewall_open_windows_enables_disabled_rule():
    """Add fails when the rule already exists disabled, so open enables it."""
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1, stdout="", stderr="already exists"),
                MagicMock(returncode=0, stdout="Ok."),
            ]
            assert open_firewall_port(50000) is True
            # Second call is the enable, not another add.
            assert mock_run.call_args_list[1][0][0][3] == "set"


def test_manual_firewall_command_contains_port():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        assert "50000" in manual_firewall_command(50000)
        assert "netsh" in manual_firewall_command(50000)
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None):
            assert manual_firewall_command(50000) == "sudo ufw allow 50000/tcp"


def test_firewall_check_windows_port_range():
    """A netsh rule covering a range that includes the port counts as open."""
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        fake = """
Rule Name:                            Riptide
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Allow
Protocol:                             TCP
LocalPort:                            49990-50010
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake)
            assert check_firewall_port(50000) is True
            assert check_firewall_port(60000) is False


def test_firewall_open_linux_uses_sudo_n():
    """Linux open must not prompt for a password, so it uses sudo -n."""
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/ufw" if cmd == "ufw" else None):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                assert open_firewall_port(50000) is True
                first_cmd = mock_run.call_args_list[0][0][0]
                assert first_cmd[0] == "sudo" and first_cmd[1] == "-n"


@pytest.mark.asyncio
async def test_join_screen_router_banner_shown_only_when_closed():
    """Router banner is shown only if port was closed; hidden when port was open."""
    # 1. Port was closed and opened: banner reports success
    app_opened = _JoinTestApp(port_was_closed=True, firewall_opened=True)
    async with app_opened.run_test(size=(100, 40)) as pilot:
        screen = app_opened.screen
        router_banner = screen.query_one("#router_banner", Static)
        text = router_banner.render().plain
        assert "opened automatically" in text
        assert "router settings" in text
        assert router_banner.styles.display == "block"

    # 2. Port was closed and opening failed: banner reports failure, not success
    app_failed = _JoinTestApp(port_was_closed=True, firewall_opened=False)
    async with app_failed.run_test(size=(100, 40)) as pilot:
        screen = app_failed.screen
        router_banner = screen.query_one("#router_banner", Static)
        text = router_banner.render().plain
        assert "could not be opened automatically" in text
        assert "router settings" in text
        assert router_banner.styles.display == "block"

    # 3. Port was open: banner remains hidden
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

    def respond_download(self, name: str, request_id: str, allow: bool, on_progress=None):
        self.responded.append((name, request_id, allow))
        if allow and on_progress:
            on_progress(name, 10, 10)
        return True


class _SessionModalApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        from riptide.screens.session_screen import SessionScreen
        self.push_screen(SessionScreen(self._session, role="host"))


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


@pytest.mark.asyncio
async def test_hostname_vs_ip_client_display(tmp_path: Path):
    """Verify hostname is displayed if connection made via hostname, else IP is displayed."""
    from riptide.screens.session_screen import SessionScreen

    # 1. Connection made using hostname
    session_host = _DummySessionForModal(tmp_path)
    session_host.peer_host = "desktop.local"
    session_host.peer_device = "yoga"
    app_host = _SessionModalApp(session_host)
    async with app_host.run_test(size=(100, 35)) as pilot:
        label = app_host.screen.query_one("#peer_client_label", Static).render().plain
        assert "desktop.local" in label

    # 2. Connection made using IP
    session_ip = _DummySessionForModal(tmp_path)
    session_ip.peer_host = "192.168.1.100"
    session_ip.peer_device = "yoga"
    app_ip = _SessionModalApp(session_ip)
    async with app_ip.run_test(size=(100, 35)) as pilot:
        label = app_ip.screen.query_one("#peer_client_label", Static).render().plain
        assert "192.168.1.100" in label


@pytest.mark.asyncio
async def test_file_list_grey_text_color_is_brightened(tmp_path: Path):
    """Verify file manager grey text is brightened closer to #E0E0E0."""
    (tmp_path / "sample.txt").write_bytes(b"hello world")
    session = _DummySessionForModal(tmp_path)
    app = _SessionModalApp(session)
    async with app.run_test(size=(100, 35)) as pilot:
        screen = app.screen
        lv = screen.query_one("#cwd_list")
        # Header colors
        hdr_name = screen.query_one(".file-header-name", Label)
        assert hdr_name.styles.color.hex.upper() == "#E0E0E0"


@pytest.mark.asyncio
async def test_focused_file_pointer_and_download_padding(tmp_path: Path):
    """Verify focused file shows > pointer in separate column and download composer has top margin."""
    (tmp_path / "file1.txt").write_bytes(b"aaa")
    (tmp_path / "file2.txt").write_bytes(b"bbb")
    session = _DummySessionForModal(tmp_path)
    app = _SessionModalApp(session)
    async with app.run_test(size=(100, 35)) as pilot:
        screen = app.screen
        lv = screen.query_one("#cwd_list", ListView)
        lv.focus()
        await pilot.pause()

        # Header has pointer placeholder
        hdr_ptr = screen.query_one(".file-header-pointer")
        assert hdr_ptr is not None
        # Child 1 (file1.txt, auto-first index 1 after parent '..') has pointer '❯ ', child 2 has '  '
        ptr1 = lv.children[1].query_one(".file-pointer", Label).render().plain
        ptr2 = lv.children[2].query_one(".file-pointer", Label).render().plain
        assert "❯" in ptr1
        assert "❯" not in ptr2

        # Move down: next item (file2.txt) gets pointer
        await pilot.press("down")
        await pilot.pause()

        ptr1_after = lv.children[1].query_one(".file-pointer", Label).render().plain
        ptr2_after = lv.children[2].query_one(".file-pointer", Label).render().plain
        assert "❯" not in ptr1_after
        assert "❯" in ptr2_after

        # Download section has top margin
        dl_composer = screen.query_one("#download_composer")
        assert dl_composer.styles.margin.top == 2
