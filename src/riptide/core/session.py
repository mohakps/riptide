"""Create / Join session protocol.

One TLS connection, started by the Join side (the client) dialling
the Create side (the host). After that one connection is live,
file direction is independent of connection direction:

- either side can Send (push a local file to the other side)
- either side can Download (request a file from the other side)

No pairing code, no pairing listener, no SSH. Authentication is
fingerprint-based, like SSH host keys:
- the client checks the host certificate fingerprint, and
  presses Allow on first connect, or aborts if it changed;
- since v1.1, the host also checks the client certificate
  fingerprint, through a signed hello challenge, and presses
  Allow on first connect, shows Known for a matching fingerprint,
  or warns on a changed fingerprint. An empty client fingerprint
  aborts, it never falls back to device-name-only approval.

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

import base64
import hashlib
import inspect
import ipaddress
import json
import os
import socket
import ssl
import struct
import threading
import time
from pathlib import Path

from .config import add_trusted_client, load_config
from .identity import (
    cert_der_from_pem,
    cert_fingerprint,
    ensure_identity,
    sign_nonce,
    verify_nonce_signature,
)


def parse_host_input(text: str) -> str:
    """Parse a Create-server address into a bare host.

    Accepts, all with no port typed by the user:
    - a hostname: metalvoid.ddns.net
    - an IPv4 address: 192.168.1.10
    - an IPv6 address: 2001:db8::1, or [2001:db8::1]
    - user@host: user@metalvoid.ddns.net,
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
    time out. socket.create_connection leaves a 30-second timeout
    on the client socket, so recv() timed out after 30 seconds of
    no file transfer and the reader loop ended the session.
    Blocking mode + keepalive removes that."""
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
                 on_file_received=None, on_ack=None, on_error=None,
                 on_progress=None,
                 on_download_ask=None, on_download_denied=None):
        self.sock = sock
        self.cwd = Path(cwd)
        self.device = device
        self.peer_device = peer_device
        self.peer_host = peer_host
        self.peer_fingerprint = ""
        # Host side only, set by HostListener: known, new, or changed.
        self.client_trust_status = ""
        self.client_old_fingerprint = ""
        self.on_file_received = on_file_received
        self.on_ack = on_ack
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






def _server_context(key_path: Path, cert_path: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    # CERT_NONE here, because a self-signed client cert would fail
    # Python's built-in verification even with CERT_OPTIONAL, as
    # verified in the v1.1 spike. Client authentication does not
    # rely on TLS client certificates at all. It relies on the
    # signed hello challenge in HostListener.wait_for_client:
    # the client presents its certificate in hello, signs a
    # host-chosen nonce with its private key, and the host
    # verifies that signature against the presented certificate.
    ctx.verify_mode = ssl.CERT_NONE
    ctx.check_hostname = False
    return ctx


def _client_context(key_path: Path, cert_path: Path) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _approve_arity(approve) -> int:
    """How many positional arguments an approve callback accepts.

    Old callbacks take (device, fingerprint). New callbacks take
    (device, fingerprint, status, old_fingerprint). Callbacks
    with *args accept any count, so treat them as new.
    """
    try:
        params = inspect.signature(approve).parameters.values()
    except Exception:
        return 2
    for param in params:
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            return 4
    count = sum(1 for p in params if p.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ))
    return count


def _call_approve(approve, device: str, fingerprint: str, status: str, old_fingerprint: str) -> bool:
    arity = _approve_arity(approve)
    if arity >= 4:
        return bool(approve(device, fingerprint, status, old_fingerprint))
    if arity == 3:
        return bool(approve(device, fingerprint, status))
    return bool(approve(device, fingerprint))


class HostListener:
    """Host side: listen for one client, approve it in the UI, return a Session.

    approve is called in the listener thread; the UI must answer
    it (in tests it can auto-approve). Old callbacks take
    (device, fingerprint). New callbacks take
    (device, fingerprint, status, old_fingerprint), where status
    is known, new, or changed. A changed fingerprint is only
    passed to a new callback. An old callback never sees a
    changed fingerprint, because that case aborts before approval,
    so a plain Allow can never silently replace a saved fingerprint.
    """

    def __init__(self, port: int, cwd: Path, device: str, home: Path | None = None,
                 approve=None):
        self.port = port
        self.cwd = Path(cwd)
        self.device = device
        self.home = home
        self.approve = approve
        self._server_sock: socket.socket | None = None

    def _abort(self, tls, message: str):
        try:
            _send_header(tls, {"type": "error", "message": message})
        except Exception:
            pass
        try:
            tls.close()
        except Exception:
            pass
        raise ConnectionError(message)

    def wait_for_client(self, timeout: float | None = None) -> Session:
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
        # Signed hello challenge. The client must present its
        # certificate in hello, then sign a host-chosen nonce.
        # A client that presents no certificate, or a bad
        # signature, aborts here, before any approval prompt.
        # This is a breaking change from v1.0 on purpose: a v1.0
        # client cannot be authenticated, so a v1.1 host must
        # not accept it on device name alone.
        try:
            hello = _read_header(tls)
        except Exception as exc:
            try:
                tls.close()
            except Exception:
                pass
            raise ConnectionError(f"hello failed: {exc}") from exc
        client_device = str(hello.get("device", "")) or "client"
        dialled_host = str(hello.get("host", "")) or _addr[0]
        cert_b64 = str(hello.get("cert", "") or "")
        if not cert_b64:
            self._abort(tls, "client fingerprint missing, cannot authenticate")
        try:
            cert_der = base64.b64decode(cert_b64, validate=True)
            if not cert_der:
                raise ValueError("empty certificate")
            peer_fp = cert_fingerprint(cert_der)
        except Exception:
            self._abort(tls, "client certificate invalid")
        nonce = os.urandom(32)
        try:
            _send_header(tls, {"type": "hello_challenge", "nonce": base64.b64encode(nonce).decode()})
            proof = _read_header(tls)
        except Exception as exc:
            try:
                tls.close()
            except Exception:
                pass
            raise ConnectionError(f"hello challenge failed: {exc}") from exc
        if proof.get("type") != "hello_proof":
            self._abort(tls, "client signature verification failed")
        try:
            signature = base64.b64decode(str(proof.get("signature", "") or ""), validate=True)
        except Exception:
            self._abort(tls, "client signature verification failed")
        if not verify_nonce_signature(cert_der, nonce, signature):
            self._abort(tls, "client signature verification failed")
        # Trust status, from trusted clients saved by this host.
        try:
            config = load_config(self.home)
        except Exception:
            config = None
        status = "new"
        old_fp = ""
        if config is not None:
            if config.trusted_client_for_fingerprint(peer_fp) is not None:
                status = "known"
            else:
                by_device = config.trusted_client_for_device(client_device)
                if by_device is not None:
                    status = "changed"
                    old_fp = by_device.fingerprint
        if status == "changed" and (self.approve is None or _approve_arity(self.approve) < 3):
            self._abort(tls, "fingerprint changed, session aborted")
        if self.approve is not None and not _call_approve(self.approve, client_device, peer_fp, status, old_fp):
            try:
                tls.close()
            except Exception:
                pass
            raise ConnectionError("host denied the session")
        # Save the trusted client only after approval. Known
        # needs no save. New and changed, where the user pressed
        # Accept after seeing the warning, are saved here, so a
        # later connection is known, or the replaced fingerprint
        # is the new trusted one.
        if config is not None and status in ("new", "changed"):
            try:
                from .config import Peer

                add_trusted_client(config, Peer(name=client_device, host="", fingerprint=peer_fp), home=self.home)
            except Exception as exc:
                try:
                    tls.close()
                except Exception:
                    pass
                raise ConnectionError(f"failed to save trusted client: {exc}") from exc
        try:
            _send_header(tls, {"type": "hello_ok", "device": self.device})
        except Exception as exc:
            raise ConnectionError(f"hello failed: {exc}") from exc
        session = Session(tls, self.cwd, device=self.device, peer_device=client_device, peer_host=dialled_host)
        session.peer_fingerprint = peer_fp
        session.client_trust_status = status
        session.client_old_fingerprint = old_fp
        return session

    def stop(self) -> None:
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except Exception:
                pass


def join_session(host: str, port: int, cwd: Path, device: str,
                   known_fingerprint: str = "", home: Path | None = None,
                   approve_fingerprint=None) -> Session:
    """Client side: dial the host, check its cert fingerprint, return a Session.

    approve_fingerprint(fingerprint) -> bool is called when the
    fingerprint is unknown or changed; in the UI it is the Allow button.

    After the host fingerprint check, the client proves its own
    identity to a v1.1 host with a signed hello challenge. A v1.0
    host replies hello_ok directly, without a challenge, and that
    path still works, because the client side check is unchanged
    and the old host simply never learns the client fingerprint.
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
            raise ConnectionError("client denied the fingerprint")
    try:
        try:
            cert_b64 = base64.b64encode(cert_der_from_pem(cert_path)).decode()
        except Exception:
            cert_b64 = ""
        _send_header(tls, {"type": "hello", "device": device, "host": host, "cert": cert_b64})
        reply = _read_header(tls)
        if reply.get("type") == "hello_ok":
            hello_ok = reply
        elif reply.get("type") == "error":
            raise ConnectionError(f"host rejected: {reply.get('message', 'session rejected')}")
        elif reply.get("type") != "hello_challenge":
            raise ConnectionError("host did not accept the session")
        else:
            try:
                nonce = base64.b64decode(str(reply.get("nonce", "") or ""), validate=True)
                signature = sign_nonce(key_path, nonce)
            except Exception as exc:
                raise ConnectionError(f"hello proof failed: {exc}") from exc
            _send_header(tls, {"type": "hello_proof", "signature": base64.b64encode(signature).decode()})
            hello_ok = _read_header(tls)
            if hello_ok.get("type") == "error":
                raise ConnectionError(f"host rejected: {hello_ok.get('message', 'session rejected')}")
            if hello_ok.get("type") != "hello_ok":
                raise ConnectionError("host did not accept the session")
    except Exception:
        try:
            tls.close()
        except Exception:
            pass
        raise
    session = Session(tls, cwd, device=device, peer_device=str(hello_ok.get("device", "")), peer_host=host)
    session.peer_fingerprint = server_fp
    return session
