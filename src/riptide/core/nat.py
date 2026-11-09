"""Public IP helpers. User-facing text never contains a port number."""
from __future__ import annotations

import ipaddress
import socket
import struct


def _xor_mapped_address(data: bytes, transaction_id: bytes) -> str | None:
    """Decode XOR-MAPPED-ADDRESS (0x0020) from a STUN Binding Response.

    Returns the address string, IPv4 for an 8-byte value and IPv6
    for a 20-byte value, or None when the attribute is absent.
    The address bytes are XORed with the magic cookie followed by
    the transaction ID.
    """
    if len(data) < 20:
        return None
    key = struct.pack(">I", 0x2112A442) + transaction_id
    pos = 20
    while pos + 4 <= len(data):
        atype, alen = struct.unpack(">HH", data[pos:pos + 4])
        val = data[pos + 4:pos + 4 + alen]
        if atype == 0x0020:
            if len(val) == 8:  # IPv4
                xaddr = struct.unpack(">I", val[4:8])[0] ^ 0x2112A442
                return socket.inet_ntoa(struct.pack(">I", xaddr))
            if len(val) == 20:  # IPv6
                xbytes = bytes(b ^ key[i] for i, b in enumerate(val[4:20]))
                return socket.inet_ntop(socket.AF_INET6, xbytes)
        pos += 4 + ((alen + 3) // 4 * 4)
    return None


def stun_public_ip(timeout: float = 2.0) -> str | None:
    """Public address as seen from the internet, via a STUN binding.

    Sends a minimal RFC 5389 Binding Request to a public STUN
    server over UDP and parses XOR-MAPPED-ADDRESS. Returns None
    on any failure, including no internet or a blocked UDP port.
    """
    import struct
    try:
        transaction_id = bytes(12)
        req = struct.pack(">HHI", 0x0001, 0, 0x2112A442) + transaction_id
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(req, ("stun.l.google.com", 19302))
            data, _addr = sock.recvfrom(2048)
        return _xor_mapped_address(data, transaction_id)
    except Exception:
        pass
    return None


def public_ipv6() -> str | None:
    """Current public IPv6 address, via HTTPS lookup.

    Returns None when the host has no IPv6. There is no STUN step
    here: the public STUN servers are IPv4-only (stun.l.google.com
    publishes no IPv6 address), so the lookup goes to IPv6-only
    echo services instead. Both only answer over IPv6, so a host
    without it fails fast and the row stays hidden.
    """
    import urllib.request
    for url in ("https://api6.ipify.org", "https://ipv6.icanhazip.com"):
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                candidate = resp.read().decode(errors="ignore").strip()
            addr = ipaddress.ip_address(candidate)
            if addr.version == 6:
                return candidate
        except Exception:
            continue
    return None



def public_ip() -> str | None:
    """Current public address, STUN first, HTTPS fallback.

    Returns None if neither works. This is the address the Create
    Server page shows, so the client knows what to dial. Behind
    CGNAT it is the shared CGNAT address, not a directly reachable
    one.
    """
    ip = stun_public_ip()
    if ip:
        return ip
    import urllib.request
    for url in ("https://api.ipify.org", "https://checkip.amazonaws.com"):
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                candidate = resp.read().decode(errors="ignore").strip()
            ipaddress.ip_address(candidate)
            return candidate
        except Exception:
            continue
    return None



