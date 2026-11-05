"""Self-signed TLS identity for a riptide session.

Each machine has one identity, stored under ~/.riptide/ (key file with
0600 permissions, certificate alongside it). It is NOT stored in
config.toml. Authentication is fingerprint-based, like SSH host keys:
on first connect the other side shows the certificate fingerprint and
the user presses Allow; afterwards the fingerprint is stored as a
known peer in config.toml and a changed fingerprint aborts.

Since v1.1, the host side also authenticates the client. TLS client
certificates do not work for self-signed identities, because Python
rejects them even with CERT_OPTIONAL, so the client proves its
identity with a signed hello challenge instead: the host sends a
random nonce, the client signs it with its private key, and the
host verifies the signature with the public key from the client
certificate presented in the hello message. The fingerprint is
always computed from that certificate, never trusted from a
fingerprint string sent by the client.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


def identity_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".riptide"


# Guards ensure_identity below. The Create screen calls it from two
# threads at once (one to show My code, one to start the listener),
# so without a lock both can see the identity missing, generate
# different keypairs, and interleave their writes, leaving a key
# from one pair and a certificate from the other on disk. The next
# load_cert_chain then fails with [X509: KEY_VALUES_MISMATCH].
_IDENTITY_LOCK = threading.Lock()
_IDENTITY_LOCKFILE_TIMEOUT = 10.0
_IDENTITY_LOCKFILE_STALE_AFTER = 60.0


@contextlib.contextmanager
def _identity_write_lock(directory: Path):
    """Hold the in-process lock and a lock file while writing the identity.

    The lock file also serialises two riptide processes started at the
    same time. It is created with O_EXCL, so exactly one holder wins;
    a lock older than a minute is treated as stale (holder killed
    mid-write) and removed. If the lock file cannot be acquired in
    time, the caller still proceeds under the in-process lock, so a
    stuck lock file can never wedge startup.
    """
    _IDENTITY_LOCK.acquire()
    lock_path = directory / ".identity.lock"
    fd = None
    try:
        deadline = time.monotonic() + _IDENTITY_LOCKFILE_TIMEOUT
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime > _IDENTITY_LOCKFILE_STALE_AFTER:
                        lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() > deadline:
                    break
                time.sleep(0.05)
        try:
            yield
        finally:
            if fd is not None:
                os.close(fd)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
    finally:
        _IDENTITY_LOCK.release()


def _pair_matches(key_path: Path, cert_path: Path) -> bool:
    """True when the key and certificate on disk belong together.

    Compares the public key in each file, so a pair left mismatched
    by an interrupted write is detected and regenerated instead of
    failing on every launch with KEY_VALUES_MISMATCH.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        public = (
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return key.public_key().public_bytes(*public) == cert.public_key().public_bytes(*public)
    except Exception:
        return False


def cert_fingerprint(cert_der: bytes) -> str:
    return hashlib.sha256(cert_der).hexdigest()


def fingerprint_code(fingerprint: str) -> str:
    """6-digit code for a fingerprint, grouped as 123-456.

    Since v1.3, this is the short form shown on approval popups
    so two people can compare it out of band, by call or message,
    instead of reading a full 64 hex character fingerprint aloud.
    Derivation, exactly as in the security plan: take the first
    3 bytes of the fingerprint, which is itself SHA-256 of the
    certificate DER, convert to an integer, take modulo 1,000,000,
    format with leading zeros, and group as 3 digits, dash, 3 digits.
    The code is a Short Authentication String, not a TOTP code:
    there is no shared secret on first connect, and the code does
    not change over time. It has about 20 bits of entropy, so it
    is much weaker than the full fingerprint, and the full
    fingerprint stays available in the same popup for sensitive
    transfers. An empty or invalid fingerprint returns ------,
    so the UI never shows a fake code for a missing fingerprint.
    """
    try:
        fp = (fingerprint or "").strip().lower()
        if len(fp) < 6:
            return "------"
        value = int.from_bytes(bytes.fromhex(fp[:6]), "big") % 1000000
        code = f"{value:06d}"
        return f"{code[:3]}-{code[3:]}"
    except Exception:
        return "------"


def fingerprint_code_from_cert_der(cert_der: bytes) -> str:
    """6-digit code for a certificate, via its fingerprint."""
    return fingerprint_code(cert_fingerprint(cert_der))


def cert_der_from_pem(cert_path: Path) -> bytes:
    """Return the DER bytes for a PEM certificate file."""
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding

    cert = x509.load_pem_x509_certificate(Path(cert_path).read_bytes())
    return cert.public_bytes(Encoding.DER)


def sign_nonce(key_path: Path, nonce: bytes) -> bytes:
    """Sign a nonce with the private key, RSA PKCS1v15 + SHA-256."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    return key.sign(nonce, padding.PKCS1v15(), hashes.SHA256())


def verify_nonce_signature(cert_der: bytes, nonce: bytes, signature: bytes) -> bool:
    """Verify a nonce signature against a certificate's public key.

    Returns True only on a valid signature. Any load, key type, or
    verification failure returns False, it never raises, so the
    caller can abort the session without leaking details.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        cert = x509.load_der_x509_certificate(cert_der)
        public_key = cert.public_key()
        public_key.verify(signature, nonce, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def ensure_identity(home: Path | None = None) -> tuple[Path, Path]:
    """Create a self-signed identity if missing, return (key_path, cert_path).

    Safe to call from several threads or processes at once. The whole
    check-and-generate runs under a lock, so only the first caller
    generates; the rest find the finished pair. The pair is written
    via temp files and os.replace, so a reader never sees a half
    written key or certificate, and a pair left mismatched by an
    interrupted write is detected and regenerated.
    """
    directory = identity_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / "identity.key"
    cert_path = directory / "identity.crt"
    with _identity_write_lock(directory):
        if key_path.exists() and cert_path.exists() and _pair_matches(key_path, cert_path):
            return key_path, cert_path
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
        except ImportError as exc:
            raise RuntimeError("cryptography is required for riptide sessions") from exc
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "riptide")])
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=3650))
            .sign(key, hashes.SHA256())
        )
        key_bytes = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        cert_bytes = cert.public_bytes(serialization.Encoding.PEM)
        suffix = f"{os.getpid()}-{threading.get_ident()}"
        key_tmp = directory / f".identity.key.tmp-{suffix}"
        cert_tmp = directory / f".identity.crt.tmp-{suffix}"
        key_tmp.write_bytes(key_bytes)
        try:
            key_tmp.chmod(0o600)
        except Exception:
            pass
        cert_tmp.write_bytes(cert_bytes)
        os.replace(key_tmp, key_path)
        os.replace(cert_tmp, cert_path)
    return key_path, cert_path


