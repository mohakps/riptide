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

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path


def identity_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".riptide"


def cert_fingerprint(cert_der: bytes) -> str:
    return hashlib.sha256(cert_der).hexdigest()


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
    """Create a self-signed identity if missing, return (key_path, cert_path)."""
    directory = identity_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / "identity.key"
    cert_path = directory / "identity.crt"
    if key_path.exists() and cert_path.exists():
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
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        key_path.chmod(0o600)
    except Exception:
        pass
    return key_path, cert_path


