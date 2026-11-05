import ssl
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.identity import (
    _pair_matches,
    cert_der_from_pem,
    cert_fingerprint,
    ensure_identity,
)


def _loadable_pair(key_path: Path, cert_path: Path) -> bool:
    """Exactly what the listener does: load the pair into an SSL context."""
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert_path), str(key_path))
        return True
    except ssl.SSLError:
        return False


def test_concurrent_ensure_identity_gives_one_matching_pair(tmp_path):
    # Regression test for the first-launch KEY_VALUES_MISMATCH: the
    # Create screen calls ensure_identity from two threads at once
    # (My code, and the listener). With the identity deleted, both
    # used to generate different keypairs and interleave their
    # writes, leaving a key from one pair and a cert from the other.
    home = tmp_path / "home"
    results = []
    errors = []

    def call():
        try:
            results.append(ensure_identity(home))
        except Exception as exc:  # noqa: BLE001 - collected, asserted below
            errors.append(exc)

    threads = [threading.Thread(target=call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors
    assert len(results) == 8
    assert len({r for r in results}) == 1
    key_path, cert_path = results[0]
    assert _pair_matches(key_path, cert_path)
    assert _loadable_pair(key_path, cert_path)
    fingerprints = {cert_fingerprint(cert_der_from_pem(cert_path)) for _ in results}
    assert len(fingerprints) == 1


def test_ensure_identity_reuses_existing_pair(tmp_path):
    home = tmp_path / "home"
    key_path, cert_path = ensure_identity(home)
    fingerprint = cert_fingerprint(cert_der_from_pem(cert_path))
    key_mtime = key_path.stat().st_mtime_ns
    cert_mtime = cert_path.stat().st_mtime_ns
    key_path2, cert_path2 = ensure_identity(home)
    assert (key_path2, cert_path2) == (key_path, cert_path)
    assert cert_fingerprint(cert_der_from_pem(cert_path2)) == fingerprint
    assert key_path.stat().st_mtime_ns == key_mtime
    assert cert_path.stat().st_mtime_ns == cert_mtime


def test_ensure_identity_repairs_mismatched_pair(tmp_path):
    # A key from one identity and a cert from another, as an
    # interrupted write used to leave behind. The next call must
    # regenerate a matching pair instead of failing on every launch.
    home_a = tmp_path / "a"
    home_b = tmp_path / "b"
    key_a, _ = ensure_identity(home_a)
    _, cert_b = ensure_identity(home_b)
    home = tmp_path / "home"
    (home / ".riptide").mkdir(parents=True)
    (home / ".riptide" / "identity.key").write_bytes(key_a.read_bytes())
    (home / ".riptide" / "identity.crt").write_bytes(cert_b.read_bytes())
    assert not _pair_matches(home / ".riptide" / "identity.key", home / ".riptide" / "identity.crt")
    assert not _loadable_pair(home / ".riptide" / "identity.key", home / ".riptide" / "identity.crt")

    key_path, cert_path = ensure_identity(home)
    assert _pair_matches(key_path, cert_path)
    assert _loadable_pair(key_path, cert_path)
    # And the repaired pair stays stable on the next call.
    key_path2, cert_path2 = ensure_identity(home)
    assert (key_path2, cert_path2) == (key_path, cert_path)
