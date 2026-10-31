"""Windows SSH setup helpers. No port numbers in any user-facing text here."""
from __future__ import annotations

import platform
import subprocess


def is_windows() -> bool:
    return platform.system() == "Windows"


def steps() -> list[dict]:
    return [
        {"title": "Install OpenSSH Server", "detail": "Uses the built-in Windows capability. Needs Administrator."},
        {"title": "Start the SSH service", "detail": "Starts it now and sets it to start automatically."},
        {"title": "Check the firewall", "detail": "Verifies the installer-created SSH firewall rule exists."},
        {"title": "Keep password auth off after pairing", "detail": "Key-only auth is required for transfers. Password auth is only a first-run fallback."},
    ]


def _run_powershell(command: str) -> tuple[int, str]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, timeout=120,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def run_setup() -> list[str]:
    """Run the Windows steps. Returns a log. Raises on non-Windows."""
    if not is_windows():
        raise RuntimeError("Windows setup only runs on Windows")
    log: list[str] = []
    code, out = _run_powershell(
        "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"
    )
    log.append(f"Install OpenSSH Server: exit {code} {out[:300]}")
    code, out = _run_powershell("Start-Service sshd; Set-Service -Name sshd -StartupType 'Automatic'")
    log.append(f"Start SSH service: exit {code} {out[:300]}")
    code, out = _run_powershell("Get-NetFirewallRule -DisplayName '*OpenSSH*' | Select-Object -ExpandProperty DisplayName")
    log.append(f"Firewall rules: {out[:300] if out else 'none found'}")
    return log
