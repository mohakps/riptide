"""Section 5: resume interrupted transfers.

Unit tests for the sidecar, the pending list, and the cleanup
rules, socketpair tests for the resume negotiation, a TLS
integration test for an interrupted transfer that resumes on
rejoin, and a pilot test for the resume card.
"""
from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import Static

from riptide.core.resume import (
    add_pending,
    cleanup_parts,
    delete_part_and_sidecar,
    load_pending,
    part_sidecar_path,
    pending_for_peer,
    read_part_sidecar,
    remove_pending,
    save_pending,
    write_part_sidecar,
)
from riptide.core.session import HostListener, Session, join_session
from riptide.screens.session_screen import SessionScreen
from riptide.theme import CSS


def _wait_for_received(received: dict, name: str, timeout: float = 5.0) -> bool:
    """Wait for a receiver's on_file_received report.

    send_file returns as soon as the bytes are sent, before the
    receiver has renamed the file and reported, so an immediate
    assert is a race, especially under load.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and name not in received:
        time.sleep(0.05)
    return name in received


# -- sidecar and pending list ---------------------------------------


def test_sidecar_round_trip_and_corrupt(tmp_path: Path):
    part = tmp_path / "report.pdf.part"
    part.write_bytes(b"abc")
    write_part_sidecar(part, "fp-1", "report.pdf", 100, "deadbeef")
    sidecar = read_part_sidecar(part)
    assert sidecar is not None
    assert sidecar["peer_fingerprint"] == "fp-1"
    assert sidecar["name"] == "report.pdf"
    assert sidecar["size"] == 100
    assert sidecar["sha256"] == "deadbeef"
    assert sidecar["updated_at"] > 0
    assert part_sidecar_path(part).exists()
    delete_part_and_sidecar(part)
    assert not part.exists()
    assert not part_sidecar_path(part).exists()
    # Corrupt sidecar reads as None.
    part.write_bytes(b"abc")
    part_sidecar_path(part).write_text("{not json")
    assert read_part_sidecar(part) is None
    # Missing sidecar reads as None.
    part_sidecar_path(part).unlink()
    assert read_part_sidecar(part) is None


def test_pending_add_remove_and_age_drop(tmp_path: Path):
    home = tmp_path
    assert load_pending(home) == []
    add_pending(home, {"peer_fingerprint": "fp-1", "name": "a.bin", "size": 10, "sha256": "aa", "path": "/tmp/a.bin"})
    add_pending(home, {"peer_fingerprint": "fp-2", "name": "b.bin", "size": 20, "sha256": "bb", "path": "/tmp/b.bin"})
    assert len(load_pending(home)) == 2
    assert len(pending_for_peer(home, "fp-1")) == 1
    # Re-adding the same transfer replaces it, it does not duplicate.
    add_pending(home, {"peer_fingerprint": "fp-1", "name": "a.bin", "size": 10, "sha256": "aa", "path": "/tmp/a.bin"})
    assert len(load_pending(home)) == 2
    remove_pending(home, "fp-1", "a.bin", 10, "aa")
    assert len(load_pending(home)) == 1
    assert pending_for_peer(home, "fp-1") == []
    # An entry older than 1 day is dropped on load.
    old = {
        "peer_fingerprint": "fp-2", "name": "b.bin", "size": 20, "sha256": "bb",
        "path": "/tmp/b.bin", "updated_at": time.time() - 25 * 3600,
    }
    save_pending(home, [old])
    assert load_pending(home) == []
    # A corrupt file is no pending transfers, not an error.
    (home / ".riptide" / "pending.json").write_text("{broken")
    assert load_pending(home) == []


def test_cleanup_parts_wrong_peer_stale_and_orphan(tmp_path: Path):
    d = tmp_path / "cwd"
    d.mkdir()
    # Wrong peer: sidecar belongs to another fingerprint.
    wrong = d / "old.bin.part"
    wrong.write_bytes(b"1234")
    write_part_sidecar(wrong, "fp-other", "old.bin", 100, "aa")
    # Stale: sidecar updated more than 1 day ago.
    stale = d / "stale.bin.part"
    stale.write_bytes(b"1234")
    write_part_sidecar(stale, "fp-1", "stale.bin", 100, "bb")
    sidecar = json.loads(part_sidecar_path(stale).read_text())
    sidecar["updated_at"] = time.time() - 25 * 3600
    part_sidecar_path(stale).write_text(json.dumps(sidecar))
    # Same peer, fresh: kept.
    keep = d / "keep.bin.part"
    keep.write_bytes(b"1234")
    write_part_sidecar(keep, "fp-1", "keep.bin", 100, "cc")
    # Orphan sidecar, no .part: deleted.
    orphan = d / "gone.bin.part.json"
    orphan.write_text("{}")
    deleted = cleanup_parts(d, "fp-1")
    assert "old.bin.part" in deleted
    assert "stale.bin.part" in deleted
    assert "gone.bin.part.json" in deleted
    assert not wrong.exists() and not stale.exists()
    assert keep.exists() and part_sidecar_path(keep).exists()
    # At app launch, with no peer, only stale .parts are deleted.
    # A fresh .part with no sidecar is kept.
    nosidecar = d / "fresh.bin.part"
    nosidecar.write_bytes(b"12")
    deleted = cleanup_parts(d, None)
    assert "fresh.bin.part" not in deleted
    assert nosidecar.exists()
    # The same fresh .part with no sidecar is deleted at session
    # start, when a peer is known, because it cannot be attributed.
    deleted = cleanup_parts(d, "fp-1")
    assert "fresh.bin.part" in deleted
    assert not nosidecar.exists()


# -- socketpair protocol tests --------------------------------------


def _pair(tmp_path: Path, sender_home: str = "shome", receiver_home: str = "rhome"):
    """Two Sessions over a socketpair, both advertising resume."""
    sender_dir = tmp_path / "sender"
    receiver_dir = tmp_path / "receiver"
    sender_dir.mkdir(exist_ok=True)
    receiver_dir.mkdir(exist_ok=True)
    a, b = socket.socketpair()
    sender = Session(a, sender_dir, device="sender", peer_device="receiver", home=tmp_path / sender_home)
    receiver = Session(b, receiver_dir, device="receiver", peer_device="sender", home=tmp_path / receiver_home)
    # Each side's peer fingerprint is the other side's identity.
    sender.peer_fingerprint = "receiver-fp"
    receiver.peer_fingerprint = "sender-fp"
    sender.peer_supports_resume = True
    receiver.peer_supports_resume = True
    return sender, receiver, sender_dir, receiver_dir


def _seed_part(receiver_dir: Path, name: str, data: bytes, size: int, sha: str, peer_fp: str = "sender-fp"):
    part = receiver_dir / f"{name}.part"
    part.write_bytes(data)
    write_part_sidecar(part, peer_fp, name, size, sha)
    return part


def test_resume_from_partial_part(tmp_path: Path):
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = bytes(range(256)) * 40  # 10240 bytes
    src = sender_dir / "big.bin"
    src.write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    # The receiver already has the first 4096 bytes.
    first = content[:4096]
    _seed_part(receiver_dir, "big.bin", first, len(content), sha)
    received_progress = []
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok, "reason": r})
    receiver.on_progress = lambda n, got, total: received_progress.append(got)
    receiver.on_resume_ask = lambda n, off, total: "allow"
    receiver.start()
    sender.start()
    assert sender.send_file(src)
    # The receiver reports progress from the offset, not from 0:
    # the first report is already past the 4096 bytes it held.
    assert received_progress and received_progress[0] >= 4096
    assert _wait_for_received(received, "big.bin")
    assert received.get("big.bin") is True
    assert (receiver_dir / "big.bin").read_bytes() == content
    # The .part and its sidecar are gone after the rename.
    assert not (receiver_dir / "big.bin.part").exists()
    assert not part_sidecar_path(receiver_dir / "big.bin.part").exists()
    sender.close()
    receiver.close()


def test_resume_deny_deletes_part(tmp_path: Path):
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = b"x" * 4096
    src = sender_dir / "big.bin"
    src.write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    _seed_part(receiver_dir, "big.bin", content[:1024], len(content), sha)
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok, "reason": r})
    receiver.on_resume_ask = lambda n, off, total: "deny"
    receiver.start()
    sender.start()
    assert sender.send_file(src) is False
    assert not (receiver_dir / "big.bin.part").exists()
    assert not part_sidecar_path(receiver_dir / "big.bin.part").exists()
    assert _wait_for_received(received, "big.bin")
    assert received.get("big.bin") is False
    assert "deleted" in received.get("reason", "")
    sender.close()
    receiver.close()


def test_wrong_peer_part_is_deleted_and_transfer_is_full(tmp_path: Path):
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = b"y" * 2048
    src = sender_dir / "f.bin"
    src.write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    # The .part belongs to a different peer.
    _seed_part(receiver_dir, "f.bin", b"junk", len(content), sha, peer_fp="someone-else")
    asked = []
    receiver.on_resume_ask = lambda n, off, total: asked.append((n, off, total)) or "allow"
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok})
    receiver.start()
    sender.start()
    assert sender.send_file(src)
    # No resume card was shown: the wrong-peer's .part was deleted
    # and the transfer ran in full.
    assert asked == []
    assert _wait_for_received(received, "f.bin")
    assert received.get("f.bin") is True
    assert (receiver_dir / "f.bin").read_bytes() == content
    sender.close()
    receiver.close()


def test_old_peer_gets_full_transfer_without_wait(tmp_path: Path):
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    sender.peer_supports_resume = False
    receiver.peer_supports_resume = False
    content = b"z" * 2048
    src = sender_dir / "f.bin"
    src.write_bytes(content)
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok})
    receiver.start()
    sender.start()
    # No resume response is ever sent, so the sender must not wait.
    assert sender.send_file(src)
    assert _wait_for_received(received, "f.bin")
    assert received.get("f.bin") is True
    assert (receiver_dir / "f.bin").read_bytes() == content
    sender.close()
    receiver.close()


def test_sender_records_pending_on_failure(tmp_path: Path):
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = bytes(range(256)) * 4096  # 1 MiB
    src = sender_dir / "big.bin"
    src.write_bytes(content)
    receiver.start()
    sender.start()
    # Interrupt on the first progress report, which fires on the
    # first chunk: shut the receiver's socket down, so the
    # sender's next sendall fails and the transfer is recorded.
    stopped = threading.Event()

    def on_prog(name, sent, total):
        if not stopped.is_set():
            stopped.set()
            try:
                receiver.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass

    result = {}

    def do_send():
        result["ok"] = sender.send_file(src, on_progress=on_prog)

    t = threading.Thread(target=do_send, daemon=True)
    t.start()
    t.join(timeout=20)
    assert result.get("ok") is False
    pending = pending_for_peer(tmp_path / "shome", "receiver-fp")
    assert len(pending) == 1
    assert pending[0]["name"] == "big.bin"
    assert pending[0]["size"] == len(content)
    sender.close()
    receiver.close()


def test_complete_part_is_verified_without_transfer(tmp_path: Path):
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = b"w" * 1024
    src = sender_dir / "f.bin"
    src.write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    # The receiver already holds the whole file as a .part.
    _seed_part(receiver_dir, "f.bin", content, len(content), sha)
    asked = []
    receiver.on_resume_ask = lambda n, off, total: asked.append((n, off, total)) or "allow"
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok})
    receiver.start()
    sender.start()
    assert sender.send_file(src)
    # No resume card: the file was already complete, so it was
    # verified and renamed without a transfer or a decision.
    assert asked == []
    assert _wait_for_received(received, "f.bin")
    assert received.get("f.bin") is True
    assert (receiver_dir / "f.bin").read_bytes() == content
    sender.close()
    receiver.close()


# -- TLS integration: interrupt, rejoin, resume ---------------------


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_tls_interrupt_then_resume_on_rejoin(tmp_path: Path):
    host_dir = tmp_path / "host"
    client_dir = tmp_path / "client"
    host_dir.mkdir()
    client_dir.mkdir()
    content = bytes(range(256)) * 20480  # 5 MiB
    src = client_dir / "big.bin"
    src.write_bytes(content)
    port = _free_port()

    host_session = {}
    host_received = {}
    host_progress = []

    def run_host():
        listener = HostListener(port, host_dir, device="host", home=tmp_path / "jhome", approve=lambda d, fp: True)
        s = listener.wait_for_client()
        s.on_file_received = lambda n, ok, r: host_received.update({n: ok, "reason": r})
        s.on_progress = lambda n, got, total: host_progress.append(got)
        s.on_resume_ask = lambda n, off, total: "allow"
        s.start()
        host_session["s"] = s

    t = threading.Thread(target=run_host, daemon=True)
    t.start()
    time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "chome", approve_fingerprint=lambda fp: True)
    client.start()
    time.sleep(0.3)
    assert client.peer_supports_resume is True
    assert host_session["s"].peer_supports_resume is True
    # Interrupt on the first progress report, which fires on the
    # first chunk: shut the client's socket down. The send then
    # fails, the host keeps the .part, and the client records a
    # pending entry.
    stopped = threading.Event()

    def on_prog(name, sent, total):
        if not stopped.is_set():
            stopped.set()
            try:
                client.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass

    send_result = {}

    def do_send():
        send_result["ok"] = client.send_file(src, on_progress=on_prog)

    st = threading.Thread(target=do_send, daemon=True)
    st.start()
    st.join(timeout=20)
    assert send_result.get("ok") is False
    # The host drains its receive buffer before hitting the
    # closed socket, so wait for the incomplete report before
    # asserting the sidecar is written.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "big.bin" not in host_received:
        time.sleep(0.05)
    assert host_received.get("big.bin") is False
    # The host kept the .part and its sidecar.
    part = host_dir / "big.bin.part"
    assert part.exists() and part.stat().st_size > 0
    assert part_sidecar_path(part).exists()
    interrupted = part.stat().st_size
    # The sender recorded the pending transfer on disk.
    assert len(pending_for_peer(tmp_path / "chome", client.peer_fingerprint)) == 1
    client.close()
    host_session["s"].close()
    time.sleep(0.3)
    # Rejoin with the same peer, and re-send. The receiver resumes.
    host_received.clear()
    host_progress.clear()
    t2 = threading.Thread(target=run_host, daemon=True)
    t2.start()
    time.sleep(0.5)
    client2 = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "chome", approve_fingerprint=lambda fp: True)
    client2.start()
    time.sleep(0.3)
    assert client2.send_file(src)
    assert _wait_for_received(host_received, "big.bin", timeout=10)
    assert host_received.get("big.bin") is True
    assert (host_dir / "big.bin").read_bytes() == content
    # The resumed transfer reported progress from the offset.
    assert host_progress and host_progress[0] >= interrupted
    # The pending entry is gone after the completed send.
    assert pending_for_peer(tmp_path / "chome", client2.peer_fingerprint) == []
    client2.close()
    host_session["s"].close()


# -- resume card pilot ----------------------------------------------


class _ResumeApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, role="host"))


@pytest.mark.asyncio
async def test_resume_card_allow_and_deny(tmp_path: Path):
    sender, receiver, _, _ = _pair(tmp_path)
    app = _ResumeApp(receiver)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        screen = app.screen
        result = {}

        def asker():
            result["value"] = screen._ask_resume("big.bin", 512, 1024)

        t = threading.Thread(target=asker, daemon=True)
        t.start()
        await pilot.pause()
        banner = app.screen.query_one("#resume_approval", Static)
        assert "big.bin" in banner.render().plain
        assert "50%" in banner.render().plain
        await pilot.click("#approve_resume")
        t.join(timeout=5)
        assert result["value"] == "allow"
        # The deny path.
        result.clear()
        t2 = threading.Thread(target=asker, daemon=True)
        t2.start()
        await pilot.pause()
        await pilot.click("#deny_resume")
        t2.join(timeout=5)
        assert result["value"] == "deny"
    sender.close()
    receiver.close()
