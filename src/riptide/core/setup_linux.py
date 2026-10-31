"""Linux / Arch SSH setup helpers. No port numbers in user-facing text."""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


def is_linux() -> bool:
    return platform.system() == "Linux"


def package_manager() -> str:
    for candidate in ("pacman", "apt", "dnf", "zypper"):
        if shutil.which(candidate):
            return candidate
    return ""


def steps() -> list[dict]:
    manager = package_manager()
    install = {
        "pacman": "sudo pacman -S --noconfirm openssh",
        "apt": "sudo apt update && sudo apt install -y openssh-server",
        "dnf": "sudo dnf install -y openssh-server",
        "zypper": "sudo zypper install -y openssh",
    }.get(manager, "Install openssh with your distro package manager")
    return [
        {"title": "Install OpenSSH", "detail": install},
        {"title": "Enable and start the SSH service", "detail": "sudo systemctl enable --now sshd"},
        {"title": "Check the firewall", "detail": "Allow SSH in ufw, firewalld, or iptables if one is active."},
        {"title": "Keep password auth off after pairing", "detail": "Key-only auth is required for transfers."},
    ]


def run_setup() -> list[str]:
    if not is_linux():
        raise RuntimeError("Linux setup only runs on Linux")
    log: list[str] = []
    manager = package_manager()
    if manager == "pacman":
        cmd = ["sudo", "pacman", "-S", "--noconfirm", "openssh"]
    elif manager == "apt":
        cmd = ["sudo", "apt", "install", "-y", "openssh-server"]
    elif manager == "dnf":
        cmd = ["sudo", "dnf", "install", "-y", "openssh-server"]
    else:
        return ["No supported package manager found. Install openssh manually, then enable sshd."]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    log.append(f"Install openssh: exit {result.returncode}")
    result = subprocess.run(["sudo", "systemctl", "enable", "--now", "sshd"],
                            capture_output=True, text=True, timeout=120)
    log.append(f"Enable sshd: exit {result.returncode} {(result.stdout + result.stderr)[:300]}")
    return log


def sshd_config_has_pubkey_only() -> bool:
    for candidate in (Path("/etc/ssh/sshd_config"), Path("/etc/ssh/sshd_config.d")):
        if candidate.is_file() and "PasswordAuthentication no" in candidate.read_text(errors="ignore"):
            return True
    return False
