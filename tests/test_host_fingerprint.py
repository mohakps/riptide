import base64
import socket
import ssl
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.config import load_config
from riptide.core.identity import cert_der_from_pem, cert_fingerprint, ensure_identity
from riptide.core.session import HostListener, join_session


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_host(port, host_dir, home, approve, result):
    try:
        listener = HostListener(port, host_dir, device="host", home=home, approve=approve)
        session = listener.wait_for_client()
        result["session"] = session
        result["status"] = session.client_trust_status
    except Exception as exc:
        result["error"] = str(exc)


def test_host_fingerprint_known_new_changed(tmp_path):
    host_dir = tmp_path / "host"
    client_dir = tmp_path / "client"
    host_dir.mkdir()
    client_dir.mkdir()
    host_home = tmp_path / "jhome"
    client_home = tmp_path / "chome"

    # First connection: new, fingerprint must be non-empty and saved.
    port = _free_port()
    seen = {}
    result = {}
    t = threading.Thread(target=_run_host, args=(port, host_dir, host_home, lambda d, fp, st, old: seen.update({"d": d, "fp": fp, "st": st, "old": old}) or True, result), daemon=True)
    t.start()
    time.sleep(0.5)
    client = join_session("127.0.0.1", port, client_dir, device="client", home=client_home, approve_fingerprint=lambda fp: True)
    t.join(timeout=5)
    assert "error" not in result, result.get("error")
    assert seen["st"] == "new"
    assert seen["fp"], "host fingerprint must not be empty in v1.1"
    assert result["session"].peer_fingerprint == seen["fp"]
    # Fingerprint must match the client certificate, not just any string.
    _k, c = ensure_identity(client_home)
    assert seen["fp"] == cert_fingerprint(cert_der_from_pem(c))
    saved = load_config(host_home)
    assert saved.trusted_client_for_fingerprint(seen["fp"]) is not None
    client.close()
    result["session"].close()
    first_fp = seen["fp"]

    # Second connection, same client identity: known.
    port = _free_port()
    seen2 = {}
    result2 = {}
    t = threading.Thread(target=_run_host, args=(port, host_dir, host_home, lambda d, fp, st, old: seen2.update({"st": st, "fp": fp}) or True, result2), daemon=True)
    t.start()
    time.sleep(0.5)
    client2 = join_session("127.0.0.1", port, client_dir, device="client", home=client_home, approve_fingerprint=lambda fp: True)
    t.join(timeout=5)
    assert "error" not in result2, result2.get("error")
    assert seen2["st"] == "known"
    assert seen2["fp"] == first_fp
    client2.close()
    result2["session"].close()

    # Third connection, new client identity, same device name: changed.
    # An old 2-arg approve callback must abort, not silently replace.
    client_home2 = tmp_path / "chome2"
    port = _free_port()
    result3 = {}
    t = threading.Thread(target=_run_host, args=(port, host_dir, host_home, lambda d, fp: True, result3), daemon=True)
    t.start()
    time.sleep(0.5)
    try:
        join_session("127.0.0.1", port, client_dir, device="client", home=client_home2, approve_fingerprint=lambda fp: True)
        assert False, "changed fingerprint with old approve callback should abort"
    except Exception as exc:
        assert "fingerprint changed" in str(exc) or "host rejected" in str(exc) or "session closed" in str(exc)
    t.join(timeout=5)
    assert "error" in result3
    assert "fingerprint changed" in result3["error"]

    # Same changed case, with a new 4-arg approve callback returning True:
    # it should succeed and replace the saved fingerprint.
    port = _free_port()
    seen4 = {}
    result4 = {}
    t = threading.Thread(target=_run_host, args=(port, host_dir, host_home, lambda d, fp, st, old: seen4.update({"st": st, "old": old, "fp": fp}) or True, result4), daemon=True)
    t.start()
    time.sleep(0.5)
    client4 = join_session("127.0.0.1", port, client_dir, device="client", home=client_home2, approve_fingerprint=lambda fp: True)
    t.join(timeout=5)
    assert "error" not in result4, result4.get("error")
    assert seen4["st"] == "changed"
    assert seen4["old"] == first_fp
    assert seen4["fp"] != first_fp
    saved2 = load_config(host_home)
    assert saved2.trusted_client_for_fingerprint(seen4["fp"]) is not None
    client4.close()
    result4["session"].close()


def test_host_missing_client_fingerprint_aborts(tmp_path):
    # Simulate a v1.0 client: TLS, then hello with no cert field.
    host_dir = tmp_path / "host"
    host_dir.mkdir()
    host_home = tmp_path / "jhome"
    port = _free_port()
    called = {}
    result = {}
    t = threading.Thread(target=_run_host, args=(port, host_dir, host_home, lambda d, fp, st, old: called.update({"yes": True}) or True, result), daemon=True)
    t.start()
    time.sleep(0.5)
    # Raw TLS client, no Riptide join_session, so no cert is sent.
    _k, hc = ensure_identity(host_home)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(str(hc), str(_k))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    raw = socket.create_connection(("127.0.0.1", port), timeout=5)
    tls = ctx.wrap_socket(raw, server_hostname="127.0.0.1")
    try:
        import json
        import struct

        raw_hello = json.dumps({"type": "hello", "device": "old-client", "host": "127.0.0.1"}).encode()
        tls.sendall(struct.pack(">I", len(raw_hello)) + raw_hello)
        # Host should send an error header, then close.
        raw_len = tls.recv(4)
        assert raw_len, "host should reply, not hang"
        (length,) = struct.unpack(">I", raw_len)
        reply = json.loads(tls.recv(length).decode())
        assert reply.get("type") == "error"
        assert "fingerprint missing" in reply.get("message", "")
    finally:
        tls.close()
    t.join(timeout=5)
    assert "error" in result
    assert "fingerprint missing" in result["error"]
    assert "yes" not in called, "approval must not be shown for an empty fingerprint"


def test_host_bad_signature_aborts(tmp_path):
    host_dir = tmp_path / "host"
    host_dir.mkdir()
    host_home = tmp_path / "jhome"
    client_home = tmp_path / "chome"
    port = _free_port()
    called = {}
    result = {}
    t = threading.Thread(target=_run_host, args=(port, host_dir, host_home, lambda d, fp, st, old: called.update({"yes": True}) or True, result), daemon=True)
    t.start()
    time.sleep(0.5)
    _k, hc = ensure_identity(host_home)
    ck, cc = ensure_identity(client_home)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(str(cc), str(ck))
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    raw = socket.create_connection(("127.0.0.1", port), timeout=5)
    tls = ctx.wrap_socket(raw, server_hostname="127.0.0.1")
    try:
        import json
        import struct

        def send(obj):
            data = json.dumps(obj).encode()
            tls.sendall(struct.pack(">I", len(data)) + data)

        def recv_obj():
            raw_len = tls.recv(4)
            (length,) = struct.unpack(">I", raw_len)
            return json.loads(tls.recv(length).decode())

        cert_b64 = base64.b64encode(cert_der_from_pem(cc)).decode()
        send({"type": "hello", "device": "client", "host": "127.0.0.1", "cert": cert_b64})
        challenge = recv_obj()
        assert challenge.get("type") == "hello_challenge"
        # Bad signature: garbage bytes, not a signature over the nonce.
        send({"type": "hello_proof", "signature": base64.b64encode(b"not-a-signature").decode()})
        reply = recv_obj()
        assert reply.get("type") == "error"
        assert "signature" in reply.get("message", "")
    finally:
        tls.close()
    t.join(timeout=5)
    assert "error" in result
    assert "signature" in result["error"]
    assert "yes" not in called
