"""NAT / CGNAT helpers. User-facing text never contains a port number."""
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
    Server page shows, so the joiner knows what to dial. Behind
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


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except Exception:
        return "127.0.0.1"


def upnp_attempt() -> tuple[bool, str]:
    """Best-effort UPnP. Returns (ok, message) without ever promising success."""
    try:
        import miniupnpc  # type: ignore
    except Exception:
        return False, "UPnP library not available. Use the manual step below."
    try:
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        upnp.discover()
        upnp.selectigd()
        return True, "UPnP gateway found. If it reports success, forwarding is set."
    except Exception as exc:
        return False, f"UPnP failed: {exc}"


def manual_instructions(local: str) -> str:
    return (
        "Manual forwarding: in your router, forward SSH to this computer "
        f"(local address {local}). If your router offers an SSH service preset, "
        "use that preset. If you are behind CGNAT, forwarding will not work: "
        "use reverse mode instead, where the CGNAT peer dials the public peer, "
        "and the file direction is independent of the connection direction."
    )


REVERSE_MODE_TEXT = (
    "Reverse mode: if the receiver is behind CGNAT, the sender cannot dial it. "
    "Instead, the CGNAT peer dials the public peer first. Over that connection "
    "the CGNAT peer can either push a file up or pull a file down. "
    "Connection direction and file direction are independent."
)
