import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.pairing import (
    CODE_TTL_SECONDS,
    PairingCode,
    PairingServer,
    append_authorized_key,
    generate_code,
    remove_authorized_key,
    send_pairing,
)


def test_code_format_and_expiry():
    code = generate_code()
    assert len(code) == 6 and code.isdigit()
    pairing = PairingCode(code)
    assert pairing.is_valid(code)
    assert not pairing.is_valid("000000")
    assert not pairing.is_valid(code, now=pairing.created_at + CODE_TTL_SECONDS + 1)


def test_authorized_key_dedupe_and_remove(tmp_path):
    auth = tmp_path / "authorized_keys"
    key = "ssh-ed25519 AAAAC3 friend"
    assert append_authorized_key(auth, key, "friend") is True
    assert append_authorized_key(auth, key, "friend") is False
    assert remove_authorized_key(auth, key) is True
    assert remove_authorized_key(auth, key) is False


def test_pairing_server_and_client(tmp_path):
    auth = tmp_path / "authorized_keys"
    seen = []
    code = PairingCode(generate_code())
    server = PairingServer(code, auth, host="127.0.0.1", port=0,
                           on_success=lambda d, k: seen.append((d, k)))
    server.start()
    try:
        result = send_pairing("127.0.0.1", server.port, code.code, "laptop", "ssh-ed25519 AAAAC3 laptop")
        assert result.get("ok") is True
        assert seen == [("laptop", "ssh-ed25519 AAAAC3 laptop")]
        assert "ssh-ed25519 AAAAC3 laptop" in auth.read_text()
        # Code is single-use.
        result2 = send_pairing("127.0.0.1", server.port, code.code, "laptop", "ssh-ed25519 AAAAC3 laptop")
        assert result2.get("ok") is False
    finally:
        server.stop()


def test_pairing_wrong_code(tmp_path):
    auth = tmp_path / "authorized_keys"
    code = PairingCode(generate_code())
    server = PairingServer(code, auth, host="127.0.0.1", port=0)
    server.start()
    try:
        result = send_pairing("127.0.0.1", server.port, "000000", "laptop", "ssh-ed25519 AAAAC3 x")
        assert result.get("ok") is False
        assert not auth.exists()
    finally:
        server.stop()
