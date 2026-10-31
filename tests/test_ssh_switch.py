import sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.session import JoinListener, create_session
from riptide.core.keys import append_authorized_key, authorized_keys_path


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_ssh_key_exchange_over_tls(tmp_path):
    port = _free_port()
    creator_dir = tmp_path / "creator"; joiner_dir = tmp_path / "joiner"
    creator_dir.mkdir(); joiner_dir.mkdir()
    join_session = {}

    def join_worker():
        listener = JoinListener(port, joiner_dir, device="joiner", home=tmp_path / "jhome", approve=lambda d, fp: True)
        s = listener.wait_for_creator(exchange_ssh_keys=True)
        s.start(); join_session["s"] = s

    t = threading.Thread(target=join_worker, daemon=True); t.start(); time.sleep(0.5)
    creator = create_session("127.0.0.1", port, creator_dir, device="creator", home=tmp_path / "chome", approve_fingerprint=lambda fp: True, exchange_ssh_keys=True)
    creator.start(); time.sleep(0.5)
    # Both sides should now have each other's SSH public key in authorized_keys.
    creator_auth = authorized_keys_path(tmp_path / "chome").read_text() if authorized_keys_path(tmp_path / "chome").exists() else ""
    joiner_auth = authorized_keys_path(tmp_path / "jhome").read_text() if authorized_keys_path(tmp_path / "jhome").exists() else ""
    assert "ssh-ed25519" in creator_auth
    assert "ssh-ed25519" in joiner_auth
    creator.close(); join_session["s"].close()


def test_ssh_download_request_control(tmp_path):
    port = _free_port()
    creator_dir = tmp_path / "creator"; joiner_dir = tmp_path / "joiner"
    creator_dir.mkdir(); joiner_dir.mkdir()
    received = {}
    join_session = {}

    def join_worker():
        listener = JoinListener(port, joiner_dir, device="joiner", home=tmp_path / "jhome2", approve=lambda d, fp: True)
        s = listener.wait_for_creator()
        s.start(); join_session["s"] = s

    t = threading.Thread(target=join_worker, daemon=True); t.start(); time.sleep(0.5)
    creator = create_session("127.0.0.1", port, creator_dir, device="creator", home=tmp_path / "chome2", approve_fingerprint=lambda fp: True)
    creator.on_ssh_download_request = lambda name: received.update({name: True})
    creator.start(); time.sleep(0.5)
    assert join_session["s"].send_ssh_download_request("hello.txt")
    time.sleep(1)
    assert received.get("hello.txt") is True
    creator.close(); join_session["s"].close()
