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
