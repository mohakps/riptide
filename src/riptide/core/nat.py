"""NAT / CGNAT helpers. User-facing text never contains a port number."""
from __future__ import annotations

import ipaddress
import socket


def is_private_ip(text: str) -> bool:
    try:
        return ipaddress.ip_address(text).is_private
    except Exception:
        return False


def is_cgnat_ip(text: str) -> bool:
    try:
        addr = ipaddress.ip_address(text)
        return addr in ipaddress.ip_network("100.64.0.0/10")
    except Exception:
        return False


def detect_cgnat(wan_ip: str, public_ip: str) -> bool:
    """True when the router WAN address is CGNAT, or differs from public IP
    while being private. Comparing the two is the reliable CGNAT check."""
    if not wan_ip or not public_ip:
        return False
    if is_cgnat_ip(wan_ip):
        return True
    return wan_ip != public_ip and is_private_ip(wan_ip)


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
