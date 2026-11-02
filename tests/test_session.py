import sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.session import HostListener, join_session, parse_host_input


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
    # Receiver progress callback fires, and the client socket is
    # in blocking mode after handshake (not the old 30s timeout).
    client_dir = tmp_path / "client2"; host_dir = tmp_path / "host2"
    client_dir.mkdir(); host_dir.mkdir()
    (client_dir / "big.txt").write_text("x" * 500000)
    port = _free_port()
    progress = []
    host_session = {}

    def host_worker():
        listener = HostListener(port, host_dir, device="host", home=tmp_path / "jhome2", approve=lambda d, fp: True)
        s = listener.wait_for_client()
        s.on_progress = lambda n, r, t: progress.append((n, r, t))
        s.start(); host_session["s"] = s

    t = threading.Thread(target=host_worker, daemon=True); t.start(); time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "chome2", approve_fingerprint=lambda fp: True)
    client.start()
    assert client.sock.gettimeout() is None
    assert client.send_file(client_dir / "big.txt")
    time.sleep(1)
    assert progress, "receiver progress should have fired"
    assert progress[-1][1] == progress[-1][2] == 500000
    client.close(); host_session["s"].close()


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_both_directions_and_download(tmp_path):
    client_dir = tmp_path / "client"
    host_dir = tmp_path / "host"
    client_dir.mkdir(); host_dir.mkdir()
    (client_dir / "a.txt").write_text("from client")
    (host_dir / "b.txt").write_text("from host")
    port = _free_port()
    received_host, received_client = {}, {}
    host_session = {}

    def host_worker():
        listener = HostListener(port, host_dir, device="host", home=tmp_path / "jhome", approve=lambda d, fp: True)
        s = listener.wait_for_client()
        s.on_file_received = lambda n, ok, r: received_host.update({n: ok})
        s.start(); host_session["s"] = s

    t = threading.Thread(target=host_worker, daemon=True); t.start(); time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "chome", approve_fingerprint=lambda fp: True)
    client.on_file_received = lambda n, ok, r: received_client.update({n: ok})
    client.start(); time.sleep(0.5)
    assert client.peer_device == "host"
    assert client.peer_fingerprint
    assert client.send_file(client_dir / "a.txt")
    time.sleep(1)
    assert received_host.get("a.txt") is True
    assert (host_dir / "a.txt").read_text() == "from client"
    assert host_session["s"].send_file(host_dir / "b.txt")
    time.sleep(1)
    assert received_client.get("b.txt") is True
    assert (client_dir / "b.txt").read_text() == "from host"
    client.close(); host_session["s"].close()


def test_fingerprint_change_aborts(tmp_path):
    # First session records a fingerprint, second session with a
    # different host identity and that fingerprint as known must abort.
    port = _free_port()
    host_dir = tmp_path / "host"; host_dir.mkdir()
    client_dir = tmp_path / "client"; client_dir.mkdir()

    def host_worker(home):
        listener = HostListener(port, host_dir, device="host", home=home, approve=lambda d, fp: True)
        try:
            s = listener.wait_for_client(); s.start()
        except Exception:
            pass

    t = threading.Thread(target=host_worker, args=(tmp_path / "jhome1",), daemon=True); t.start(); time.sleep(0.5)
    first = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "chome", approve_fingerprint=lambda fp: True)
    fp = first.peer_fingerprint; first.close(); t.join(timeout=2)

    port2 = _free_port()
    listener = HostListener(port2, host_dir, device="host", home=tmp_path / "jhome2", approve=lambda d, fp: True)
    th = threading.Thread(target=lambda: listener.wait_for_client(), daemon=True); th.start(); time.sleep(0.5)
    try:
        join_session("127.0.0.1", port2, client_dir, device="client", home=tmp_path / "chome", known_fingerprint=fp)
        assert False, "changed fingerprint should abort"
    except Exception as exc:
        assert "fingerprint changed" in str(exc)


def test_download_ask_requires_peer_allow(tmp_path):
    import socket as _socket
    def _free():
        with _socket.socket() as s:
            s.bind(("127.0.0.1", 0)); return s.getsockname()[1]
    client_dir = tmp_path / "c3"; host_dir = tmp_path / "j3"
    client_dir.mkdir(); host_dir.mkdir()
    secret = host_dir / "secret.txt"; secret.write_text("peer file")
    port = _free()
    asked = {}
    host_session = {}
    def host_worker():
        listener = HostListener(port, host_dir, device="host", home=tmp_path / "jh3", approve=lambda d, fp: True)
        s = listener.wait_for_client()
        s.on_download_ask = lambda n, rid: asked.update({"name": n, "id": rid, "session": s})
        s.start(); host_session["s"] = s
    t = threading.Thread(target=host_worker, daemon=True); t.start(); time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / "ch3", approve_fingerprint=lambda fp: True)
    client.start(); time.sleep(0.5)
    # Absolute path on the peer, via approval flow.
    assert client.request_download(str(secret), request_id="req-1")
    time.sleep(1)
    assert asked.get("name") == str(secret)
    # No file yet, before approval.
    assert not (client_dir / "secret.txt").exists()
    # Peer allows: file arrives.
    assert host_session["s"].respond_download(asked["name"], asked["id"], True)
    time.sleep(1)
    assert (client_dir / "secret.txt").read_text() == "peer file"
    # Deny path: second file is not sent.
    denied = {}
    client.on_download_denied = lambda n, rid: denied.update({"name": n})
    (host_dir / "nope.txt").write_text("no")
    assert client.request_download(str(host_dir / "nope.txt"), request_id="req-2")
    time.sleep(1)
    assert host_session["s"].respond_download(str(host_dir / "nope.txt"), "req-2", False)
    time.sleep(1)
    assert denied.get("name") == str(host_dir / "nope.txt")
    assert not (client_dir / "nope.txt").exists()
    client.close(); host_session["s"].close()
