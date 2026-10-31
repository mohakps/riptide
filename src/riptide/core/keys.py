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


def authorized_keys_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".ssh" / "authorized_keys"


def append_authorized_key(public_key: str, home: Path | None = None) -> bool:
    """Append a public key to authorized_keys if not already present."""
    key = public_key.strip()
    if not key or "PRIVATE KEY" in key:
        return False
    path = authorized_keys_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if key in existing:
        return False
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(key + "\n")
    try:
        path.chmod(0o600)
    except Exception:
        pass
    return True


def ensure_keypair(home: Path | None = None) -> tuple[Path, Path]:
    """Create an ed25519 pair if missing, return (private, public).

    Uses cryptography, because Paramiko's Ed25519Key has no
    generate() in Paramiko 5. The private key is written in
    OpenSSH format, which Paramiko can read back for SSH login.
    """
    private, public = key_paths(home)
    if private.exists() and public.exists():
        return private, public
    private.parent.mkdir(parents=True, exist_ok=True)
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        key = ed25519.Ed25519PrivateKey.generate()
        private.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        ))
        public.write_bytes(key.public_key().public_bytes(
            serialization.Encoding.OpenSSH,
            serialization.PublicFormat.OpenSSH,
        ) + b"\n")
    except ImportError:
        import paramiko
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file(str(private))
        public.write_text(f"{key.get_name()} {key.get_base64()}\n", encoding="utf-8")
    try:
        os.chmod(private, 0o600)
    except Exception:
        pass
    return private, public
