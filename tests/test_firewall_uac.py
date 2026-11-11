"""UAC on Windows and pkexec on Linux, for the first-launch setup
and the Create Server click.

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
            # A zero exit code means the rule was added. The rule
            # is not re-checked: reading it needs root on ufw
            # systems, and the check wrongly reported open when
            # it could not look.
            with patch("riptide.core.firewall._pkexec_run", return_value=0):
                with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                    assert fw.elevated_open_firewall_port_linux(50000) == "opened"
                    mock_check.assert_not_called()
            with patch("riptide.core.firewall._pkexec_run", return_value=127):
                assert fw.elevated_open_firewall_port_linux(50000) == "failed"


def test_linux_pkexec_missing_is_failed_not_hang():
    with patch("riptide.core.firewall.shutil.which", return_value=None):
        assert fw._pkexec_run(["ufw", "allow", "50000/tcp"]) == 127


def test_linux_firewalld_uses_one_pkexec_call():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/firewall-cmd" if name == "firewall-cmd" else None):
            with patch("riptide.core.firewall._pkexec_run", return_value=0) as mock_pkexec:
                with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                    assert fw.elevated_open_firewall_port_linux(50000) == "opened"
                    assert mock_pkexec.call_count == 1
                    mock_check.assert_not_called()
                    cmd = " ".join(mock_pkexec.call_args[0][0])
                    assert "firewall-cmd --add-port=50000/tcp" in cmd
                    assert "firewall-cmd --reload" in cmd


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
            "riptide.core.firewall.setup_firewall_port",
            return_value="cancelled",
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


def test_any_port_rules_do_not_count_for_port_50000():
    """Any-port rules are program/service rules, not port 50000 rules.

    Regression for v0.15.1: a normal Windows machine has dozens
    of Any-port rules, including Any block rules, and counting
    them made Riptide always report blocked and always skip the
    UAC prompt, even though traffic worked.
    """
    assert fw._port_in_localport("Any", 50000) is False
    assert fw._port_in_localport("50000", 50000) is True
    assert fw._port_in_localport("49990-50010", 50000) is True
    fake = """
Rule Name:                            Some App Block
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Block
Protocol:                             TCP
LocalPort:                            Any

Rule Name:                            Some App Allow
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Allow
Protocol:                             TCP
LocalPort:                            Any
"""
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake)
            assert fw.windows_block_rule_exists(50000) is False
            assert fw.check_firewall_port(50000) is False


def test_explicit_port_allow_wins_over_any_block():
    fake = """
Rule Name:                            Riptide
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Allow
Protocol:                             TCP
LocalPort:                            50000

Rule Name:                            Some App Block
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Block
Protocol:                             TCP
LocalPort:                            Any
"""
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake)
            assert fw.check_firewall_port(50000) is True
            assert fw.windows_block_rule_exists(50000) is False


def test_parser_keeps_rule_name_with_its_fields():
    fake = """
Rule Name:                            Riptide Test
----------------------------------------------------------------------
Enabled:                              Yes
Direction:                            In
Action:                               Allow
Protocol:                             TCP
LocalPort:                            50000
"""
    rules = fw._parse_netsh_rules(fake)
    assert len(rules) == 1
    assert rules[0]["rule name"] == "riptide test"
    assert rules[0]["localport"] == "50000"


def test_windows_elevated_access_denied_is_cancelled():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=False):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=5):
                with patch("riptide.core.firewall.check_firewall_port") as mock_check:
                    assert fw.elevated_open_firewall_port_windows(50000) == "cancelled"
                    mock_check.assert_not_called()
