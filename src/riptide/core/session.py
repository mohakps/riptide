"""Create / Join session protocol, v2.

One TLS connection, started by the CGNAT side (the creator) dialling
the public side (the joiner). After that one connection is live,
file direction is independent of who created or joined:

- either side can Send (push a local file to the other side)
- either side can Download (request a file from the other side)

No pairing code, no pairing listener, no SSH. Authentication is
fingerprint-based, like SSH host keys:
- the creator checks the joiner's certificate fingerprint, and
  presses Allow on first connect, or aborts if it changed;
- the joiner sees the creator's device name and certificate
  fingerprint, and presses Allow to accept the session.

Framing: 4-byte big-endian length + JSON header, then, for a
file message, exactly size bytes. A file is written to a .part
file in the receiver's cwd and renamed only after its SHA-256
matches the header. A mismatch is reported, not renamed.

Only one file transfer runs at a time on a session (a send lock
makes header + bytes atomic). A send does not block waiting for
its ack: the ack arrives as a normal message and is delivered
through on_ack, so the reader loop can never deadlock waiting
for a message it is supposed to read itself.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import ssl
import struct
import threading
import time
from pathlib import Path

from .identity import cert_fingerprint, ensure_identity


def parse_host_input(text: str) -> str:
    """Parse a Create-server address into a bare host.

    Accepts, all with no port typed by the user:
    - a hostname: metalvoid.ddns.net
    - an IPv4 address: 192.168.1.10
    - an IPv6 address: 2001:db8::1, or [2001:db8::1]
    - user@host, for compatibility with the v3 input: user@metalvoid.ddns.net,
      user@192.168.1.10, user@[2001:db8::1]
    - host:port, if a port was typed anyway, is stripped for plain
      hostnames / IPv4; a bare IPv6 address is never split on ':'.
    Raises ValueError for an empty or unusable input.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Enter a host first")
    if "@" in text:
        text = text.rsplit("@", 1)[1].strip()
    if not text:
        raise ValueError("Enter a host first")
    if text.startswith("["):
        # [ipv6] or [ipv6]:port
        end = text.find("]")
        if end == -1:
            raise ValueError("Bad IPv6 address: missing ]")
        host = text[1:end].strip()
        if not host:
            raise ValueError("Enter a host first")
        return host
    # Bare IPv6: more than one ':' and a valid IPv6 parse.
    if text.count(":") > 1:
        try:
            ipaddress.IPv6Address(text)
            return text
        except Exception:
            raise ValueError("Bad IPv6 address")
    # Single ':' for hostname/IPv4 with a port: strip the port.
    if text.count(":") == 1:
        host, _port = text.split(":", 1)
        host = host.strip()
        if not host:
            raise ValueError("Enter a host first")
        return host
    return text


def _set_keepalive(sock) -> None:
    """Blocking socket + TCP keepalive, so an idle session does not
    time out. This is the v2 idle-cutoff fix: socket.create_connection
    left a 30-second timeout on the creator socket, so recv() timed
    out after 30 seconds of no file transfer and the reader loop
    ended the session. Blocking mode + keepalive removes that."""
    try:
        sock.settimeout(None)
    except Exception:
        pass
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except Exception:
        pass
    # Linux TCP keepalive tunables; harmless if unavailable (Windows).
    for opt, value in (("TCP_KEEPIDLE", 10), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 3)):
        try:
            sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, opt), value)
        except Exception:
            pass


def _recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("session closed")
        data += chunk
    return data


def _send_header(sock, header: dict) -> None:
    raw = json.dumps(header).encode()
    sock.sendall(struct.pack(">I", len(raw)) + raw)


class Session:
    def __init__(self, sock, cwd: Path, device: str = "", peer_device: str = "",
                 peer_host: str = "",
                 on_file_received=None, on_ack=None, on_status=None, on_error=None,
                 on_ssh_download_request=None, on_progress=None,
                 on_download_ask=None, on_download_denied=None):
        self.sock = sock
        self.cwd = Path(cwd)
        self.device = device
        self.peer_device = peer_device
        self.peer_host = peer_host
        self.peer_fingerprint = ""
        self.on_ssh_download_request = on_ssh_download_request
        self.on_file_received = on_file_received
        self.on_ack = on_ack
        self.on_status = on_status
        self.on_error = on_error
        self.on_progress = on_progress
        self.on_download_ask = on_download_ask
        self.on_download_denied = on_download_denied
        self._send_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None

    # -- sending -------------------------------------------------
    def send_file(self, path: Path, on_progress=None) -> bool:
        path = Path(path)
        if not path.is_file():
            return False
        size = path.stat().st_size
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 256), b""):
                digest.update(chunk)
        header = {"type": "file", "name": path.name, "size": size, "sha256": digest.hexdigest()}
        with self._send_lock:
            try:
                _send_header(self.sock, header)
                sent = 0
                last_report = 0.0
                with open(path, "rb") as handle:
                    while True:
                        chunk = handle.read(1024 * 128)
                        if not chunk:
                            break
                        self.sock.sendall(chunk)
                        sent += len(chunk)
                        # Sender progress was the bug: it reported every
                        # 128KB chunk, while the receiver reports at most
                        # every 0.1s. The UI computes speed from the time
                        # between UI callbacks, and call_from_thread lets
                        # the sender run ahead and queue a burst of
                        # callbacks that the UI then processes almost
                        # instantly, so bytes / tiny time = 4-5x speed.
                        # Throttle the sender exactly like the receiver:
                        # at most every 0.1s, plus always on the final
                        # chunk, so the UI time between reports is real
                        # network time, not queue-processing time.
                        now = time.monotonic()
                        if on_progress is not None and (now - last_report >= 0.1 or sent >= size):
                            last_report = now
                            on_progress(path.name, sent, size)
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(f"send failed: {exc}")
                return False
        return True

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

    def request_download(self, name: str, request_id: str = "") -> bool:
        """Ask the peer for approval to download a file.

        ``name`` may be absolute (a path on the peer) or relative
        to the peer's cwd. Nothing is sent until the peer allows
        it; the file then arrives as a normal file message."""
        with self._send_lock:
            try:
                _send_header(self.sock, {"type": "download_ask", "name": name, "id": request_id})
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(f"download request failed: {exc}")
                return False
        return True

    def respond_download(self, name: str, request_id: str, allow: bool, on_progress=None) -> bool:
        """Peer side: answer a download_ask. On allow, send the
        file (absolute path, or relative to this side's cwd).
        On deny, tell the requester, and send nothing.
        on_progress, when given, is passed to send_file so the
        approver side gets progress like a normal send. Without
        it, the approver saw no progress bar at all."""
        if not allow:
            with self._send_lock:
                try:
                    _send_header(self.sock, {"type": "download_denied", "name": name, "id": request_id})
                except Exception:
                    pass
            return True
        path = Path(name).expanduser()
        if not path.is_absolute():
            path = self.cwd / path
        # send_file only sends files, and its header carries only
        # the basename, so the receiver saves it in its own cwd.
        return self.send_file(path, on_progress=on_progress)

    def send_ack(self, name: str, ok: bool, reason: str = "") -> None:
        with self._send_lock:
            try:
                _send_header(self.sock, {"type": "ack", "name": name, "ok": ok, "reason": reason})
            except Exception:
                pass

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

    def send_info(self, text: str) -> None:
        with self._send_lock:
            try:
                _send_header(self.sock, {"type": "info", "message": text})
            except Exception:
                pass

    # -- receiving ------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        _set_keepalive(self.sock)
        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat(self) -> None:
        """Ping every 10 seconds while idle, so NAT/firewall idle
        timeouts do not close a session with no file transferring.
        Ping/pong are control messages, not file bytes."""
        while self._running:
            time.sleep(10)
            if not self._running:
                break
            try:
                with self._send_lock:
                    _send_header(self.sock, {"type": "ping"})
            except Exception:
                break

    def _reader(self) -> None:
        try:
            while self._running:
                raw_len = _recv_exact(self.sock, 4)
                (length,) = struct.unpack(">I", raw_len)
                if length <= 0 or length > 1024 * 1024:
                    raise ConnectionError("bad header length")
                header = json.loads(_recv_exact(self.sock, length).decode())
                kind = header.get("type")
                if kind == "file":
                    self._receive_file(header)
                elif kind == "request":
                    self._handle_request(header.get("name", ""))
                elif kind == "download_ask":
                    if self.on_download_ask is not None:
                        self.on_download_ask(str(header.get("name", "")), str(header.get("id", "")))
                elif kind == "download_denied":
                    if self.on_download_denied is not None:
                        self.on_download_denied(str(header.get("name", "")), str(header.get("id", "")))
                elif kind == "ack":
                    if self.on_ack is not None:
                        self.on_ack(header.get("name", ""), bool(header.get("ok")), header.get("reason", ""))
                elif kind == "ping":
                    # Reply, so both directions see traffic. No UI update.
                    try:
                        with self._send_lock:
                            _send_header(self.sock, {"type": "pong"})
                    except Exception:
                        pass
                elif kind == "pong":
                    pass
                elif kind == "ssh_download_request":
                    if self.on_ssh_download_request is not None:
                        self.on_ssh_download_request(str(header.get("name", "")))
                elif kind == "info":
                    if self.on_status is not None:
                        self.on_status(str(header.get("message", "")))
                elif kind == "bye":
                    break
                elif kind == "error":
                    if self.on_error is not None:
                        self.on_error(str(header.get("message", "")))
        except Exception as exc:
            if self._running and self.on_error is not None:
                self.on_error(f"session ended: {exc}")
        finally:
            self._running = False

    def _receive_file(self, header: dict) -> None:
        name = Path(str(header.get("name", ""))).name
        size = int(header.get("size", 0))
        expected = str(header.get("sha256", ""))
        part = self.cwd / f"{name}.part"
        final = self.cwd / name
        digest = hashlib.sha256()
        remaining = size
        received = 0
        last_report = 0.0
        try:
            with open(part, "wb") as dest:
                while remaining > 0:
                    chunk = self.sock.recv(min(1024 * 128, remaining))
                    if not chunk:
                        raise ConnectionError("session closed during file")
                    dest.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
                    received += len(chunk)
                    # Receiver progress: report at most every 0.1s, plus
                    # always on the final chunk, so the UI stays live
                    # without flooding it on every 128KB chunk.
                    now = time.monotonic()
                    if self.on_progress is not None and (now - last_report >= 0.1 or remaining == 0):
                        last_report = now
                        try:
                            self.on_progress(name, received, size)
                        except Exception:
                            pass
        except Exception as exc:
            if self.on_error is not None:
                self.on_error(f"receive failed: {exc}")
            if self.on_file_received is not None:
                self.on_file_received(name, False, "incomplete")
            return
        ok = digest.hexdigest() == expected
        if ok:
            try:
                part.replace(final)
            except Exception:
                try:
                    final.unlink(missing_ok=True)
                    part.replace(final)
                except Exception as exc:
                    ok = False
                    if self.on_error is not None:
                        self.on_error(f"rename failed: {exc}")
        if self.on_file_received is not None:
            self.on_file_received(name, ok, "" if ok else "SHA-256 mismatch, kept as .part")
        # Ack is a normal message, not a file, so it cannot interleave
        # with file bytes: file bytes are already fully read here.
        self.send_ack(name, ok, "" if ok else "SHA-256 mismatch")

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

    def close(self) -> None:
        self._running = False
        try:
            with self._send_lock:
                _send_header(self.sock, {"type": "bye"})
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


def _read_header(sock) -> dict:
    raw_len = _recv_exact(sock, 4)
    (length,) = struct.unpack(">I", raw_len)
    if length <= 0 or length > 1024 * 1024:
        raise ConnectionError("bad header length")
    return json.loads(_recv_exact(sock, length).decode())


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


def _server_context(key_path: Path, cert_path: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    # CERT_NONE here, because a self-signed client cert would fail
    # Python's built-in verification even with CERT_OPTIONAL.
    # The strong check in v2 is the creator checking the joiner's
    # server certificate fingerprint; the joiner approves the
    # creator by device name in the UI before the session opens.
    ctx.verify_mode = ssl.CERT_NONE
    ctx.check_hostname = False
    return ctx


def _client_context(key_path: Path, cert_path: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class JoinListener:
    """Join side: listen for one creator, approve it in the UI, return a Session.

    approve(device, fingerprint) -> bool is called in the listener
    thread; the UI must answer it (in tests it can auto-approve).
    """

    def __init__(self, port: int, cwd: Path, device: str, home: Path | None = None,
                 approve=None, on_status=None):
        self.port = port
        self.cwd = Path(cwd)
        self.device = device
        self.home = home
        self.approve = approve
        self.on_status = on_status
        self._server_sock: socket.socket | None = None

    def wait_for_creator(self, timeout: float | None = None, exchange_ssh_keys: bool = False) -> Session:
        key_path, cert_path = ensure_identity(self.home)
        ctx = _server_context(key_path, cert_path)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.port))
        server.listen(1)
        if timeout is not None:
            server.settimeout(timeout)
        self._server_sock = server
        try:
            raw, _addr = server.accept()
        finally:
            try:
                server.close()
            except Exception:
                pass
            self._server_sock = None
        try:
            tls = ctx.wrap_socket(raw, server_side=True)
        except Exception as exc:
            raise ConnectionError(f"TLS failed: {exc}") from exc
        _set_keepalive(tls)
        # Creator identity: its client cert, if presented.
        peer_der = tls.getpeercert(binary_form=True)
        peer_fp = cert_fingerprint(peer_der) if peer_der else ""
        # Hello carries the creator's device name.
        raw_len = _recv_exact(tls, 4)
        (length,) = struct.unpack(">I", raw_len)
        hello = json.loads(_recv_exact(tls, length).decode())
        creator_device = str(hello.get("device", "")) or "creator"
        dialler_host = str(hello.get("host", "")) or _addr[0]
        if self.approve is not None and not self.approve(creator_device, peer_fp):
            try:
                tls.close()
            except Exception:
                pass
            raise ConnectionError("joiner denied the session")
        try:
            _send_header(tls, {"type": "hello_ok", "device": self.device})
        except Exception as exc:
            raise ConnectionError(f"hello failed: {exc}") from exc
        if exchange_ssh_keys:
            exchange_ssh_keys_server(tls, self.home)
        session = Session(tls, self.cwd, device=self.device, peer_device=creator_device, peer_host=dialler_host)
        session.peer_fingerprint = peer_fp
        return session

    def stop(self) -> None:
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except Exception:
                pass


def create_session(host: str, port: int, cwd: Path, device: str,
                   known_fingerprint: str = "", home: Path | None = None,
                   approve_fingerprint=None, exchange_ssh_keys: bool = False) -> Session:
    """Creator side: dial the joiner, check its cert fingerprint, return a Session.

    approve_fingerprint(fingerprint) -> bool is called when the
    fingerprint is unknown or changed; in the UI it is the Allow button.
    """
    key_path, cert_path = ensure_identity(home)
    ctx = _client_context(key_path, cert_path)
    raw = socket.create_connection((host, port), timeout=30)
    try:
        tls = ctx.wrap_socket(raw, server_hostname=host)
    except Exception as exc:
        try:
            raw.close()
        except Exception:
            pass
        raise ConnectionError(f"TLS failed: {exc}") from exc
    # Critical: create_connection left a 30s timeout on this socket.
    # Without clearing it, an idle session timed out after 30s.
    _set_keepalive(tls)
    server_der = tls.getpeercert(binary_form=True)
    server_fp = cert_fingerprint(server_der) if server_der else ""
    if known_fingerprint and server_fp != known_fingerprint:
        try:
            tls.close()
        except Exception:
            pass
        raise ConnectionError("fingerprint changed, session aborted")
    if not known_fingerprint and approve_fingerprint is not None:
        if not approve_fingerprint(server_fp):
            try:
                tls.close()
            except Exception:
                pass
            raise ConnectionError("creator denied the fingerprint")
    try:
        _send_header(tls, {"type": "hello", "device": device, "host": host})
        hello_ok = _read_header(tls)
        if hello_ok.get("type") != "hello_ok":
            raise ConnectionError("joiner did not accept the session")
        if exchange_ssh_keys:
            exchange_ssh_keys_client(tls, home)
    except Exception:
        try:
            tls.close()
        except Exception:
            pass
        raise
    session = Session(tls, cwd, device=device, peer_device=str(hello_ok.get("device", "")), peer_host=host)
    session.peer_fingerprint = server_fp
    return session
