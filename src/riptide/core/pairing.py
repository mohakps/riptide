"""Pairing: a short code, not a typed public key.

The receiver shows a 6-digit code valid for five minutes. The sender
enters only that code. The sender's public key travels over a pairing
listener authenticated by the code, and the receiver adds it to
authorized_keys. The listener port is internal and is never shown in UI.
"""
from __future__ import annotations

import json
import secrets
import socket
import socketserver
import threading
import time
from dataclasses import dataclass
from pathlib import Path

CODE_TTL_SECONDS = 300


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


@dataclass
class PairingCode:
    code: str
    created_at: float = 0.0
    used: bool = False

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def is_valid(self, candidate: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if self.used:
            return False
        if now - self.created_at > CODE_TTL_SECONDS:
            return False
        return secrets.compare_digest(candidate.strip(), self.code)


def append_authorized_key(authorized_keys: Path, public_key: str, device: str) -> bool:
    """Append a key if not already present. Returns True if it was added."""
    authorized_keys.parent.mkdir(parents=True, exist_ok=True)
    key = public_key.strip()
    if not key:
        return False
    existing = authorized_keys.read_text(encoding="utf-8") if authorized_keys.exists() else ""
    if key in existing:
        return False
    comment = f" riptide:{device}" if device else ""
    with open(authorized_keys, "a", encoding="utf-8") as handle:
        handle.write(key + comment + "\n")
    try:
        authorized_keys.chmod(0o600)
    except Exception:
        pass
    return True


def remove_authorized_key(authorized_keys: Path, public_key: str) -> bool:
    if not authorized_keys.exists():
        return False
    key = public_key.strip()
    lines = authorized_keys.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if key not in line]
    if len(kept) == len(lines):
        return False
    authorized_keys.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return True


class _PairingHandler(socketserver.BaseRequestHandler):
    def handle(self):  # type: ignore[override]
        server = self.server  # type: ignore[attr-defined]
        try:
            raw = self.request.recv(65536).decode("utf-8").strip()
            data = json.loads(raw)
            code = str(data.get("code", ""))
            device = str(data.get("device", ""))
            public_key = str(data.get("public_key", ""))
            if not server.code.is_valid(code):  # type: ignore[attr-defined]
                self.request.sendall(json.dumps({"ok": False, "error": "invalid or expired code"}).encode())
                return
            if not public_key:
                self.request.sendall(json.dumps({"ok": False, "error": "missing public key"}).encode())
                return
            server.code.used = True  # type: ignore[attr-defined]
            added = append_authorized_key(server.authorized_keys, public_key, device)  # type: ignore[attr-defined]
            if server.on_success:  # type: ignore[attr-defined]
                try:
                    server.on_success(device, public_key)  # type: ignore[attr-defined]
                except Exception:
                    pass
            self.request.sendall(json.dumps({"ok": True, "added": added}).encode())
        except Exception as exc:
            try:
                self.request.sendall(json.dumps({"ok": False, "error": str(exc)}).encode())
            except Exception:
                pass


class PairingServer:
    def __init__(self, code: PairingCode, authorized_keys: Path, host: str = "0.0.0.0",
                 port: int = 0, on_success=None):
        self.code = code
        self.authorized_keys = authorized_keys
        self._server = socketserver.ThreadingTCPServer((host, port), _PairingHandler, bind_and_activate=False)
        self._server.allow_reuse_address = True
        self._server.daemon_threads = True
        self._server.code = code  # type: ignore[attr-defined]
        self._server.authorized_keys = authorized_keys  # type: ignore[attr-defined]
        self._server.on_success = on_success  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._server.server_bind()
        self._server.server_activate()
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass


def send_pairing(host: str, port: int, code: str, device: str, public_key: str,
                 timeout: float = 15.0) -> dict:
    payload = json.dumps({"code": code, "device": device, "public_key": public_key}).encode()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(payload)
        raw = sock.recv(65536).decode("utf-8")
    return json.loads(raw) if raw else {"ok": False, "error": "empty response"}
