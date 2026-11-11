"""Section 4: firewall rule Private, Public only, and riptide --cleanup.

Tests cover the profile in the add command, the delete commands
per tool, the cleanup confirmation and abort order, and the
Create page note for an old all-profile rule. All elevation
calls are mocked: this VM is Linux, it has no Windows UAC and
no pkexec binary, so a real prompt can never be tested here.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import Static

import riptide.core.firewall as fw
from riptide.app import build_parser, main
from riptide.core.cleanup import run_cleanup
from riptide.core.config import Config, Peer, save_config
from riptide.screens.create import CreateScreen
from riptide.theme import CSS


def _netsh_show(name="Riptide", profile="Private,Public", enabled="Yes", action="Allow", localport="50000"):
    return f"""
Rule Name:                            {name}
----------------------------------------------------------------------
Enabled:                              {enabled}
Direction:                            In
Profiles:                             {profile}
Action:                               {action}
Protocol:                             TCP
LocalPort:                            {localport}
"""


def test_windows_add_command_uses_private_public_profile():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert fw.open_firewall_port(50000) is True
            cmd = mock_run.call_args[0][0]
            assert "profile=private,public" in cmd
            assert "localport=50000" in cmd


def test_windows_enable_fallback_sets_profile():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [MagicMock(returncode=1), MagicMock(returncode=0)]
            assert fw.open_firewall_port(50000) is True
            cmd = mock_run.call_args[0][0]
            assert "set" in cmd and "enable=yes" in cmd
            assert "profile=private,public" in cmd


def test_windows_elevated_add_parameters_include_profile():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=False):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=33) as mock_run:
                with patch("riptide.core.firewall.check_firewall_port", return_value=True):
                    assert fw.elevated_open_firewall_port_windows(50000) == "opened"
                    params = mock_run.call_args[0][1]
                    assert "add rule" in params
                    assert "profile=private,public" in params


def test_windows_elevated_enable_parameters_include_profile():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall._windows_riptide_rule_disabled", return_value=True):
            with patch("riptide.core.firewall._shell_execute_runas", return_value=33) as mock_run:
                with patch("riptide.core.firewall.check_firewall_port", return_value=True):
                    assert fw.elevated_open_firewall_port_windows(50000) == "opened"
                    params = mock_run.call_args[0][1]
                    assert "set rule" in params
                    assert "enable=yes" in params
                    assert "profile=private,public" in params


def test_manual_command_includes_profile():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        assert "profile=private,public" in fw.manual_firewall_command(50000)


def test_windows_rule_profile_reads_private_public_and_any():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=_netsh_show(profile="Private,Public"))
            assert fw.windows_riptide_rule_profile(50000) == "private,public"
            mock_run.return_value = MagicMock(returncode=0, stdout=_netsh_show(profile="Any"))
            assert fw.windows_riptide_rule_profile(50000) == "any"


def test_windows_rule_profile_none_when_missing_or_disabled():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="No rules match the specified criteria.")
            assert fw.windows_riptide_rule_profile(50000) is None
            mock_run.return_value = MagicMock(returncode=0, stdout=_netsh_show(enabled="No"))
            assert fw.windows_riptide_rule_profile(50000) is None
            mock_run.return_value = MagicMock(returncode=0, stdout=_netsh_show(localport="49999"))
            assert fw.windows_riptide_rule_profile(50000) is None


def test_windows_rule_exists():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=_netsh_show())
            assert fw.windows_riptide_rule_exists() is True
            mock_run.return_value = MagicMock(returncode=1, stdout="No rules match the specified criteria.")
            assert fw.windows_riptide_rule_exists() is False


def test_remove_rejects_bad_ports():
    assert fw.remove_firewall_port(0) == "failed"
    assert fw.remove_firewall_port(70000) == "failed"


def test_linux_delete_ufw_command_and_removed():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/ufw" if name == "ufw" else None):
            with patch("riptide.core.firewall.subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")):
                with patch("riptide.core.firewall._pkexec_run_output", return_value=(0, "")) as mock_pkexec:
                    assert fw.remove_firewall_port(50000) == "removed"
                    assert mock_pkexec.call_count == 1
                    cmd = mock_pkexec.call_args[0][0]
                    assert "ufw" in cmd
                    assert "delete" in cmd
                    assert "allow" in cmd
                    assert "50000/tcp" in cmd


def test_linux_delete_ufw_not_found_without_pkexec():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/ufw" if name == "ufw" else None):
            with patch("riptide.core.firewall.subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="Could not delete non-existent rule.")):
                with patch("riptide.core.firewall._pkexec_run_output") as mock_pkexec:
                    assert fw.remove_firewall_port(50000) == "not_found"
                    mock_pkexec.assert_not_called()


def test_linux_delete_pkexec_cancelled():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/ufw" if name == "ufw" else None):
            with patch("riptide.core.firewall.subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="")):
                with patch("riptide.core.firewall._pkexec_run_output", return_value=(126, "")):
                    assert fw.remove_firewall_port(50000) == "cancelled"


def test_linux_delete_no_tool_is_not_found():
    with patch("riptide.core.firewall.shutil.which", return_value=None):
        assert fw.remove_firewall_port(50000) == "not_found"


def test_linux_delete_firewalld_missing_is_not_found_without_prompt():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/firewall-cmd" if name == "firewall-cmd" else None):
            with patch("riptide.core.firewall.subprocess.run", return_value=MagicMock(returncode=1)) as mock_run:
                with patch("riptide.core.firewall._pkexec_run_output") as mock_pkexec:
                    assert fw.remove_firewall_port(50000) == "not_found"
                    mock_pkexec.assert_not_called()
                    assert "--query-port=50000/tcp" in mock_run.call_args[0][0]


def test_linux_delete_iptables_bad_rule_is_not_found():
    with patch("riptide.core.firewall.get_os", return_value="linux"):
        with patch("riptide.core.firewall.shutil.which", side_effect=lambda name: "/usr/bin/iptables" if name == "iptables" else None):
            with patch("riptide.core.firewall.subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="iptables: Bad rule (does a matching rule exist in that chain?).")):
                with patch("riptide.core.firewall._pkexec_run_output") as mock_pkexec:
                    assert fw.remove_firewall_port(50000) == "not_found"
                    mock_pkexec.assert_not_called()


def test_windows_delete_no_rule_is_not_found_without_prompt():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="No rules match the specified criteria.")
            with patch("riptide.core.firewall._shell_execute_runas") as mock_runas:
                assert fw.remove_firewall_port(50000) == "not_found"
                mock_runas.assert_not_called()


def test_windows_delete_elevated_removes():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall.is_elevated", return_value=True):
            with patch("riptide.core.firewall.windows_riptide_rule_exists", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
                    assert fw.remove_firewall_port(50000) == "removed"
                    cmd = mock_run.call_args[0][0]
                    assert "delete" in cmd
                    assert "name=Riptide" in cmd


def test_windows_delete_runas_cancelled():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall.is_elevated", return_value=False):
            with patch("riptide.core.firewall.windows_riptide_rule_exists", return_value=True):
                with patch("riptide.core.firewall._shell_execute_runas", return_value=1223):
                    assert fw.remove_firewall_port(50000) == "cancelled"


def test_windows_delete_runas_success_polls_until_gone():
    with patch("riptide.core.firewall.get_os", return_value="windows"):
        with patch("riptide.core.firewall.is_elevated", return_value=False):
            with patch("riptide.core.firewall.windows_riptide_rule_exists", return_value=True):
                with patch("riptide.core.firewall._shell_execute_runas", return_value=33) as mock_runas:
                    with patch("riptide.core.firewall.check_firewall_port", return_value=False):
                        assert fw.remove_firewall_port(50000) == "removed"
                        params = mock_runas.call_args[0][1]
                        assert "delete rule name=Riptide" in params


def _seed_home(tmp_path: Path):
    d = tmp_path / ".riptide"
    d.mkdir()
    (d / "identity.key").write_text("key")
    (d / "identity.crt").write_text("cert")
    save_config(Config(session_port=50000, peers=[Peer(name="friend", host="192.0.2.10", fingerprint="abc")]), home=tmp_path)


def test_cleanup_yes_removes_everything(tmp_path: Path, capsys):
    _seed_home(tmp_path)
    with patch("riptide.core.cleanup.remove_firewall_port", return_value="removed") as mock_remove:
        assert run_cleanup(yes=True, home=tmp_path) == 0
        mock_remove.assert_called_once_with(50000)
        assert not (tmp_path / ".riptide").exists()
        out = capsys.readouterr().out
        assert "Firewall rule: removed" in out
        assert "Identity: deleted" in out
        assert "Saved peers: deleted" in out
        assert "router" in out.lower()
        assert "pip uninstall riptide-transfer" in out


def test_cleanup_second_run_reports_not_found(tmp_path: Path, capsys):
    with patch("riptide.core.cleanup.remove_firewall_port", return_value="not_found"):
        assert run_cleanup(yes=True, home=tmp_path) == 0
        out = capsys.readouterr().out
        assert "not found" in out


def test_cleanup_declined_deletes_nothing(tmp_path: Path):
    _seed_home(tmp_path)
    with patch("riptide.core.cleanup.remove_firewall_port") as mock_remove:
        with patch("builtins.input", return_value="no"):
            assert run_cleanup(yes=False, home=tmp_path) == 1
        mock_remove.assert_not_called()
        assert (tmp_path / ".riptide" / "identity.key").exists()
        assert (tmp_path / ".riptide" / "config.toml").exists()


def test_cleanup_firewall_cancelled_aborts_and_deletes_nothing(tmp_path: Path):
    _seed_home(tmp_path)
    with patch("riptide.core.cleanup.remove_firewall_port", return_value="cancelled"):
        with patch("builtins.input", return_value="YES"):
            assert run_cleanup(yes=False, home=tmp_path) == 1
        assert (tmp_path / ".riptide" / "identity.key").exists()
        assert (tmp_path / ".riptide" / "config.toml").exists()


def test_cleanup_firewall_failed_aborts_and_deletes_nothing(tmp_path: Path):
    _seed_home(tmp_path)
    with patch("riptide.core.cleanup.remove_firewall_port", return_value="failed"):
        with patch("builtins.input", return_value="YES"):
            assert run_cleanup(yes=False, home=tmp_path) == 1
        assert (tmp_path / ".riptide" / "identity.key").exists()


def test_cleanup_yes_flag_skips_prompt(tmp_path: Path):
    _seed_home(tmp_path)
    with patch("riptide.core.cleanup.remove_firewall_port", return_value="removed"):
        with patch("builtins.input", side_effect=AssertionError("should not prompt")):
            assert run_cleanup(yes=True, home=tmp_path) == 0


def test_cli_cleanup_flag_and_yes_requires_cleanup():
    parser = build_parser()
    args = parser.parse_args(["--cleanup"])
    assert args.cleanup is True and args.yes is False
    with pytest.raises(SystemExit):
        main(["--yes"])


def test_main_cleanup_runs_and_exits():
    with patch("riptide.core.cleanup.run_cleanup", return_value=0) as mock_clean:
        assert main(["--cleanup"]) == 0
        mock_clean.assert_called_once_with(yes=False)
    with patch("riptide.core.cleanup.run_cleanup", return_value=0) as mock_clean:
        assert main(["--cleanup", "--yes"]) == 0
        mock_clean.assert_called_once_with(yes=True)


class _ProfileApp(App):
    CSS = CSS

    def on_mount(self):
        self.push_screen(CreateScreen())


@pytest.mark.asyncio
async def test_create_screen_shows_profile_note():
    app = _ProfileApp()
    with patch("riptide.core.firewall.windows_riptide_rule_profile", return_value="any"):
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            banner = app.screen.query_one("#router_banner", Static)
            text = banner.render().plain
            assert "all profiles" in text
            assert "riptide --cleanup" in text
            assert banner.styles.display == "block"


@pytest.mark.asyncio
async def test_create_screen_no_profile_note_for_private_public():
    app = _ProfileApp()
    with patch("riptide.core.firewall.windows_riptide_rule_profile", return_value="private,public"):
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            banner = app.screen.query_one("#router_banner", Static)
            assert banner.render().plain == ""
