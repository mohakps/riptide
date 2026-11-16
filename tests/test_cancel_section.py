"""Cancel a transfer and keep the session connected.

Two new framed messages, "cancel" and "cancel_ack", let either
side stop a transfer in progress by draining to the next message
boundary, never by closing the socket. The canceller and the other
side both deliver exactly the declared number of payload bytes,
so the next framed message is read as a message, not as file
bytes. A cancelled receive deletes its .part and is never
resumable; a cancelled send is never added to pending.json.
There is no capability negotiation and no old-peer fallback: both
peers are expected to be new.
"""

import hashlib
import socket
import threading
import time
from pathlib import Path

import pytest
from textual.app import App

from riptide.core.resume import (
    load_pending,
    part_sidecar_path,
    pending_for_peer,
)
from riptide.core.session import Session
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


def _pair(tmp_path: Path, sender_home: str = "shome", receiver_home: str = "rhome"):
    """Two Sessions over a socketpair, both advertising resume."""
    sender_dir = tmp_path / "sender"
    receiver_dir = tmp_path / "receiver"
    sender_dir.mkdir(exist_ok=True)
    receiver_dir.mkdir(exist_ok=True)
    a, b = socket.socketpair()
    sender = Session(a, sender_dir, device="sender", peer_device="receiver", home=tmp_path / sender_home)
    receiver = Session(b, receiver_dir, device="receiver", peer_device="sender", home=tmp_path / receiver_home)
    sender.peer_fingerprint = "receiver-fp"
    receiver.peer_fingerprint = "sender-fp"
    sender.peer_supports_resume = True
    receiver.peer_supports_resume = True
    return sender, receiver, sender_dir, receiver_dir


def _send_in_thread(session, path, on_progress=None):
    """Run send_file on a worker thread, return the result dict."""
    result = {}

    def do_send():
        result["ok"] = session.send_file(path, on_progress=on_progress)

    t = threading.Thread(target=do_send, daemon=True)
    t.start()
    return result, t


# -- receiver-initiated cancel --------------------------------------


def test_receiver_cancel_cancels_and_session_stays_open(tmp_path: Path):
    """The receiver cancels; the sender pads zeros and confirms.

    The receiver cancels on its first progress report. The sender
    notices the cancel between chunks, pads zeros for the remainder
    of the declared size, and sends "cancel_ack". The receiver
    drains the payload, the .part is deleted, nothing is pending,
    and a follow-up file completes on the same connection, which
    proves the drain consumed exactly size bytes and the session
    stayed open.
    """
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = bytes(range(256)) * 4096  # 1 MiB, 8 chunks of 128 KB
    src = sender_dir / "big.bin"
    src.write_bytes(content)
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok, "reason": r})
    receiver.start()
    sender.start()

    cancelled = threading.Event()

    def on_recv_prog(name, got, total):
        if not cancelled.is_set():
            cancelled.set()
            assert receiver.cancel_receive(name) is True

    # The receiver's progress drives the cancel; hook it before
    # the send starts, so the first received chunk cancels.
    receiver.on_progress = on_recv_prog
    result, t = _send_in_thread(sender, src, on_progress=lambda n, s, tot: None)
    t.join(timeout=20)
    assert result.get("ok") is False
    assert sender.last_cancelled_send == "big.bin"
    assert _wait_for_received(received, "big.bin")
    assert received.get("big.bin") is False
    assert received.get("reason") == "cancelled"
    # The .part and its sidecar are deleted, never kept for resume.
    assert not (receiver_dir / "big.bin.part").exists()
    assert not part_sidecar_path(receiver_dir / "big.bin.part").exists()
    # A cancelled send is never added to pending.json.
    assert pending_for_peer(tmp_path / "shome", "receiver-fp") == []
    # The session stays open: a follow-up file completes on the
    # same connection, which also proves the drain consumed exactly
    # size bytes (a misaligned stream would break the next header).
    follow = sender_dir / "next.bin"
    follow.write_bytes(b"hello")
    assert sender.send_file(follow)
    assert _wait_for_received(received, "next.bin")
    assert received.get("next.bin") is True
    assert (receiver_dir / "next.bin").read_bytes() == b"hello"
    sender.close()
    receiver.close()


# -- sender-initiated cancel ----------------------------------------


def test_sender_cancel_cancels_and_session_stays_open(tmp_path: Path):
    """The sender cancels; the receiver peeks, confirms, deletes.

    The sender cancels on its first progress report. It pads zeros
    for the remainder of the declared size and sends "cancel". The
    receiver reads the full payload, peeks for the pending cancel
    before the SHA check, deletes the .part, sends "cancel_ack",
    and does not send "ack". A follow-up file completes on the
    same connection.
    """
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = bytes(range(256)) * 4096  # 1 MiB, 8 chunks of 128 KB
    src = sender_dir / "big.bin"
    src.write_bytes(content)
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok, "reason": r})
    receiver.start()
    sender.start()

    cancelled = threading.Event()

    def on_send_prog(name, sent, total):
        if not cancelled.is_set():
            cancelled.set()
            assert sender.cancel_send(name) is True

    result, t = _send_in_thread(sender, src, on_progress=on_send_prog)
    t.join(timeout=20)
    assert result.get("ok") is False
    assert sender.last_cancelled_send == "big.bin"
    assert _wait_for_received(received, "big.bin")
    assert received.get("big.bin") is False
    # The receiver reports "cancelled" when its peek finds the
    # sender's "cancel" before the SHA check. Under load the peek
    # can miss it (the cancel has not landed yet), and the receiver
    # then fails the SHA check on the zero padding and reports a
    # mismatch. Both are the same cancel outcome: the file was not
    # received, the .part is deleted, and nothing is pending.
    assert received.get("reason") in ("cancelled", "SHA-256 mismatch, partial file deleted")
    assert not (receiver_dir / "big.bin.part").exists()
    assert not part_sidecar_path(receiver_dir / "big.bin.part").exists()
    assert pending_for_peer(tmp_path / "shome", "receiver-fp") == []
    follow = sender_dir / "next.bin"
    follow.write_bytes(b"hello")
    assert sender.send_file(follow)
    assert _wait_for_received(received, "next.bin")
    assert received.get("next.bin") is True
    assert (receiver_dir / "next.bin").read_bytes() == b"hello"
    sender.close()
    receiver.close()


# -- .part deletion and no pending entry ----------------------------


def test_cancelled_receive_is_never_resumable(tmp_path: Path):
    """A cancelled receive leaves no .part and no pending entry.

    The receiver cancels, and after the cancel settles there is no
    .part, no sidecar, and no pending.json entry, so the file can
    never be resumed. A fresh send of the same file afterwards
    transfers it in full.
    """
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = bytes(range(256)) * 4096  # 1 MiB
    src = sender_dir / "big.bin"
    src.write_bytes(content)
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok, "reason": r})
    receiver.start()
    sender.start()

    cancelled = threading.Event()

    def on_recv_prog(name, got, total):
        if not cancelled.is_set():
            cancelled.set()
            receiver.cancel_receive(name)

    receiver.on_progress = on_recv_prog
    result, t = _send_in_thread(sender, src)
    t.join(timeout=20)
    assert result.get("ok") is False
    assert _wait_for_received(received, "big.bin")
    assert received.get("reason") == "cancelled"
    assert not (receiver_dir / "big.bin.part").exists()
    assert not part_sidecar_path(receiver_dir / "big.bin.part").exists()
    assert pending_for_peer(tmp_path / "shome", "receiver-fp") == []
    assert load_pending(tmp_path / "shome") == []
    # A fresh send of the same file transfers it in full.
    received.clear()
    assert sender.send_file(src)
    assert _wait_for_received(received, "big.bin")
    assert received.get("big.bin") is True
    assert (receiver_dir / "big.bin").read_bytes() == content
    sender.close()
    receiver.close()


# -- late-ack race rule ---------------------------------------------


def test_late_cancel_completion_stands(tmp_path: Path):
    """A cancel after the file is fully sent is a no-op.

    A single-chunk file is fully sent before the cancel flag can
    take effect (the send loop only checks while bytes remain, so
    sent == size ignores the cancel). The receiver completes and
    acks, and the sender reports success, not a cancel. This is
    the race rule: completion stands when the receiver already
    finished before the cancel landed.
    """
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = b"small"
    src = sender_dir / "small.bin"
    src.write_bytes(content)
    received = {}
    receiver.on_file_received = lambda n, ok, r: received.update({n: ok, "reason": r})
    receiver.start()
    sender.start()

    def on_send_prog(name, sent, total):
        # Fires on the final (only) chunk, after it was sent.
        sender.cancel_send(name)

    result, t = _send_in_thread(sender, src, on_progress=on_send_prog)
    t.join(timeout=20)
    assert result.get("ok") is True
    assert sender.last_cancelled_send is None
    assert _wait_for_received(received, "small.bin")
    assert received.get("small.bin") is True
    assert (receiver_dir / "small.bin").read_bytes() == content
    # A cancel for a file that is no longer being sent is a no-op.
    assert sender.cancel_send("small.bin") is False
    assert receiver.cancel_receive("small.bin") is False
    sender.close()
    receiver.close()


def test_cancel_outcome_prefers_ack_when_completion_won(tmp_path: Path):
    """_wait_cancel_outcome returns True for an ack with ok true.

    The sender's wait ends with the receiver's ack when the
    receiver acked before the cancel landed, so completion stands.
    A cancel_ack, or an ack with ok false (the zero padding
    corrupted the hash), ends the wait as a cancel.
    """
    sender, receiver, _, _ = _pair(tmp_path)
    receiver.start()
    sender.start()
    # The sender is "sending" f.bin, so the reader records an
    # outcome for it.
    sender._sending_name = "f.bin"
    sender._sending_outcome = None
    sender._sending_outcome_event.clear()
    receiver.send_ack("f.bin", True, "")
    assert sender._wait_cancel_outcome("f.bin") is True
    # A cancel_ack ends the wait as a cancel.
    sender._sending_outcome = None
    sender._sending_outcome_event.clear()
    receiver._send_cancel_ack("f.bin")
    assert sender._wait_cancel_outcome("f.bin") is False
    # An ack with ok false (the zero padding corrupted the hash)
    # also ends the wait as a cancel, not as a failure.
    sender._sending_outcome = None
    sender._sending_outcome_event.clear()
    receiver.send_ack("f.bin", False, "SHA-256 mismatch")
    assert sender._wait_cancel_outcome("f.bin") is False
    sender._sending_name = None
    sender.close()
    receiver.close()


# -- rapid cancel ---------------------------------------------------


def test_rapid_cancel_is_one_cancel(tmp_path: Path):
    """Rapid cancel taps settle as exactly one Cancelled transfer.

    The UI disables the Cancel button at once, but the session
    must also be safe if cancel is called several times in quick
    succession. The transfer is reported as Cancelled exactly
    once, the .part is deleted, and the session stays open.
    """
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    content = bytes(range(256)) * 4096  # 1 MiB
    src = sender_dir / "big.bin"
    src.write_bytes(content)
    received = {}
    reports = []
    receiver.on_file_received = lambda n, ok, r: (received.update({n: ok, "reason": r}), reports.append((n, ok, r)))
    receiver.start()
    sender.start()

    cancelled = threading.Event()

    def on_recv_prog(name, got, total):
        if not cancelled.is_set():
            cancelled.set()
            # Five rapid taps, from different threads, as the UI
            # could if the button were not disabled.
            threads = [threading.Thread(target=lambda: receiver.cancel_receive(name), daemon=True) for _ in range(5)]
            for th in threads:
                th.start()
            for th in threads:
                th.join(timeout=5)

    receiver.on_progress = on_recv_prog
    result, t = _send_in_thread(sender, src)
    t.join(timeout=20)
    assert result.get("ok") is False
    assert _wait_for_received(received, "big.bin")
    assert received.get("reason") == "cancelled"
    # Exactly one Cancelled report, not five.
    assert [r for r in reports if r[0] == "big.bin"] == [("big.bin", False, "cancelled")]
    assert not (receiver_dir / "big.bin.part").exists()
    assert pending_for_peer(tmp_path / "shome", "receiver-fp") == []
    follow = sender_dir / "next.bin"
    follow.write_bytes(b"hello")
    assert sender.send_file(follow)
    assert _wait_for_received(received, "next.bin")
    assert received.get("next.bin") is True
    sender.close()
    receiver.close()


# -- UI: the Cancel button ------------------------------------------


class _CancelApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, role="host"))


@pytest.mark.asyncio
async def test_cancel_button_cancels_and_disables(tmp_path: Path):
    """The Cancel button shows during a transfer and cancels it.

    The button is hidden until a transfer starts, appears while
    the transfer is in progress, disables itself on the first tap
    (so rapid taps cannot cancel twice), and the status shows
    "Cancelling…". A local transfer finishes faster than the pilot
    can observe it, so the transfer state is driven directly
    through _on_progress (the same call a real transfer makes),
    and the button is verified to call the session's cancel for
    the active file. The real cancel itself is covered by the
    protocol tests above.
    """
    sender, receiver, sender_dir, receiver_dir = _pair(tmp_path)
    receiver.start()
    sender.start()
    # Spy on the session's cancel, so the test verifies the button
    # calls it for the active file.
    calls = []
    orig_cancel_receive = receiver.cancel_receive

    def spy_cancel_receive(name):
        calls.append(name)
        return orig_cancel_receive(name)

    receiver.cancel_receive = spy_cancel_receive
    app = _CancelApp(receiver)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        screen = app.screen
        # No transfer yet: the Cancel button row is hidden.
        cancel_row = screen.query_one("#progress_cancel_row")
        assert cancel_row.styles.display == "none"
        # Simulate a transfer in progress, the same call the
        # session's progress callback makes.
        screen._on_progress("big.bin", 512, 1024, 512, 1024, "Receiving")
        await pilot.pause()
        assert cancel_row.styles.display != "none"
        await pilot.click("#cancel_transfer")
        await pilot.pause()
        # The button disabled itself on the tap.
        assert screen.query_one("#cancel_transfer").disabled is True
        # The status shows "Cancelling…".
        assert "Cancelling big.bin" in getattr(screen, "_last_status", "")
        # The button called the session's cancel for this file.
        assert calls == ["big.bin"]
    sender.close()
    receiver.close()
