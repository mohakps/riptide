import sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.session import JoinListener, create_session, parse_host_input


def test_parse_host_input():
    assert parse_host_input("metalvoid.ddns.net") == "metalvoid.ddns.net"
    assert parse_host_input("192.168.1.10") == "192.168.1.10"
    assert parse_host_input("2001:db8::1") == "2001:db8::1"
    assert parse_host_input("[2001:db8::1]") == "2001:db8::1"
    assert parse_host_input("mpsingh@metalvoid.ddns.net") == "metalvoid.ddns.net"
    assert parse_host_input("user@[2001:db8::1]") == "2001:db8::1"
    assert parse_host_input("  192.168.1.10  ") == "192.168.1.10"
    try:
        parse_host_input("")
        assert False
    except ValueError:
        pass


def test_receiver_progress_and_no_idle_timeout(tmp_path):
    # Receiver progress callback fires, and the creator socket is
    # in blocking mode after handshake (not the old 30s timeout).
    creator_dir = tmp_path / "creator2"; joiner_dir = tmp_path / "joiner2"
    creator_dir.mkdir(); joiner_dir.mkdir()
    (creator_dir / "big.txt").write_text("x" * 500000)
    port = _free_port()
    progress = []
    join_session = {}

    def join_worker():
        listener = JoinListener(port, joiner_dir, device="joiner", home=tmp_path / "jhome2", approve=lambda d, fp: True)
        s = listener.wait_for_creator()
        s.on_progress = lambda n, r, t: progress.append((n, r, t))
        s.start(); join_session["s"] = s

    t = threading.Thread(target=join_worker, daemon=True); t.start(); time.sleep(0.5)
    creator = create_session("127.0.0.1", port, creator_dir, device="creator", home=tmp_path / "chome2", approve_fingerprint=lambda fp: True)
    creator.start()
    assert creator.sock.gettimeout() is None
    assert creator.send_file(creator_dir / "big.txt")
    time.sleep(1)
    assert progress, "receiver progress should have fired"
    assert progress[-1][1] == progress[-1][2] == 500000
    creator.close(); join_session["s"].close()


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_both_directions_and_download(tmp_path):
    creator_dir = tmp_path / "creator"
    joiner_dir = tmp_path / "joiner"
    creator_dir.mkdir(); joiner_dir.mkdir()
    (creator_dir / "a.txt").write_text("from creator")
    (joiner_dir / "b.txt").write_text("from joiner")
    port = _free_port()
    received_joiner, received_creator = {}, {}
    join_session = {}

    def join_worker():
        listener = JoinListener(port, joiner_dir, device="joiner", home=tmp_path / "jhome", approve=lambda d, fp: True)
        s = listener.wait_for_creator()
        s.on_file_received = lambda n, ok, r: received_joiner.update({n: ok})
        s.start(); join_session["s"] = s

    t = threading.Thread(target=join_worker, daemon=True); t.start(); time.sleep(0.5)
    creator = create_session("127.0.0.1", port, creator_dir, device="creator", home=tmp_path / "chome", approve_fingerprint=lambda fp: True)
    creator.on_file_received = lambda n, ok, r: received_creator.update({n: ok})
    creator.start(); time.sleep(0.5)
    assert creator.peer_device == "joiner"
    assert creator.peer_fingerprint
    assert creator.send_file(creator_dir / "a.txt")
    time.sleep(1)
    assert received_joiner.get("a.txt") is True
    assert (joiner_dir / "a.txt").read_text() == "from creator"
    assert join_session["s"].send_file(joiner_dir / "b.txt")
    time.sleep(1)
    assert received_creator.get("b.txt") is True
    assert (creator_dir / "b.txt").read_text() == "from joiner"
    assert creator.request_file("b.txt")
    time.sleep(1)
    assert received_creator.get("b.txt") is True
    creator.close(); join_session["s"].close()


def test_fingerprint_change_aborts(tmp_path):
    # First session records a fingerprint, second session with a
    # different joiner identity and that fingerprint as known must abort.
    port = _free_port()
    joiner_dir = tmp_path / "joiner"; joiner_dir.mkdir()
    creator_dir = tmp_path / "creator"; creator_dir.mkdir()

    def join_worker(home):
        listener = JoinListener(port, joiner_dir, device="joiner", home=home, approve=lambda d, fp: True)
        try:
            s = listener.wait_for_creator(); s.start()
        except Exception:
            pass

    t = threading.Thread(target=join_worker, args=(tmp_path / "jhome1",), daemon=True); t.start(); time.sleep(0.5)
    first = create_session("127.0.0.1", port, creator_dir, device="creator", home=tmp_path / "chome", approve_fingerprint=lambda fp: True)
    fp = first.peer_fingerprint; first.close(); t.join(timeout=2)

    port2 = _free_port()
    listener = JoinListener(port2, joiner_dir, device="joiner", home=tmp_path / "jhome2", approve=lambda d, fp: True)
    th = threading.Thread(target=lambda: listener.wait_for_creator(), daemon=True); th.start(); time.sleep(0.5)
    try:
        create_session("127.0.0.1", port2, creator_dir, device="creator", home=tmp_path / "chome", known_fingerprint=fp)
        assert False, "changed fingerprint should abort"
    except Exception as exc:
        assert "fingerprint changed" in str(exc)


def test_download_ask_requires_peer_allow(tmp_path):
    import socket as _socket
    def _free():
        with _socket.socket() as s:
            s.bind(("127.0.0.1", 0)); return s.getsockname()[1]
    creator_dir = tmp_path / "c3"; joiner_dir = tmp_path / "j3"
    creator_dir.mkdir(); joiner_dir.mkdir()
    secret = joiner_dir / "secret.txt"; secret.write_text("peer file")
    port = _free()
    asked = {}
    join_session = {}
    def join_worker():
        listener = JoinListener(port, joiner_dir, device="joiner", home=tmp_path / "jh3", approve=lambda d, fp: True)
        s = listener.wait_for_creator()
        s.on_download_ask = lambda n, rid: asked.update({"name": n, "id": rid, "session": s})
        s.start(); join_session["s"] = s
    t = threading.Thread(target=join_worker, daemon=True); t.start(); time.sleep(0.5)
    creator = create_session("127.0.0.1", port, creator_dir, device="creator", home=tmp_path / "ch3", approve_fingerprint=lambda fp: True)
    creator.start(); time.sleep(0.5)
    # Absolute path on the peer, via approval flow.
    assert creator.request_download(str(secret), request_id="req-1")
    time.sleep(1)
    assert asked.get("name") == str(secret)
    # No file yet, before approval.
    assert not (creator_dir / "secret.txt").exists()
    # Peer allows: file arrives.
    assert join_session["s"].respond_download(asked["name"], asked["id"], True)
    time.sleep(1)
    assert (creator_dir / "secret.txt").read_text() == "peer file"
    # Deny path: second file is not sent.
    denied = {}
    creator.on_download_denied = lambda n, rid: denied.update({"name": n})
    (joiner_dir / "nope.txt").write_text("no")
    assert creator.request_download(str(joiner_dir / "nope.txt"), request_id="req-2")
    time.sleep(1)
    assert join_session["s"].respond_download(str(joiner_dir / "nope.txt"), "req-2", False)
    time.sleep(1)
    assert denied.get("name") == str(joiner_dir / "nope.txt")
    assert not (creator_dir / "nope.txt").exists()
    creator.close(); join_session["s"].close()
