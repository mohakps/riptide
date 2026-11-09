import socket
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.session import HostListener, join_session


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _has_ipv6():
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::1", 0))
        return True
    except OSError:
        return False


def _start_listener(tmp_path, label, port):
    listener = HostListener(
        port, tmp_path / f"host-{label}", device="host",
        home=tmp_path / f"jhome-{label}", approve=lambda d, fp: True,
    )
    result = {}

    def run():
        try:
            result["session"] = listener.wait_for_client()
        except Exception as exc:  # noqa: BLE001 - collected, asserted by caller
            result["error"] = exc

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return listener, result, t


def test_ipv4_client_still_connects(tmp_path):
    # The listener must keep accepting IPv4 exactly as before.
    port = _free_port()
    listener, result, t = _start_listener(tmp_path, "v4", port)
    time.sleep(0.5)
    client = join_session(
        "127.0.0.1", port, tmp_path / "client-v4", device="client",
        home=tmp_path / "chome-v4", approve_fingerprint=lambda fp: True,
    )
    client.start()
    t.join(timeout=5)
    assert "session" in result, f"host failed: {result.get('error')!r}"
    assert not t.is_alive()
    client.close()
    result["session"].close()


def test_ipv6_client_connects(tmp_path):
    # Regression test for the phone timing out after 30s: the old
    # listener bound AF_INET / 0.0.0.0 only, so an IPv6 dial to the
    # host's global address could never reach it.
    if not _has_ipv6():
        pytest.skip("no IPv6 on this host")
    port = _free_port()
    listener, result, t = _start_listener(tmp_path, "v6", port)
    time.sleep(0.5)
    client = join_session(
        "::1", port, tmp_path / "client-v6", device="client",
        home=tmp_path / "chome-v6", approve_fingerprint=lambda fp: True,
    )
    client.start()
    t.join(timeout=5)
    assert "session" in result, f"host failed: {result.get('error')!r}"
    assert not t.is_alive()
    client.close()
    result["session"].close()


def test_listener_is_dual_stack(tmp_path):
    # The listener socket itself must be AF_INET6 with
    # IPV6_V6ONLY=0, so one socket accepts both families.
    if not _has_ipv6():
        pytest.skip("no IPv6 on this host")
    port = _free_port()
    listener, result, t = _start_listener(tmp_path, "dual", port)
    try:
        deadline = time.monotonic() + 5
        while not listener._server_socks and time.monotonic() < deadline:
            time.sleep(0.1)
        assert len(listener._server_socks) == 1
        server = listener._server_socks[0]
        assert server.family == socket.AF_INET6
        assert server.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY) == 0
    finally:
        listener.stop()
        t.join(timeout=5)
    assert not t.is_alive(), "wait_for_client did not return after stop()"


def _two_sockets(port):
    s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s4.bind(("127.0.0.1", port))
    s4.listen(1)
    s6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    s6.bind(("::1", port))
    s6.listen(1)
    return s4, s6


def test_accept_one_picks_the_ready_socket(tmp_path):
    # The per-family fallback path (one socket per family) waits on
    # both with select and accepts whichever gets a connection.
    if not _has_ipv6():
        pytest.skip("no IPv6 on this host")
    port = _free_port()
    s4, s6 = _two_sockets(port)
    listener = HostListener(port, tmp_path, device="host", home=tmp_path)
    result = {}

    def run():
        try:
            result["conn"] = listener._accept_one([s4, s6], timeout=5)
        except Exception as exc:  # noqa: BLE001 - collected, asserted below
            result["error"] = exc

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.3)
    client = socket.create_connection(("::1", port), timeout=5)
    t.join(timeout=5)
    try:
        assert not t.is_alive()
        assert "conn" in result, f"accept failed: {result.get('error')!r}"
        conn, addr = result["conn"]
        assert addr[0] == "::1"
        conn.close()
    finally:
        client.close()
        s4.close()
        s6.close()


def test_stop_wakes_two_socket_accept(tmp_path):
    # stop() must wake the select() wait even with two sockets, so
    # leaving Create still releases the port at once.
    if not _has_ipv6():
        pytest.skip("no IPv6 on this host")
    port = _free_port()
    s4, s6 = _two_sockets(port)
    listener = HostListener(port, tmp_path, device="host", home=tmp_path)
    listener._server_socks = [s4, s6]
    errors = []

    def run():
        try:
            listener._accept_one([s4, s6], timeout=None)
        except Exception as exc:  # noqa: BLE001 - collected, asserted below
            errors.append(exc)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.5)
    listener.stop()
    t.join(timeout=5)
    assert not t.is_alive(), "accept did not return after stop()"
    assert errors, "expected _accept_one to raise after stop()"
