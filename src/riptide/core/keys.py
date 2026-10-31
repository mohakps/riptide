"""SSH key handling. Keys live in ~/.ssh/, never in ~/.riptide/."""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path


def key_paths(home: Path | None = None) -> tuple[Path, Path]:
    ssh_dir = (home or Path.home()) / ".ssh"
    return ssh_dir / "id_riptide", ssh_dir / "id_riptide.pub"


def public_key_text(home: Path | None = None) -> str | None:
    _, pub = key_paths(home)
    if pub.exists():
        return pub.read_text(encoding="utf-8").strip()
    return None


def fingerprint_of_public_key(public_key: str) -> str:
    """OpenSSH-style SHA256 fingerprint, without ever handling a private key."""
    parts = public_key.strip().split()
    if len(parts) < 2:
        return ""
    try:
        blob = base64.b64decode(parts[1])
    except Exception:
        return ""
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return f"SHA256:{digest}"


def ensure_keypair(home: Path | None = None) -> tuple[Path, Path]:
    """Create an ed25519 pair if missing, return (private, public)."""
    import paramiko

    private, public = key_paths(home)
    if private.exists() and public.exists():
        return private, public
    private.parent.mkdir(parents=True, exist_ok=True)
    key = paramiko.Ed25519Key.generate()
    key.write_private_key_file(str(private))
    try:
        os.chmod(private, 0o600)
    except Exception:
        pass
    public.write_text(f"{key.get_name()} {key.get_base64()}\n", encoding="utf-8")
    return private, public
