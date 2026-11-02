"""UAC on Windows and pkexec on Linux, for the Create Server click only.

All elevation calls are mocked here: this VM is Linux, it has no
Windows UAC and no pkexec binary, so a real prompt can never be
tested here. The live prompt is covered by the Windows and Linux
checklists in the docs, not by these tests. These tests cover the
logic around the prompt: when it appears, when it does not, what
a cancel returns, and that the watch loop never prompts.

No program rule is checked anywhere: only the port 50000 rule
matters, per the user's correction during v0.15.0 work.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import OptionList, Static

import riptide.core.firewall as fw
from riptide.core.config import load_config
from riptide.screens.create import CreateScreen
from riptide.screens.menu import MenuScreen
from riptide.theme import CSS


def test_is_elevated_other_os_is_false():
    with patch("riptide.core.firewall.get_os", return_value="solaris"):
        assert fw.is_elevated() is False


def test_is_elevated_linux_root_and_user():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch.object(os, "geteuid", return_value=0):
            assert fw.is_elevated() is True
        with patch.object(os, "geteuid", return_value=1000):
            assert fw.is_elevated() is False


def test_windows_elevated_cancelled_returns_cancelled_and_prompts_once():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=False):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=1223) as mock_run:
                with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                    assert fw.elevated_open_firewall_port_windows(50000) == "cancelled"
                    assert mock_run.call_count == 1
                    assert "localport=50000" in mock_run.call_args[0][1]
                    # Cancelled: no poll, so no re-check.
                    mock_check.assert_not_called()


def test_windows_elevated_success_uses_add_rule():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=False):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=33) as mock_run:
                with patch("riptide.core.firewall.check_firewall_port", return_value=True):
                    assert fw.elevated_open_firewall_port_windows(50000) == "opened"
                    assert "add rule" in mock_run.call_args[0][1]
                    assert "localport=50000" in mock_run.call_args[0][1]


def test_windows_elevated_disabled_rule_uses_enable_not_add():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=True):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=33) as mock_run:
                with patch("riptide.core.firewall.check_firewall_port", return_value=True):
                    assert fw.elevated_open_firewall_port_windows(50000) == "opened"
                    assert "set rule" in mock_run.call_args[0][1]
                    assert "enable=yes" in mock_run.call_args[0][1]
                    assert "add rule" not in mock_run.call_args[0][1]


def test_windows_elevated_other_error_is_failed():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=False):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=0):
                assert fw.elevated_open_firewall_port_windows(50000) == "failed"


def test_windows_elevated_poll_timeout_is_failed():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=False):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=33):
                with patch("riptide.core.firewall.check_firewall_port", return_value=False):
                    # poll_timeout=0 keeps this test fast.
                    assert fw.elevated_open_firewall_port_windows(50000, poll_timeout=0) == "failed"


def test_elevated_open_rejects_bad_ports_without_prompting():
    with patch("riptide.core.firewall._shell_execute_runas") as mock_run:
        with patch("riptide.core.firewall._pkexec_run") as mock_pkexec:
            assert fw.elevated_open_firewall_port_windows(0) == "failed"
            assert fw.elevated_open_firewall_port_windows(70000) == "failed"
            assert fw.elevated_open_firewall_port_linux(0) == "failed"
            mock_run.assert_not_called()
            mock_pkexec.assert_not_called()


def test_linux_pkexec_cancelled_is_126():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "ufw" else None):
            with patch("riptide.core.firewall._pkexec_run", return_value=126) as mock_pkexec:
                assert fw.elevated_open_firewall_port_linux(50000) == "cancelled"
                assert mock_pkexec.call_count == 1
                assert "ufw" in mock_pkexec.call_args[0][0]
                assert "50000/tcp" in mock_pkexec.call_args[0][0]


def test_linux_pkexec_success_and_failure():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "ufw" else None):
            with patch("riptide.core.firewall._pkexec_run", return_value=0):
                with patch("riptide.core.firewall.check_firewall_port", return_value=True):
                    assert fw.elevated_open_firewall_port_linux(50000) == "opened"
            with patch("riptide.core.firewall._pkexec_run", return_value=127):
                assert fw.elevated_open_firewall_port_linux(50000) == "failed"


def test_linux_pkexec_missing_is_failed_not_hang():
    with patch("riptide.core.firewall.shutil.which", return_value=None):
        assert fw._pkexec_run(["ufw", "allow", "50000/tcp"]) == 127


def test_linux_firewalld_uses_one_pkexec_call():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/firewall-cmd" if name == "firewall-cmd" else None):
            with patch("riptide.core.firewall._pkexec_run", return_value=0) as mock_pkexec:
                with patch("riptide.core.firewall.check_firewall_port", return_value=True):
                    assert fw.elevated_open_firewall_port_linux(50000) == "opened"
                    assert mock_pkexec.call_count == 1
                    cmd = " ".join(mock_pkexec.call_args[0][0])
                    assert "firewall-cmd --add-port=50000/tcp" in cmd
                    assert "firewall-cmd --reload" in cmd


def test_ensure_with_elevation_already_open_prompts_nothing():
    with patch("riptide.core.firewall.check_firewall_port", return_value=True):
        with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
            assert fw.ensure_firewall_port_with_elevation(50000) == (True, False, True, False)
            mock_elev.assert_not_called()


def test_ensure_with_elevation_block_rule_prompts_nothing():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall.check_firewall_port", return_value=False):
            with patch("riptide.core.firewall.windows_block_rule_exists", return_value=True):
                with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
                    assert fw.ensure_firewall_port_with_elevation(50000) == (False, False, False, False)
                    mock_elev.assert_not_called()


def test_ensure_with_elevation_already_elevated_uses_plain_path():
    with patch("riptide.core.firewall.check_firewall_port", return_value=False):
        with patch("riptide.core.firewall.is_elevated", return_value=True):
            with patch("riptide.core.firewall.ensure_firewall_port", return_value=(False, True, True)):
                with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
                    assert fw.ensure_firewall_port_with_elevation(50000) == (False, True, True, False)
                    mock_elev.assert_not_called()


def test_ensure_with_elevation_plain_open_first_then_prompt():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.check_firewall_port", return_value=False):
            with patch("riptide.core.firewall.is_elevated", return_value=False):
                with patch("riptide.core.firewall.ensure_firewall_port", return_value=(False, True, True)):
                    with patch("riptide.core.firewall.elevated_open_firewall_port") as mock_elev:
                        assert fw.ensure_firewall_port_with_elevation(50000) == (False, True, True, False)
                        mock_elev.assert_not_called()


def test_ensure_with_elevation_cancelled_and_opened():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.check_firewall_port", return_value=False):
            with patch("riptide.core.firewall.is_elevated", return_value=False):
                with patch("riptide.core.firewall.ensure_firewall_port", return_value=(False, False, False)):
                    with patch("riptide.core.firewall.elevated_open_firewall_port", return_value="cancelled"):
                        assert fw.ensure_firewall_port_with_elevation(50000) == (False, False, False, True)
                    with patch("riptide.core.firewall.elevated_open_firewall_port", return_value="opened"):
                        assert fw.ensure_firewall_port_with_elevation(50000) == (False, True, True, False)
                    with patch("riptide.core.firewall.elevated_open_firewall_port", return_value="failed"):
                        assert fw.ensure_firewall_port_with_elevation(50000) == (False, False, False, False)


class _CancelledApp(App):
    CSS = CSS

    def on_mount(self):
        self.push_screen(
            CreateScreen(port_was_closed=True, firewall_opened=False, firewall_cancelled=True)
        )


@pytest.mark.asyncio
async def test_create_screen_cancelled_banner():
    app = _CancelledApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        banner = app.screen.query_one("#router_banner", Static)
        text = banner.render().plain
        assert "cancelled the admin prompt" in text
        assert "Create Server again" in text
        assert banner.styles.display == "block"


class _MenuCancelledApp(App):
    CSS = CSS

    def compose(self):
        yield MenuScreen()


@pytest.mark.asyncio
async def test_menu_cancelled_saves_closed_and_passes_cancelled(tmp_path: Path):
    app = _MenuCancelledApp()
    with patch("riptide.core.config.config_dir", return_value=tmp_path):
        with patch(
            "riptide.core.firewall.ensure_firewall_port_with_elevation",
            return_value=(False, False, False, True),
        ):
            async with app.run_test() as pilot:
                opt_list = app.screen.query_one("#menu_list", OptionList)
                opt_list.highlighted = 0
                await pilot.press("enter")
                await pilot.pause()
                cfg = load_config(home=tmp_path)
                assert cfg.firewall_port_open is False
                assert isinstance(app.screen, CreateScreen)
                assert app.screen.firewall_cancelled is True
