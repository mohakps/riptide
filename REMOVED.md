# Removed code

This file records code removed in v0.14.0, so a single function or file can be brought back without rolling back the whole commit. Each entry gives the original path, why it was removed, and the full code as it was at removal time. To restore one entry, copy its code block back into the file named in its heading, and restore its imports and callers if any.

Textual framework handlers (on_mount, on_key, on_button_pressed, on_input_submitted, and similar) were NOT treated as unused, even when no production code calls them directly, because Textual dispatches them by name.

## _split_pasted

- Original path: `src/riptide/core/file_select.py`
- Reason: Unused in production. The typed-name / Tab completion / drag-and-drop paste input was removed when files became selectable only from the file manager. These helpers were only exercised by tests.

```python
def _split_pasted(text: str) -> list[str]:
    """Split pasted text, honouring quotes, Windows paths, and spaces."""
    text = text.strip()
    if not text:
        return []
    # shlex with posix=False keeps Windows backslashes intact.
    try:
        parts = shlex.split(text, posix=False)
    except ValueError:
        parts = re.findall(r'"([^"]+)"|\'([^\']+)\'|(\S+)', text)
        parts = [a or b or c for a, b, c in parts]  # type: ignore[assignment]
    cleaned: list[str] = []
    for part in parts:
        part = part.strip().strip(",")
        if len(part) >= 2 and part[0] == part[-1] and part[0] in "\"'":
            part = part[1:-1]
        if part:
            cleaned.append(part)
    return cleaned
```

## _resolve

- Original path: `src/riptide/core/file_select.py`
- Reason: Unused in production. The typed-name / Tab completion / drag-and-drop paste input was removed when files became selectable only from the file manager. These helpers were only exercised by tests.

```python
def _resolve(token: str, cwd: Path) -> Path | None:
    token = token.strip()
    if not token:
        return None
    # Windows absolute path, e.g. C:\Users\... or C:/Users/...
    if re.match(r"^[A-Za-z]:[\\/]", token):
        candidate = Path(token)
    else:
        candidate = Path(token).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
    try:
        if candidate.is_file():
            return candidate
    except OSError:
        return None
    return None
```

## parse_dropped_text

- Original path: `src/riptide/core/file_select.py`
- Reason: Unused in production. The typed-name / Tab completion / drag-and-drop paste input was removed when files became selectable only from the file manager. These helpers were only exercised by tests.

```python
def parse_dropped_text(text: str, cwd: Path) -> list[Path]:
    """Parse typed or dropped text into existing files, deduped, in order."""
    seen: set[Path] = set()
    out: list[Path] = []
    for token in _split_pasted(text):
        resolved = _resolve(token, cwd)
        if resolved is not None and resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out
```

## complete

- Original path: `src/riptide/core/file_select.py`
- Reason: Unused in production. The typed-name / Tab completion / drag-and-drop paste input was removed when files became selectable only from the file manager. These helpers were only exercised by tests.

```python
def complete(prefix: str, cwd: Path) -> list[str]:
    """Tab completion candidates for a prefix, relative or absolute.

    Absolute paths used to be broken: the old code returned only
    the bare entry name for an absolute prefix, so completing
    ``/home/user/doc`` replaced the input with ``document.pdf``
    and lost the directory. Now the returned candidate keeps
    the full absolute prefix, including a trailing slash when
    the prefix itself ends in a separator.
    """
    prefix = prefix.strip()
    if not prefix:
        return []
    if prefix.startswith("~"):
        prefix = str(Path(prefix).expanduser())
    sep = "\\" if "\\" in prefix else "/"
    # Trailing separator: complete inside that directory.
    if prefix.endswith(("/", "\\")):
        directory = Path(prefix).expanduser()
        if re.match(r"^[A-Za-z]:[\\/]", prefix):
            directory = Path(prefix)
        if not directory.is_dir():
            return []
        return [f"{str(directory / e.name)}{sep if e.is_dir() else ''}"
                for e in sorted(directory.iterdir(), key=lambda p: p.name.lower())]
    raw = Path(prefix)
    is_win_abs = bool(re.match(r"^[A-Za-z]:[\\/]", prefix))
    if raw.is_absolute() or is_win_abs:
        directory = raw.parent
        stem = raw.name
        # Keep the absolute directory in the candidate, e.g.
        # /home/user/do -> /home/user/document.pdf
        base = str(directory)
        if not base.endswith(("/", "\\")):
            base += sep
    else:
        if "/" in prefix or "\\" in prefix:
            directory = cwd / raw.parent
            stem = raw.name
            base = str(raw.parent).replace("\\", "/") + "/"
        else:
            directory = cwd
            stem = prefix
            base = ""
    try:
        directory = directory.expanduser()
    except Exception:
        pass
    if not directory.is_dir():
        return []
    out: list[str] = []
    for entry in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.lower().startswith(stem.lower()):
            suffix = "/" if entry.is_dir() else ""
            out.append(f"{base}{entry.name}{suffix}")
    return out
```

## common_prefix

- Original path: `src/riptide/core/file_select.py`
- Reason: Unused in production. The typed-name / Tab completion / drag-and-drop paste input was removed when files became selectable only from the file manager. These helpers were only exercised by tests.

```python
def common_prefix(candidates: list[str]) -> str:
    """Longest common prefix of all candidates, or '' if none."""
    if not candidates:
        return ""
    prefix = candidates[0]
    for cand in candidates[1:]:
        while not cand.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix
```

## list_cwd_files

- Original path: `src/riptide/core/file_select.py`
- Reason: Unused in production. The typed-name / Tab completion / drag-and-drop paste input was removed when files became selectable only from the file manager. These helpers were only exercised by tests.

```python
def list_cwd_files(cwd: Path) -> list[Path]:
    if not cwd.is_dir():
        return []
    return sorted(
        (p for p in cwd.iterdir() if p.is_file()),
        key=lambda p: p.name.lower(),
    )
```

## sha256_file

- Original path: `src/riptide/core/transfer.py`
- Reason: Unused in production. Transfers now run over the TLS session in core/session.py, which hashes inline. download_file, upload_files and remote_sha256 are SFTP / SSH exec helpers from the old SSH design.

```python
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

## remote_sha256

- Original path: `src/riptide/core/transfer.py`
- Reason: Unused in production. Transfers now run over the TLS session in core/session.py, which hashes inline. download_file, upload_files and remote_sha256 are SFTP / SSH exec helpers from the old SSH design.

```python
def remote_sha256(ssh_client, remote_path: str) -> str | None:
    """Best-effort remote SHA-256 via an exec channel, or None if unavailable."""
    commands = [
        f"sha256sum {remote_path!r}",
        f"powershell -NoProfile -Command \"(Get-FileHash -Algorithm SHA256 {remote_path!r}).Hash\"",
    ]
    for command in commands:
        try:
            _, stdout, _ = ssh_client.exec_command(command)
            out = stdout.read().decode(errors="ignore").strip()
        except Exception:
            continue
        if not out:
            continue
        token = out.split()[0].strip().lower()
        if len(token) == 64 and all(c in "0123456789abcdef" for c in token):
            return token
    return None
```

## download_file

- Original path: `src/riptide/core/transfer.py`
- Reason: Unused in production. Transfers now run over the TLS session in core/session.py, which hashes inline. download_file, upload_files and remote_sha256 are SFTP / SSH exec helpers from the old SSH design.

```python
def download_file(sftp, remote_name: str, local_dir: Path, on_progress=None) -> Path:
    """Download one file via SFTP, writing .part then renaming after size check.
    Returns the final local path. Raises on failure."""
    local_dir = Path(local_dir)
    part = local_dir / f"{Path(remote_name).name}.part"
    final = local_dir / Path(remote_name).name
    size = int(sftp.stat(remote_name).st_size)
    with sftp.open(remote_name, "rb") as source, open(part, "wb") as dest:
        sent = 0
        while True:
            chunk = source.read(1024 * 128)
            if not chunk:
                break
            dest.write(chunk)
            sent += len(chunk)
            if on_progress is not None:
                on_progress(Path(remote_name).name, sent, size)
    if part.stat().st_size == size:
        part.replace(final)
        return final
    raise IOError(f"size mismatch downloading {remote_name}")
```

## upload_files

- Original path: `src/riptide/core/transfer.py`
- Reason: Unused in production. Transfers now run over the TLS session in core/session.py, which hashes inline. download_file, upload_files and remote_sha256 are SFTP / SSH exec helpers from the old SSH design.

```python
def upload_files(sftp, local_paths: list[Path], remote_dir: str, progress: TransferProgress,
                 on_file: object = None) -> list[str]:
    """Upload files resumably, writing .part then renaming after verification.

    ``sftp`` is a Paramiko SFTPClient (or a compatible object in tests).
    ``on_file`` if given is called as on_file(name, sent_for_file, size).
    Returns the list of remote final paths.
    """
    remote_dir = remote_dir.rstrip("/") or "."
    uploaded: list[str] = []
    base_sent = 0
    for local in local_paths:
        size = local.stat().st_size
        remote_part = f"{remote_dir}/{local.name}.part"
        remote_final = f"{remote_dir}/{local.name}"
        offset = 0
        try:
            offset = int(sftp.stat(remote_part).st_size)
            offset = min(offset, size)
        except Exception:
            offset = 0
        mode = "ab" if offset else "wb"
        with open(local, "rb") as source:
            source.seek(offset)
            with sftp.open(remote_part, mode) as dest:
                if offset:
                    dest.seek(offset)
                sent_for_file = offset
                progress.update(base_sent + sent_for_file)
                while True:
                    chunk = source.read(1024 * 128)
                    if not chunk:
                        break
                    dest.write(chunk)
                    sent_for_file += len(chunk)
                    progress.update(base_sent + sent_for_file)
                    if on_file is not None:
                        on_file(local.name, sent_for_file, size)  # type: ignore[operator]
        # Verification is done by the caller when an SSH exec channel exists;
        # renaming here only happens after the caller has had a chance to
        # check, so this helper renames when size matches.
        try:
            remote_size = int(sftp.stat(remote_part).st_size)
        except Exception:
            remote_size = -1
        if remote_size == size:
            try:
                sftp.rename(remote_part, remote_final)
            except Exception:
                # Windows receivers may refuse rename over an existing file.
                try:
                    sftp.remove(remote_final)
                    sftp.rename(remote_part, remote_final)
                except Exception:
                    pass
            uploaded.append(remote_final)
        base_sent += size
        progress.update(base_sent)
    return uploaded
```

## exchange_ssh_keys_server

- Original path: `src/riptide/core/session.py`
- Reason: Unused or legacy in production. request_file / _handle_request are the old direct file request, replaced by request_download / respond_download with approval. send_ssh_download_request, send_info, and the SSH key exchange helpers are from the old SSH design and are never called by the UI.

```python
def exchange_ssh_keys_server(tls, home) -> None:
    """Join side: read creator's SSH public key, add it, reply with own key."""
    from .keys import append_authorized_key, ensure_keypair, public_key_text
    header = _read_header(tls)
    if header.get("type") != "ssh_key":
        raise ConnectionError("expected ssh_key exchange")
    append_authorized_key(str(header.get("key", "")), home=home)
    _private, _public = ensure_keypair(home)
    own = public_key_text(home) or ""
    _send_header(tls, {"type": "ssh_key_ok", "key": own})
```

## exchange_ssh_keys_client

- Original path: `src/riptide/core/session.py`
- Reason: Unused or legacy in production. request_file / _handle_request are the old direct file request, replaced by request_download / respond_download with approval. send_ssh_download_request, send_info, and the SSH key exchange helpers are from the old SSH design and are never called by the UI.

```python
def exchange_ssh_keys_client(tls, home) -> None:
    """Creator side: send own SSH public key, read joiner's key, add it."""
    from .keys import append_authorized_key, ensure_keypair, public_key_text
    _private, _public = ensure_keypair(home)
    own = public_key_text(home) or ""
    _send_header(tls, {"type": "ssh_key", "key": own})
    header = _read_header(tls)
    if header.get("type") != "ssh_key_ok":
        raise ConnectionError("expected ssh_key_ok exchange")
    append_authorized_key(str(header.get("key", "")), home=home)
```

## fingerprint_of_cert_file

- Original path: `src/riptide/core/identity.py`
- Reason: Unused anywhere, in production or tests.

```python
def fingerprint_of_cert_file(cert_path: Path) -> str:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    return cert_fingerprint(cert.public_bytes(serialization.Encoding.DER))
```

## block_banner

- Original path: `src/riptide/theme.py`
- Reason: Unused anywhere, in production or tests. The page banners are now the BANNER_HOST, BANNER_CLIENT, BANNER_CREATE and BANNER_JOIN constants.

```python
def block_banner(text: str) -> str:
    rows = [""] * 5
    for ch in text:
        glyph = _BLOCK_FONT.get(ch, ["     "] * 5)
        for i, row in enumerate(glyph):
            rows[i] += row + " "
    return "\n".join(row.rstrip() for row in rows)
```

## local_ip

- Original path: `src/riptide/core/nat.py`
- Reason: Unused in production after the Setup screen was removed. Only public_ip / stun_public_ip are used, by the Create Server page.

```python
def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except Exception:
        return "127.0.0.1"
```

## upnp_attempt

- Original path: `src/riptide/core/nat.py`
- Reason: Unused in production after the Setup screen was removed. Only public_ip / stun_public_ip are used, by the Create Server page.

```python
def upnp_attempt() -> tuple[bool, str]:
    """Best-effort UPnP. Returns (ok, message) without ever promising success."""
    try:
        import miniupnpc  # type: ignore
    except Exception:
        return False, "UPnP library not available. Use the manual step below."
    try:
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        upnp.discover()
        upnp.selectigd()
        return True, "UPnP gateway found. If it reports success, forwarding is set."
    except Exception as exc:
        return False, f"UPnP failed: {exc}"
```

## manual_instructions

- Original path: `src/riptide/core/nat.py`
- Reason: Unused in production after the Setup screen was removed. Only public_ip / stun_public_ip are used, by the Create Server page.

```python
def manual_instructions(local: str) -> str:
    return (
        "Manual forwarding: in your router, forward SSH to this computer "
        f"(local address {local}). If your router offers an SSH service preset, "
        "use that preset. If you are behind CGNAT, forwarding will not work: "
        "use reverse mode instead, where the CGNAT peer dials the public peer, "
        "and the file direction is independent of the connection direction."
    )
```

## Whole file: src/riptide/core/keys.py

- Reason: SSH key handling. Only used by the removed SSH key exchange in core/session.py. No production code uses it after that exchange is removed.

```python
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
```

## Whole file: src/riptide/core/ssh_client.py

- Reason: SSH client wrapper. No production code imports it. Transfers no longer use SSH.

```python
"""SSH client with staged status and strict fingerprint handling."""
from __future__ import annotations

import socket
from pathlib import Path

from .config import DEFAULT_SSH_PORT


def parse_peer(text: str) -> tuple[str, str]:
    """Parse user@host. Raises ValueError for anything else."""
    text = text.strip()
    if "@" not in text:
        raise ValueError("Enter a peer as user@host")
    user, host = text.rsplit("@", 1)
    user, host = user.strip(), host.strip()
    if not user or not host:
        raise ValueError("Enter a peer as user@host")
    return user, host


class FingerprintChangedError(Exception):
    pass


class UnknownHostError(Exception):
    pass


def _fingerprint_from_key(key) -> str:
    import base64
    import hashlib

    blob = key.asbytes()
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return f"SHA256:{digest}"


class RiptideSSH:
    """Thin Paramiko wrapper. The caller owns stage reporting."""

    def __init__(self, user: str, host: str, port: int = DEFAULT_SSH_PORT,
                 key_path: Path | None = None, known_fingerprint: str = ""):
        self.user = user
        self.host = host
        self.port = int(port)
        self.key_path = key_path
        self.known_fingerprint = known_fingerprint
        self.client = None
        self.fingerprint = ""

    def connect(self, on_stage=None, allow_new_host: bool = False, timeout: float = 30.0):
        import paramiko

        def stage(message: str):
            if on_stage:
                on_stage(message)

        stage("Resolving")
        socket.getaddrinfo(self.host, self.port, proto=socket.IPPROTO_TCP)
        stage("Connecting")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        stage("SSH handshake")
        client.connect(
            hostname=self.host, port=self.port, username=self.user,
            key_filename=str(self.key_path) if self.key_path else None,
            timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
            look_for_keys=False, allow_agent=False,
        )
        transport = client.get_transport()
        remote_key = transport.get_remote_server_key() if transport else None
        self.fingerprint = _fingerprint_from_key(remote_key) if remote_key else ""
        stage("Host key check")
        if self.known_fingerprint and self.fingerprint != self.known_fingerprint:
            client.close()
            raise FingerprintChangedError(
                "Host fingerprint changed. Aborting: this may mean a different "
                "computer is answering for this host. Check with the peer out of band."
            )
        if not self.known_fingerprint and not allow_new_host:
            client.close()
            raise UnknownHostError(f"Unknown host. Fingerprint is {self.fingerprint}. Confirm it, then retry.")
        stage("Authenticated")
        self.client = client
        return client

    def open_sftp(self):
        if self.client is None:
            raise RuntimeError("Not connected")
        return self.client.open_sftp()

    def exec_command(self, command: str):
        if self.client is None:
            raise RuntimeError("Not connected")
        return self.client.exec_command(command)

    def close(self) -> None:
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass
        self.client = None
```

## Whole file: src/riptide/core/setup_linux.py

- Reason: OpenSSH setup helpers. Only used by the removed Setup screen. No production code imports them.

```python
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
```

## Whole file: src/riptide/core/setup_windows.py

- Reason: OpenSSH setup helpers. Only used by the removed Setup screen. No production code imports them.

```python
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
```

## Whole file: src/riptide/screens/setup.py

- Reason: Setup screen. Not offered in the menu any more. Only exercised by a smoke test.

```python
from __future__ import annotations

import platform
import threading

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..core import nat as nat_mod
from ..core.focus import focus_first, handle_arrow_key
from ..core.setup_linux import run_setup as linux_setup, steps as linux_steps
from ..core.setup_windows import run_setup as windows_setup, steps as windows_steps
from ..theme import HEADER_LINES, TAGLINES

class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        system = platform.system()
        steps = windows_steps() if system == "Windows" else linux_steps()
        step_text = "\n".join(f"- {s['title']}: {s['detail']}" for s in steps)
        yield Vertical(
            Static("ENVIRONMENT & NETWORK SETUP", classes="screen-title"),
            Static(TAGLINES["setup"], classes="screen-desc"),
            Static(f"Detected system: {system}", classes="dim"),
            Static(step_text),
            Static("Output:", classes="accent"),
            Static("Not run yet.", id="output"),
            Button("Run set-up", id="run", classes="primary"),
            Button("Try automatic forwarding", id="upnp"),
            Static("[Esc] Back", classes="keymap-bar"),
            Static(nat_mod.REVERSE_MODE_TEXT, classes="dim"),
            Static(nat_mod.manual_instructions(nat_mod.local_ip()), classes="dim"),
        )

    def _set_output(self, text: str) -> None:
        try:
            self.query_one("#output", Static).update(text)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self._set_output("Running set-up in the background. This may ask for Administrator or sudo.")
            threading.Thread(target=self._run_worker, daemon=True).start()
        elif event.button.id == "upnp":
            ok, message = nat_mod.upnp_attempt()
            self._set_output(f"Automatic forwarding: {message}")
        elif event.button.id == "back":
            self.app.pop_screen()

    def _run_worker(self) -> None:
        try:
            if platform.system() == "Windows":
                lines = windows_setup()
            else:
                lines = linux_setup()
            self.app.call_from_thread(self._set_output, "\n".join(lines))
        except Exception as exc:
            self.app.call_from_thread(self._set_output, f"Set-up failed: {exc}")

    def on_mount(self) -> None:
        focus_first(self)

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
            return
        if handle_arrow_key(self, event.key):
            event.stop()
```

## request_file

- Original path: `src/riptide/core/session.py` (method of Session)
- Reason: Unused or legacy in production. See the Session helpers entry.

```python
def request_file(self, name: str) -> bool:
        # Legacy direct request: only a file in this side's cwd,
        # by basename. Kept for tests and old clients. The UI
        # no longer uses this for downloads; it uses
        # request_download() below, which asks for approval and
        # allows absolute paths.
        with self._send_lock:
            try:
                _send_header(self.sock, {"type": "request", "name": name})
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(f"request failed: {exc}")
                return False
        return True
```

## _handle_request

- Original path: `src/riptide/core/session.py` (method of Session)
- Reason: Unused or legacy in production. See the Session helpers entry.

```python
def _handle_request(self, name: str) -> None:
        safe = Path(name).name
        path = self.cwd / safe
        if not path.is_file():
            with self._send_lock:
                try:
                    _send_header(self.sock, {"type": "error", "message": f"no such file: {safe}"})
                except Exception:
                    pass
            return
        # send_file acquires the lock itself; the reader loop is not
        # holding it while reading, so this cannot deadlock.
        self.send_file(path)
```

## send_ssh_download_request

- Original path: `src/riptide/core/session.py` (method of Session)
- Reason: Unused or legacy in production. See the Session helpers entry.

```python
def send_ssh_download_request(self, name: str) -> bool:
        """Control message only: ask the other side to download this
        file from me via SSH/SFTP. No file bytes travel over TLS here."""
        with self._send_lock:
            try:
                _send_header(self.sock, {"type": "ssh_download_request", "name": name})
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(f"ssh download request failed: {exc}")
                return False
        return True
```

## send_info

- Original path: `src/riptide/core/session.py` (method of Session)
- Reason: Unused or legacy in production. See the Session helpers entry.

```python
def send_info(self, text: str) -> None:
        with self._send_lock:
            try:
                _send_header(self.sock, {"type": "info", "message": text})
            except Exception:
                pass
```

## label

- Original path: `src/riptide/core/config.py` (method of Peer)
- Reason: Peer.label() was unused in production.

```python
def label(self) -> str:
        return self.host or self.name
```

## Removed protocol messages

- `request` (core/session.py, _reader branch): only sent by the removed request_file, and only handled by the removed _handle_request. The UI uses `download_ask` / `download_denied` instead.
- `info` (core/session.py, _reader branch, with Session on_status): only sent by the removed send_info, and only delivered to the never-set on_status callback.
- `ssh_download_request` (core/session.py, _reader branch, with Session on_ssh_download_request): only sent by the removed send_ssh_download_request, and only delivered to the never-set on_ssh_download_request callback.

## Removed config and theme entries

- `LEGACY_SESSION_PORT = 49872` and the migration in load_config (core/config.py): the old default port. The app is not published yet and no saved config from that port needs migrating. The session port is now only `DEFAULT_SESSION_PORT = 50000`.
- `DEFAULT_SSH_PORT = 22` (core/config.py): only used by the removed SSH client. Transfers do not use SSH.
- `Peer.user`, `Peer.ssh_fingerprint`, `Peer.allow_always` (core/config.py): saved and loaded, but never read by production code. A peer is now only name, host, and TLS certificate fingerprint. The `user` argument of `Config.peer_for` was also removed for the same reason; it is now `peer_for(host)`.
- `Session` parameters `on_status` and `on_ssh_download_request`, `HostListener` parameter `on_status`, and the `exchange_ssh_keys` parameters of the listener and dial functions: only used by the removed SSH and info paths above.
- `REVERSE_MODE_TEXT` (core/nat.py): only used by the removed Setup screen.
- `_BLOCK_FONT` (src/riptide/theme.py): only used by the removed block_banner.
- `TAGLINES` entries `create`, `join`, `session`, and `setup` (src/riptide/theme.py): only the `home` tagline is shown in production, on the menu. The removed entries described pages that do not show a tagline, and `setup` described the removed Setup screen.
- The old Windows firewall rule name `Riptide File Transfer` (core/firewall.py, open_firewall_port): only tried when enabling a rule. The rule name is now only `Riptide`.
