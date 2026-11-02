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
            if res.returncode != 0:
                return False

            blocks = res.stdout.split("----------------------------------------------------------------------")
            for block in blocks:
                props: dict[str, str] = {}
                for line in block.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        props[k.strip().lower()] = v.strip().lower()

                if props.get("action") == "allow" and props.get("enabled") == "yes":
                    if _port_in_localport(props.get("localport", ""), port):
                        return True
            return False
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


def open_firewall_port(port: int, rule_name: str = "Riptide File Transfer") -> bool:
    """Attempt to open the given port in the OS firewall.

    Checks the operating system first and runs the corresponding rule addition.
    Returns True if the command succeeded, False otherwise.
    """
    os_name = get_os()

    if os_name == "windows":
        try:
            cmd = [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return res.returncode == 0
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
            f'netsh advfirewall firewall add rule name="Riptide File Transfer" '
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
    before any change. opened is True only when an open command
    succeeded for a port that was closed. is_open_now is True when
    the port was already open, or an open command succeeded.
    When opening fails, is_open_now is False and the caller should
    show manual_firewall_command(port) to the user.
    """
    was_open = check_firewall_port(port)
    if was_open:
        return (True, False, True)
    opened = open_firewall_port(port)
    if opened:
        return (False, True, True)
    return (False, False, check_firewall_port(port))
