"""Firewall checks and port configuration across Windows, Linux, and macOS."""
from __future__ import annotations

import platform
import shutil
import subprocess


def get_os() -> str:
    """Return lowercase operating system name ('windows', 'linux', 'darwin', etc.)."""
    return platform.system().lower()


def _port_in_localport(localport: str, port: int) -> bool:
    """True if a netsh LocalPort value covers the port.

    Handles single ports, comma lists, ranges like 49990-50010, and Any.
    """
    for token in localport.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token == "any":
            return True
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

    Rules are separated by a dash line, and each rule starts with a
    Rule Name line. Splitting only on the dash line is fragile when
    the separator length changes, so both are used as boundaries.
    """
    rules: list[dict[str, str]] = []
    props: dict[str, str] = {}
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped and set(stripped) == {"-"}:
            if props:
                rules.append(props)
                props = {}
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
