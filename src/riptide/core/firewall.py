"""Firewall checks and port configuration across Windows, Linux, and macOS."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time


def get_os() -> str:
    """Return lowercase operating system name ('windows', 'linux', 'darwin', etc.)."""
    return platform.system().lower()


def _port_in_localport(localport: str, port: int) -> bool:
    """True if a netsh LocalPort value explicitly covers the port.

    Handles single ports, comma lists, and ranges like 49990-50010.
    A value of Any is deliberately NOT counted: Riptide only
    cares about rules for port 50000, and Any-port rules are
    program or service rules, not port rules. Counting Any made
    a normal Windows machine, with 35 Any-port rules and 2 Any
    block rules, always look blocked and always skip the UAC
    prompt, even though traffic worked.
    """
    for token in localport.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token == "any":
            continue
        if "-" in token:
            try:
                low, high = token.split("-", 1)
                if int(low) <= port <= int(high):
                    return True
            except ValueError:
                continue
        elif token == str(port):
            return True
    return False


def _parse_netsh_rules(stdout: str) -> list[dict[str, str]]:
    """Parse netsh show rule output into one dict per rule.

    Each rule starts with a Rule Name line, followed by a dash
    line, then its fields. The dash line is inside a rule, not
    between rules, so splitting on it used to put the rule name
    in a separate chunk from its fields, and the matcher chunk
    had no name. Dash lines are now ignored, and a rule ends
    only when the next Rule Name line appears after an Action.
    """
    rules: list[dict[str, str]] = []
    props: dict[str, str] = {}
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped and set(stripped) == {"-"}:
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().lower()
        if k == "rule name" and props and "action" in props:
            rules.append(props)
            props = {}
        props[k] = v.strip().lower()
    if props:
        rules.append(props)
    return rules


def _windows_rule_matches(rule: dict[str, str], port: int) -> bool:
    """True if a netsh rule covers inbound TCP traffic on the port."""
    if rule.get("enabled") != "yes":
        return False
    if rule.get("direction") and rule.get("direction") != "in":
        return False
    if rule.get("protocol") and rule.get("protocol") not in ("tcp", "any"):
        return False
    return _port_in_localport(rule.get("localport", ""), port)


def windows_block_rule_exists(port: int) -> bool:
    """True if an enabled inbound block rule covers the port on Windows.

    A block rule wins over an allow rule in Windows Firewall, so an
    allow rule alone does not open the port in that case.
    """
    if get_os() != "windows":
        return False
    try:
        res = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode != 0 or not isinstance(res.stdout, str):
            return False
        return any(
            rule.get("action") == "block" and _windows_rule_matches(rule, port)
            for rule in _parse_netsh_rules(res.stdout)
        )
    except Exception:
        return False


def check_firewall_port(port: int) -> bool:
    """Check if the given port is open in the OS firewall.

    Checks the operating system first and uses the native OS firewall tools.
    Returns True if the port is open/allowed, False if closed.
    """
    os_name = get_os()

    if os_name == "windows":
        try:
            # Query inbound rules using netsh for fast execution (~50ms)
            cmd = ["netsh", "advfirewall", "firewall", "show", "rule", "name=all", "dir=in"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode != 0 or not isinstance(res.stdout, str):
                return False

            rules = _parse_netsh_rules(res.stdout)
            allow = any(
                rule.get("action") == "allow" and _windows_rule_matches(rule, port)
                for rule in rules
            )
            block = any(
                rule.get("action") == "block" and _windows_rule_matches(rule, port)
                for rule in rules
            )
            # A block rule wins over an allow rule, so allow plus
            # block is still closed. Reporting it as open was the
            # silent failure behind a dialler timeout.
            return allow and not block
        except Exception:
            return False

    elif os_name == "linux":
        try:
            # 1. Check UFW if installed
            if shutil.which("ufw"):
                res = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
                if "Status: active" in res.stdout:
                    for line in res.stdout.splitlines():
                        if str(port) in line and "ALLOW" in line.upper():
                            return True
                    return False

            # 2. Check Firewalld if running
            if shutil.which("firewall-cmd"):
                state = subprocess.run(["firewall-cmd", "--state"], capture_output=True, text=True, timeout=5)
                if state.returncode == 0 and "running" in state.stdout:
                    query = subprocess.run(
                        ["firewall-cmd", f"--query-port={port}/tcp"],
                        capture_output=True, text=True, timeout=5,
                    )
                    return query.returncode == 0

            # 3. Check iptables if default policy drops
            if shutil.which("iptables"):
                res = subprocess.run(["iptables", "-L", "INPUT", "-n"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    lines = res.stdout.splitlines()
                    if lines and any(p in lines[0] for p in ("policy DROP", "policy REJECT")):
                        return f"dpt:{port}" in res.stdout

            # 4. Check nftables if it has a drop policy for input
            if shutil.which("nft"):
                res = subprocess.run(["nft", "list", "ruleset"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and "policy drop" in res.stdout.lower():
                    return f"dport {port}" in res.stdout

            # If no firewall daemon is active/blocking, OS firewall allows inbound connections
            return True
        except Exception:
            return True

    elif os_name == "darwin":
        try:
            fw = "/usr/libexec/ApplicationFirewall/socketfilterfw"
            if shutil.which(fw):
                res = subprocess.run([fw, "--getglobalstate"], capture_output=True, text=True, timeout=5)
                if "disabled" in res.stdout.lower():
                    return True
            return True
        except Exception:
            return True

    return True


def open_firewall_port(port: int, rule_name: str = "Riptide") -> bool:
    """Attempt to open the given port in the OS firewall.

    Checks the operating system first and runs the corresponding rule addition.
    Returns True if the command succeeded, False otherwise.
    """
    os_name = get_os()

    if os_name == "windows":
        try:
            # Single-word rule name: a name with spaces was fragile
            # in netsh argument parsing.
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return True
            # Add fails when a rule with that name already exists,
            # which is exactly the case when the user turned the
            # rule off instead of deleting it. Enable it instead.
            for name in (rule_name,):
                res = subprocess.run(
                    [
                        "netsh", "advfirewall", "firewall", "set", "rule",
                        f"name={name}", "new", "enable=yes",
                    ],
                    capture_output=True, text=True, timeout=10,
                )
                if res.returncode == 0:
                    return True
            return False
        except Exception:
            return False

    elif os_name == "linux":
        try:
            # Use sudo -n, never plain sudo. Plain sudo would prompt for a
            # password that the Textual UI cannot show, and would hang
            # until the subprocess timeout. sudo -n fails fast when no
            # passwordless sudo is available, and the direct command
            # still works when Riptide itself runs as root.
            def _try(cmd: list[str]) -> bool:
                for full in ([ "sudo", "-n", *cmd], cmd):
                    try:
                        res = subprocess.run(full, capture_output=True, text=True, timeout=10)
                    except Exception:
                        continue
                    if res.returncode == 0:
                        return True
                return False

            # 1. Try UFW
            if shutil.which("ufw"):
                if _try(["ufw", "allow", f"{port}/tcp"]):
                    return True

            # 2. Try Firewalld
            if shutil.which("firewall-cmd"):
                if _try(["firewall-cmd", f"--add-port={port}/tcp", "--permanent"]):
                    _try(["firewall-cmd", "--reload"])
                    return True

            # 3. Try iptables
            if shutil.which("iptables"):
                if _try(["iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"]):
                    return True

            # 4. Try nftables, common inet filter input chain
            if shutil.which("nft"):
                if _try(["nft", "add", "rule", "inet", "filter", "input", "tcp", "dport", str(port), "accept"]):
                    return True

            return False
        except Exception:
            return False

    return False


def manual_firewall_command(port: int) -> str:
    """The manual command to open the port, for the Create page banner.

    Returns the command for the OS and firewall tool found on this
    machine, or a generic command when none is found. No command is
    run by this function.
    """
    os_name = get_os()
    if os_name == "windows":
        return (
            f"netsh advfirewall firewall add rule name=Riptide "
            f"dir=in action=allow protocol=TCP localport={port}"
        )
    if os_name == "linux":
        if shutil.which("ufw"):
            return f"sudo ufw allow {port}/tcp"
        if shutil.which("firewall-cmd"):
            return f"sudo firewall-cmd --add-port={port}/tcp --permanent && sudo firewall-cmd --reload"
        if shutil.which("iptables"):
            return f"sudo iptables -I INPUT -p tcp --dport {port} -j ACCEPT"
        if shutil.which("nft"):
            return f"sudo nft add rule inet filter input tcp dport {port} accept"
        return f"sudo ufw allow {port}/tcp"
    return ""


def is_elevated() -> bool:
    """True if this process already has admin or root rights.

    Windows: IsUserAnAdmin. Linux and macOS: effective user id 0.
    False on any error, so a failed check never skips a prompt it
    should have shown, it only falls back to the normal path.
    """
    os_name = get_os()
    if os_name == "windows":
        try:
            import ctypes

            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    if os_name in ("linux", "darwin"):
        try:
            return os.geteuid() == 0
        except Exception:
            return False
    return False


def _valid_port(port: int) -> bool:
    return isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535


def _shell_execute_runas(executable: str, parameters: str) -> int:
    """Run one program as administrator on Windows, via ShellExecuteW.

    This is a thin wrapper so tests can mock it without touching
    ctypes. Return value: above 32 means success, 1223 means the
    user cancelled the UAC prompt, 5 means access denied, 32 or
    below otherwise means another error. A standard-user
    credentials prompt returns 5 when the user clicks No, while
    an admin Yes/No prompt returns 1223, both observed live.
    ShellExecuteW returns immediately, it does not wait for the
    program, so the caller must poll check_firewall_port after it.
    """
    try:
        import ctypes

        return int(
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", executable, parameters, None, 0
            )
        )
    except Exception:
        return 0


def _netsh_path() -> str:
    system_root = os.environ.get("SystemRoot", "")
    if system_root:
        return os.path.join(system_root, "System32", "netsh.exe")
    return "netsh"


def _windows_riptide_rule_disabled() -> bool:
    """True if a Riptide rule exists but is turned off on Windows.

    Knowing this before elevating keeps the prompt to one: an
    existing disabled rule is enabled, otherwise a new rule is
    added. A second elevated call would prompt a second time.
    """
    if get_os() != "windows":
        return False
    try:
        res = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=Riptide"],
            capture_output=True, text=True, timeout=10,
        )
        if res.returncode != 0 or not isinstance(res.stdout, str):
            return False
        return any(
            rule.get("rule name") == "riptide" and rule.get("enabled") == "no"
            for rule in _parse_netsh_rules(res.stdout)
        )
    except Exception:
        return False


def _poll_firewall_open(port: int, timeout: float = 30, interval: float = 0.5) -> bool:
    """Poll check_firewall_port until it is open or the timeout ends.

    Used after a UAC prompt, because ShellExecuteW returns before
    the user has answered the prompt and before netsh has run.
    """
    deadline = time.monotonic() + timeout
    while True:
        if check_firewall_port(port):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def elevated_open_firewall_port_windows(port: int, poll_timeout: float = 30) -> str:
    """Open the port with one UAC prompt on Windows.

    Returns "opened", "cancelled", or "failed". The command is
    fixed: rule name Riptide, inbound, allow, TCP, and the port
    as a validated integer. No user input goes into it.
    """
    if not _valid_port(port):
        return "failed"
    if _windows_riptide_rule_disabled():
        parameters = "advfirewall firewall set rule name=Riptide new enable=yes"
    else:
        parameters = (
            "advfirewall firewall add rule name=Riptide "
            f"dir=in action=allow protocol=TCP localport={port}"
        )
    result = _shell_execute_runas(_netsh_path(), parameters)
    if result in (1223, 5):
        return "cancelled"
    if result <= 32:
        return "failed"
    return "opened" if _poll_firewall_open(port, timeout=poll_timeout) else "failed"


def _pkexec_run(cmd: list[str]) -> int:
    """Run one command as root on Linux, via pkexec.

    Returns the program return code, 126 if the user dismissed
    the authentication dialog, or 127 if pkexec is missing, no
    authentication agent is available, or authorisation failed.
    Those codes are from the pkexec manual. The
    --disable-internal-agent flag is deliberate: without it,
    pkexec would register its own textual agent and prompt for
    a password in the terminal, which would fight the Textual
    UI the same way plain sudo did. With the flag, a machine
    with no graphical agent fails fast instead of hanging,
    and the caller falls back to the manual command.
    """
    if not shutil.which("pkexec"):
        return 127
    try:
        res = subprocess.run(
            ["pkexec", "--disable-internal-agent", *cmd],
            capture_output=True, text=True, timeout=120,
        )
        return res.returncode
    except Exception:
        return 127


def elevated_open_firewall_port_linux(port: int) -> str:
    """Open the port with one pkexec prompt on Linux.

    Returns "opened", "cancelled", or "failed". Only the first
    firewall tool found is tried, so at most one prompt appears
    per click. For firewalld, add and reload run in one pkexec
    shell command, again so only one prompt appears.
    """
    if not _valid_port(port):
        return "failed"
    if shutil.which("ufw"):
        cmd = ["ufw", "allow", f"{port}/tcp"]
    elif shutil.which("firewall-cmd"):
        cmd = [
            "/bin/sh", "-c",
            f"firewall-cmd --add-port={port}/tcp --permanent "
            "&& firewall-cmd --reload",
        ]
    elif shutil.which("iptables"):
        cmd = ["iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"]
    elif shutil.which("nft"):
        cmd = ["nft", "add", "rule", "inet", "filter", "input", "tcp", "dport", str(port), "accept"]
    else:
        return "failed"
    result = _pkexec_run(cmd)
    if result == 126:
        return "cancelled"
    if result != 0:
        return "failed"
    return "opened" if check_firewall_port(port) else "failed"


def elevated_open_firewall_port(port: int, poll_timeout: float = 30) -> str:
    """Open the port with an elevation prompt, Windows or Linux.

    Returns "opened", "cancelled", or "failed". Other operating
    systems have no elevation path here and return "failed".
    """
    os_name = get_os()
    if os_name == "windows":
        return elevated_open_firewall_port_windows(port, poll_timeout=poll_timeout)
    if os_name == "linux":
        return elevated_open_firewall_port_linux(port)
    return "failed"


def ensure_firewall_port_with_elevation(
    port: int, poll_timeout: float = 30
) -> tuple[bool, bool, bool, bool]:
    """Check the port, open it if closed, with elevation if needed.

    Returns (was_open, opened, is_open_now, cancelled). This is
    the menu path only: it may prompt once, on the Create Server
    click. The 20 second watch loop must keep using the plain
    ensure_firewall_port, which never prompts.

    Order matters, so no prompt appears when it is not needed:
    already open, then a block rule on Windows (an allow rule
    cannot open it, so prompting would mislead), then already
    elevated, then the plain open (passwordless sudo on Linux),
    and only then the elevation prompt. The command is fixed
    to port 50000 in practice through config.session_port, and
    only that port is ever opened; no program rule is checked
    or relied on.
    """
    was_open = check_firewall_port(port)
    if was_open:
        return (True, False, True, False)
    if get_os() == "windows" and windows_block_rule_exists(port):
        return (False, False, False, False)
    if is_elevated() or get_os() not in ("windows", "linux"):
        _was, opened, is_open_now = ensure_firewall_port(port)
        return (_was, opened, is_open_now, False)
    _was, opened, is_open_now = ensure_firewall_port(port)
    if is_open_now:
        return (_was, opened, is_open_now, False)
    result = elevated_open_firewall_port(port, poll_timeout=poll_timeout)
    if result == "opened":
        return (False, True, True, False)
    if result == "cancelled":
        return (False, False, False, True)
    return (False, False, False, False)


def ensure_firewall_port(port: int) -> tuple[bool, bool, bool]:
    """Check the port, open it if closed, and report the result.

    Returns (was_open, opened, is_open_now). was_open is the state
    before any change. opened and is_open_now are True only when
    a re-check after opening finds the port open. Trusting the
    open command alone was wrong: an allow rule does not open
    the port when a block rule for the same port still exists.
    When opening fails, is_open_now is False and the caller should
    show manual_firewall_command(port) to the user.
    """
    was_open = check_firewall_port(port)
    if was_open:
        return (True, False, True)
    open_firewall_port(port)
    is_open_now = check_firewall_port(port)
    return (False, is_open_now, is_open_now)
