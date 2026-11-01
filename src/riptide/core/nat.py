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


def upnp_wan_ip(timeout: float = 2.5) -> str | None:
    """Router WAN address via stdlib UPnP only, no extra dependency.

    Discovers an Internet Gateway Device with SSDP, fetches its
    description, then calls GetExternalIPAddress over SOAP. Any
    failure returns None, never raises, because many routers have
    UPnP off. This is the address the ISP gave the router, which
    is the one that tells CGNAT apart from a normal home NAT.
    """
    import http.client
    import urllib.parse
    import urllib.request
    import xml.etree.ElementTree as ET

    try:
        req = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ns=01"\r\n'
            "MX: 2\r\n"
            "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n"
        ).encode()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(req, ("239.255.255.250", 1900))
            locations: list[str] = []
            try:
                while True:
                    data, _addr = sock.recvfrom(65535)
                    for line in data.decode(errors="ignore").splitlines():
                        if line.lower().startswith("location:"):
                            locations.append(line.split(":", 1)[1].strip())
            except Exception:
                pass
        for loc in locations:
            try:
                with urllib.request.urlopen(loc, timeout=timeout) as resp:
                    xml = resp.read()
                root = ET.fromstring(xml)
                ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                control = None
                base = urllib.parse.urlparse(loc)
                for service in root.iter("{urn:schemas-upnp-org:device-1-0}service"):
                    st = service.findtext("d:serviceType", namespaces=ns) or ""
                    if "WANIPConnection" in st or "WANPPPConnection" in st:
                        control = service.findtext("d:controlURL", namespaces=ns) or ""
                        break
                if not control:
                    continue
                url = urllib.parse.urljoin(loc, control)
                body = (
                    '<?xml version="1.0"?>'
                    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                    's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
                    "<s:Body><u:GetExternalIPAddress "
                    'xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1"/>'
                    "</s:Body></s:Envelope>"
                ).encode()
                req2 = urllib.request.Request(
                    url, data=body, method="POST",
                    headers={
                        "Content-Type": 'text/xml; charset="utf-8"',
                        "SOAPAction": '"urn:schemas-upnp-org:service:WANIPConnection:1#GetExternalIPAddress"',
                    },
                )
                with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                    out = resp2.read().decode(errors="ignore")
                for tag in ("NewExternalIPAddress",):
                    start = out.find(f"<{tag}>")
                    end = out.find(f"</{tag}>")
                    if start != -1 and end != -1:
                        return out[start + len(tag) + 2:end].strip()
                # Namespace-prefixed variant.
                import re
                m = re.search(r"NewExternalIPAddress[^>]*>([^<]+)<", out)
                if m:
                    return m.group(1).strip()
            except Exception:
                continue
    except Exception:
        pass
    return None


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


def detect_cgnat_auto() -> bool | None:
    """Best-effort CGNAT check, for the Create Server (listener) page.

    Returns True when CGNAT is found, False when it is confidently
    not CGNAT, and None when it cannot be told. The UI only shows
    the red banner on True, never on None, to avoid false alarms.

    - This PC's own address in 100.64.0.0/10 means it is directly
      on a CGNAT address, no home router in between.
    - A UPnP router WAN address in 100.64.0.0/10 is definitive.
    - A private UPnP WAN address that differs from the STUN public
      address means the router itself is behind another NAT, which
      for a listener is the same failure as CGNAT.
    - A public UPnP WAN address means no CGNAT, only a home NAT,
      where port forwarding can work.
    A public address alone never proves CGNAT, because a CGNAT
    public address looks like any other public address.
    """
    if is_cgnat_ip(local_ip()):
        return True
    wan = upnp_wan_ip()
    if wan:
        if is_cgnat_ip(wan):
            return True
        if not is_private_ip(wan):
            return False
        public = stun_public_ip()
        if public:
            return detect_cgnat(wan, public)
        # Private WAN, public unknown: still not a directly reachable
        # public address, so treat as behind an upstream NAT.
        return True
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
