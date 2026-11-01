"""Firewall checks and port configuration across Windows, Linux, and macOS."""
from __future__ import annotations

import platform
import shutil
import subprocess


def get_os() -> str:
    """Return lowercase operating system name ('windows', 'linux', 'darwin', etc.)."""
    return platform.system().lower()


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
                if str(port) in block:
                    props: dict[str, str] = {}
                    for line in block.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            props[k.strip().lower()] = v.strip().lower()

                    if props.get("action") == "allow" and props.get("enabled") == "yes":
                        local_port = props.get("localport", "")
                        ports = [p.strip() for p in local_port.split(",")]
                        if str(port) in ports or "any" in ports:
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
            # 1. Try UFW
            if shutil.which("ufw"):
                res = subprocess.run(["sudo", "ufw", "allow", f"{port}/tcp"], capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    return True
                res = subprocess.run(["ufw", "allow", f"{port}/tcp"], capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    return True

            # 2. Try Firewalld
            if shutil.which("firewall-cmd"):
                res = subprocess.run(
                    ["sudo", "firewall-cmd", f"--add-port={port}/tcp", "--permanent"],
                    capture_output=True, text=True, timeout=10,
                )
                if res.returncode == 0:
                    subprocess.run(["sudo", "firewall-cmd", "--reload"], capture_output=True, text=True, timeout=10)
                    return True

            # 3. Try iptables
            if shutil.which("iptables"):
                res = subprocess.run(
                    ["sudo", "iptables", "-I", "INPUT", "-p", "tcp", "--dport", str(port), "-j", "ACCEPT"],
                    capture_output=True, text=True, timeout=10,
                )
                return res.returncode == 0

            return False
        except Exception:
            return False

    return False
