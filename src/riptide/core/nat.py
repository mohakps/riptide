"""Public IP helpers. User-facing text never contains a port number."""
from __future__ import annotations

import ipaddress
import socket


def stun_public_ip(timeout: float = 2.0) -> str | None:
    """Public address as seen from the internet, via a STUN binding.

    Sends a minimal RFC 5389 Binding Request to a public STUN
    server over UDP and parses XOR-MAPPED-ADDRESS. Returns None
    on any failure, including no internet or a blocked UDP port.
    """
    import struct
    try:
        req = struct.pack(">HHI", 0x0001, 0, 0x2112A442) + bytes(12)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(req, ("stun.l.google.com", 19302))
            data, _addr = sock.recvfrom(2048)
        if len(data) < 20:
            return None
        # Walk attributes after the 20-byte header.
        pos = 20
        while pos + 4 <= len(data):
            atype, alen = struct.unpack(">HH", data[pos:pos + 4])
            val = data[pos + 4:pos + 4 + alen]
            if atype == 0x0020 and len(val) >= 8:  # XOR-MAPPED-ADDRESS, IPv4
                port = struct.unpack(">H", val[2:4])[0] ^ 0x2112
                xaddr = struct.unpack(">I", val[4:8])[0] ^ 0x2112A442
                return socket.inet_ntoa(struct.pack(">I", xaddr))
            pos += 4 + ((alen + 3) // 4 * 4)
    except Exception:
        pass
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








