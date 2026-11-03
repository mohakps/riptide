import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.identity import fingerprint_code, fingerprint_code_from_cert_der
from riptide.screens.join import join_fingerprint_body


def test_fingerprint_code_derivation():
    # First 3 bytes of the fingerprint, modulo 1,000,000, grouped.
    # 0x123456 = 1193046, modulo 1000000 = 193046, so 193-046.
    assert fingerprint_code("123456" + "ab" * 29) == "193-046"
    # Same fingerprint always gives the same code.
    assert fingerprint_code("123456" + "ab" * 29) == fingerprint_code("123456" + "ab" * 29)
    # Different fingerprint gives a different code in the normal case.
    assert fingerprint_code("abcdef" + "00" * 29) != fingerprint_code("123456" + "ab" * 29)
    # Case-insensitive hex.
    assert fingerprint_code("ABCDEF" + "00" * 29) == fingerprint_code("abcdef" + "00" * 29)


def test_fingerprint_code_leading_zeros():
    # 0x000001 = 1, so code is 000-001, leading zeros preserved.
    assert fingerprint_code("000001" + "00" * 29) == "000-001"
    # 0x000000 = 0, so code is 000-000.
    assert fingerprint_code("000000" + "00" * 29) == "000-000"


def test_fingerprint_code_invalid():
    assert fingerprint_code("") == "------"
    assert fingerprint_code("abc") == "------"
    assert fingerprint_code("zzzzzz" + "00" * 29) == "------"
    assert fingerprint_code(None) == "------"  # type: ignore[arg-type]


def test_fingerprint_code_from_cert_der():
    # A real cert DER, via its fingerprint, must give the same code
    # as fingerprint_code on that fingerprint.
    import hashlib

    der = b"test-certificate-bytes"
    fp = hashlib.sha256(der).hexdigest()
    assert fingerprint_code_from_cert_der(der) == fingerprint_code(fp)


def test_join_fingerprint_body_shows_code_and_full_fingerprint():
    fp = "123456" + "ab" * 29
    body = join_fingerprint_body(fp)
    assert "Host code: [bold #FFD166]193-046[/]" in body
    assert "Compare this code with the host out of band" in body
    assert fp[:32] in body
    assert fp[32:] in body
    assert "Allow to trust this host?" in body


def test_join_fingerprint_body_missing():
    body = join_fingerprint_body("")
    assert "Host code: [bold #FFD166]------[/]" in body
    assert "missing" in body
