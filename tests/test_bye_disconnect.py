import sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.session import HostListener, join_session


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _paired_session(tmp_path, label):
    client_dir = tmp_path / f"client-{label}"
    host_dir = tmp_path / f"host-{label}"
    client_dir.mkdir(); host_dir.mkdir()
    port = _free_port()
    host_session = {}
    host_errors = []
    host_disconnects = []

    def host_worker():
        listener = HostListener(port, host_dir, device="host", home=tmp_path / f"jhome-{label}", approve=lambda d, fp: True)
        s = listener.wait_for_client()
        s.on_error = lambda m: host_errors.append(m)
        s.on_disconnect = lambda: host_disconnects.append(True)
        s.start(); host_session["s"] = s

    t = threading.Thread(target=host_worker, daemon=True); t.start(); time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=tmp_path / f"chome-{label}", approve_fingerprint=lambda fp: True)
    client.start()
    time.sleep(0.5)
    return client, host_session, host_errors, host_disconnects


def test_peer_bye_notifies_host_disconnect(tmp_path):
    # The phone sends bye on Disconnect. Before this fix the host
    # reader broke out of its loop silently, so the UI never
    # learned the session ended and kept showing connected.
    client, host_session, host_errors, host_disconnects = _paired_session(tmp_path, "bye")
    client.close()
    assert host_session["s"].wait_ended(timeout=5)
    assert host_errors == ["peer disconnected"]
    assert len(host_disconnects) == 1
    # Closing our side afterwards must not notify a second time.
    host_session["s"].close()
    time.sleep(0.3)
    assert host_errors == ["peer disconnected"]
    assert len(host_disconnects) == 1


def test_dropped_connection_notifies_host_disconnect(tmp_path):
    # No bye at all: the peer socket just goes away. The host must
    # still learn the session ended, once. shutdown() is used
    # instead of a bare close(), because closing a socket from
    # another thread does not send FIN while the peer's own reader
    # is blocked in recv on it; shutdown forces the FIN out.
    import socket
    client, host_session, host_errors, host_disconnects = _paired_session(tmp_path, "drop")
    client.sock.shutdown(socket.SHUT_RDWR)
    client.sock.close()
    assert host_session["s"].wait_ended(timeout=5)
    assert len(host_errors) == 1
    assert host_errors[0].startswith("session ended:")
    assert len(host_disconnects) == 1
    host_session["s"].close()


def test_listener_stop_frees_port(tmp_path):
    # Regression test: stop() used to only close() the server
    # socket, which does not wake a thread blocked in accept(), so
    # the worker stayed blocked and the port stayed bound, and the
    # next Create Server page failed to bind with EADDRINUSE.
    # shutdown() wakes accept() at once.
    import socket

    port = _free_port()
    listener = HostListener(port, tmp_path / "host", device="host", home=tmp_path / "home", approve=lambda d, fp: True)
    errors = []

    def wait():
        try:
            listener.wait_for_client()
        except Exception as exc:  # noqa: BLE001 - collected, asserted below
            errors.append(exc)

    t = threading.Thread(target=wait, daemon=True)
    t.start()
    time.sleep(0.5)
    listener.stop()
    t.join(timeout=5)
    assert not t.is_alive(), "wait_for_client did not return after stop()"
    # The port must be bindable again straight away.
    probe = socket.socket()
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", port))
    finally:
        probe.close()
