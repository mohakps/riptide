"""First Create Server click: create the firewall rule once,
record it in config, and trust that record on later clicks.

This replaces the old click-time check. The old check asked ufw
for the port status as a normal user, ufw refused to answer
without root, and the check mistook that silence for "the port
is open", so the rule was never re-added after it was deleted.
The setup does not check at all: it creates the rule, trusts
the create command's own success, and records it in the
existing firewall_port_open config property. The setup runs
only on a Create Server click, never at app launch, so a
Join-only user is never prompted.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import OptionList

import riptide.core.firewall as fw
from riptide.app import RiptideApp
from riptide.core.config import Config, load_config, save_config
from riptide.screens.create import CreateScreen
from riptide.screens.menu import MenuScreen
from riptide.theme import CSS


class _MenuApp(App):
    CSS = CSS

    def compose(self):
        yield MenuScreen()


def test_setup_plain_open_success_needs_no_prompt():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.open_firewall_port", return_value=True) as mock_open:
            with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
                assert fw.setup_firewall_port(50000) == "opened"
                mock_open.assert_called_once_with(50000)
                mock_elev.assert_not_called()


def test_setup_pkexec_success_never_consults_the_check():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.open_firewall_port", return_value=False):
            with patch("riptide.core.firewall.elevated_open_firewall_port", return_value="opened") as mock_elev:
                with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                    assert fw.setup_firewall_port(50000) == "opened"
                    mock_elev.assert_called_once()
                    mock_check.assert_not_called()


def test_setup_cancelled_and_failed():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.open_firewall_port", return_value=False):
            with patch("riptide.core.firewall.elevated_open_firewall_port", return_value="cancelled"):
                assert fw.setup_firewall_port(50000) == "cancelled"
            with patch("riptide.core.firewall.elevated_open_firewall_port", return_value="failed"):
                assert fw.setup_firewall_port(50000) == "failed"


def test_setup_rejects_bad_ports_without_prompting():
    assert fw.setup_firewall_port(0) == "failed"
    assert fw.setup_firewall_port(70000) == "failed"


def test_setup_windows_block_rule_fails_without_prompting():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall.windows_block_rule_exists", return_value=True):
            with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
                assert fw.setup_firewall_port(50000) == "failed"
                mock_elev.assert_not_called()


def test_setup_friend_scenario_unreadable_ufw_still_opens():
    """The friend's scenario: ufw refuses even to be read as a
    normal user, so the old check wrongly said open. The setup
    does not read ufw at all: the plain open fails, the pkexec
    create runs, and its zero exit code means the rule is in."""
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/ufw" if name == "ufw" else None):
            with patch("riptide.core.firewall.subprocess.run", return_value=MagicMock(returncode=1)):
                with patch("riptide.core.firewall._pkexec_run", return_value=0) as mock_pkexec:
                    with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                        assert fw.setup_firewall_port(50000) == "opened"
                        assert mock_pkexec.call_count == 1
                        assert "ufw" in mock_pkexec.call_args[0][0]
                        assert "50000/tcp" in mock_pkexec.call_args[0][0]
                        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_app_launch_does_not_touch_the_firewall(tmp_path: Path):
    """No setup at app launch: a Join-only user is never prompted."""
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        with patch("riptide.core.firewall.setup_firewall_port") as mock_setup:
            with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                with patch("riptide.core.firewall.open_firewall_port") as mock_open:
                    with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
                        app = RiptideApp()
                        async with app.run_test() as pilot:
                            await pilot.pause()
                            mock_setup.assert_not_called()
                            mock_check.assert_not_called()
                            mock_open.assert_not_called()
                            mock_elev.assert_not_called()


@pytest.mark.asyncio
async def test_menu_click_setup_done_skips_the_firewall_entirely(tmp_path: Path):
    """Later clicks trust the config record: no check, no open,
    no prompt."""
    app = _MenuApp()
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        save_config(Config(session_port=50000, firewall_port_open=True), home=tmp_path)
        with patch("riptide.core.firewall.setup_firewall_port") as mock_setup:
            with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                with patch("riptide.core.firewall.open_firewall_port") as mock_open:
                    with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
                        async with app.run_test() as pilot:
                            opt_list = app.screen.query_one("#menu_list", OptionList)
                            opt_list.highlighted = 0
                            await pilot.press("enter")
                            await pilot.pause()
                            assert isinstance(app.screen, CreateScreen)
                            assert app.screen.port_was_closed is False
                            assert app.screen.firewall_opened is False
                            assert app.screen.firewall_cancelled is False
                            mock_setup.assert_not_called()
                            mock_check.assert_not_called()
                            mock_open.assert_not_called()
                            mock_elev.assert_not_called()


@pytest.mark.asyncio
async def test_menu_click_runs_setup_when_not_done(tmp_path: Path):
    app = _MenuApp()
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        with patch("riptide.core.firewall.setup_firewall_port", return_value="opened") as mock_setup:
            async with app.run_test() as pilot:
                opt_list = app.screen.query_one("#menu_list", OptionList)
                opt_list.highlighted = 0
                await pilot.press("enter")
                await pilot.pause()
                mock_setup.assert_called_once_with(50000)
                assert load_config(home=tmp_path).firewall_port_open is True
                assert isinstance(app.screen, CreateScreen)
                assert app.screen.port_was_closed is True
                assert app.screen.firewall_opened is True


@pytest.mark.asyncio
async def test_menu_click_runs_setup_when_record_says_closed(tmp_path: Path):
    """A False record means not done, the same as no record."""
    app = _MenuApp()
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        save_config(Config(session_port=50000, firewall_port_open=False), home=tmp_path)
        with patch("riptide.core.firewall.setup_firewall_port", return_value="opened") as mock_setup:
            async with app.run_test() as pilot:
                opt_list = app.screen.query_one("#menu_list", OptionList)
                opt_list.highlighted = 0
                await pilot.press("enter")
                await pilot.pause()
                mock_setup.assert_called_once_with(50000)
                assert load_config(home=tmp_path).firewall_port_open is True
