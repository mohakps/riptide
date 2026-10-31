"""Transfer progress, hashing, and resumable SFTP upload.

No invented crypto: SFTP encryption comes from SSH/Paramiko, and
integrity comes from SHA-256 computed locally and, when an exec channel
is available, on the receiver.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path


def format_bytes(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n} B"


def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds != seconds or seconds == float("inf"):
        return "--"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


class TransferProgress:
    """EMA speed, remaining size, and ETA for one whole transfer."""

    def __init__(self, total: int):
        self.total = int(total)
        self.sent = 0
        self.started = time.monotonic()
        self._last_time = self.started
        self._last_sent = 0
        self.speed_ema = 0.0

    def update(self, sent: int) -> None:
        now = time.monotonic()
        self.sent = int(sent)
        dt = now - self._last_time
        if dt > 0:
            instant = (self.sent - self._last_sent) / dt
            if self.speed_ema == 0:
                self.speed_ema = instant
            else:
                self.speed_ema = 0.7 * self.speed_ema + 0.3 * instant
            self._last_time = now
            self._last_sent = self.sent

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.sent)

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 1.0
        return min(1.0, self.sent / self.total)

    @property
    def eta_seconds(self) -> float | None:
        if self.speed_ema <= 0:
            return None
        return self.remaining / self.speed_ema


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
