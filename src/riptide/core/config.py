"""Saved connections and settings.

Location is always Path.home() / ".riptide" / "config.toml", on every OS.
Private keys and certificates are never stored here. A peer is identified
by host + TLS certificate fingerprint, approved in the UI on first connect.

Since v1.1, the host side also keeps trusted clients, separate from
dial-out peers. A trusted client is identified by fingerprint, with
the device name as a display label only. The dial-out peer list is
keyed by host, for filling the Join address, while the trusted
client list is keyed by fingerprint, for host-side authentication.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11, not supported by pyproject
    import tomli as tomllib  # type: ignore

# Session port. Kept in code/config only, except for the
# Create/Join header and waiting text.
# 50000 is in the dynamic/private range (49152-65535), so it is not
# IANA-reserved, but it is the de facto default for IBM DB2, Jenkins
# agents, and SAP NetWeaver Java, so a machine running one of those
# will already have it in use and Riptide will fail to bind.
DEFAULT_SESSION_PORT = 50000


def config_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".riptide"


def config_path(home: Path | None = None) -> Path:
    return config_dir(home) / "config.toml"


@dataclass
class Peer:
    name: str
    host: str = ""
    fingerprint: str = ""


@dataclass
class Config:
    peers: list[Peer] = field(default_factory=list)
    trusted_clients: list[Peer] = field(default_factory=list)
    session_port: int = DEFAULT_SESSION_PORT
    firewall_port_open: bool | None = None
    def peer_for(self, host: str) -> Peer | None:
        for peer in self.peers:
            if peer.host == host:
                return peer
        return None
    def trusted_client_for_fingerprint(self, fingerprint: str) -> Peer | None:
        for peer in self.trusted_clients:
            if peer.fingerprint and peer.fingerprint == fingerprint:
                return peer
        return None
    def trusted_client_for_device(self, device: str) -> Peer | None:
        for peer in self.trusted_clients:
            if peer.name and peer.name == device:
                return peer
        return None


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _contains_private_key(text: str) -> bool:
    return "PRIVATE KEY" in text or "-----BEGIN" in text


def load_config(home: Path | None = None) -> Config:
    path = config_path(home)
    if not path.exists():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return Config()
    peers = []
    for item in data.get("peer", []) if isinstance(data.get("peer", []), list) else []:
        if not isinstance(item, dict):
            continue
        peers.append(Peer(
            name=str(item.get("name", "")),
            host=str(item.get("host", "")),
            fingerprint=str(item.get("fingerprint", "")),
        ))
    trusted_clients = []
    for item in data.get("trusted_client", []) if isinstance(data.get("trusted_client", []), list) else []:
        if not isinstance(item, dict):
            continue
        trusted_clients.append(Peer(
            name=str(item.get("name", "")),
            host=str(item.get("host", "")),
            fingerprint=str(item.get("fingerprint", "")),
        ))
    session_port = data.get("session_port", DEFAULT_SESSION_PORT)
    try:
        session_port = int(session_port)
    except Exception:
        session_port = DEFAULT_SESSION_PORT
    firewall_val = data.get("firewall_port_open")
    firewall_port_open = bool(firewall_val) if firewall_val is not None else None
    return Config(peers=peers, trusted_clients=trusted_clients, session_port=session_port, firewall_port_open=firewall_port_open)


def save_config(config: Config, home: Path | None = None) -> Path:
    for peer in list(config.peers) + list(config.trusted_clients):
        for value in (peer.name, peer.host, peer.fingerprint):
            if _contains_private_key(value):
                raise ValueError("refusing to store a private key in config")
    directory = config_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f"session_port = {int(config.session_port)}"]
    if config.firewall_port_open is not None:
        lines.append(f"firewall_port_open = {'true' if config.firewall_port_open else 'false'}")
    lines.append("")
    for peer in config.peers:
        lines.append("[[peer]]")
        lines.append(f'name = "{_escape(peer.name)}"')
        lines.append(f'host = "{_escape(peer.host)}"')
        lines.append(f'fingerprint = "{_escape(peer.fingerprint)}"')
        lines.append("")
    for peer in config.trusted_clients:
        lines.append("[[trusted_client]]")
        lines.append(f'name = "{_escape(peer.name)}"')
        lines.append(f'host = "{_escape(peer.host)}"')
        lines.append(f'fingerprint = "{_escape(peer.fingerprint)}"')
        lines.append("")
    path = config_path(home)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def add_peer(config: Config, peer: Peer, home: Path | None = None) -> Config:
    existing = config.peer_for(peer.host) if peer.host else None
    if existing is not None:
        existing.name = peer.name or existing.name
        existing.fingerprint = peer.fingerprint or existing.fingerprint
    else:
        config.peers.append(peer)
    save_config(config, home=home)
    return config


def add_trusted_client(config: Config, peer: Peer, home: Path | None = None) -> Config:
    """Save a host-side trusted client, keyed by fingerprint.

    If the fingerprint is already trusted, update its label.
    If the device label is already trusted with a different
    fingerprint, replace that fingerprint, which is the explicit
    Replace flow after a changed-fingerprint warning. Otherwise
    append a new trusted client.
    """
    if peer.fingerprint:
        existing = config.trusted_client_for_fingerprint(peer.fingerprint)
        if existing is not None:
            existing.name = peer.name or existing.name
            save_config(config, home=home)
            return config
    if peer.name:
        by_device = config.trusted_client_for_device(peer.name)
        if by_device is not None:
            by_device.fingerprint = peer.fingerprint
            save_config(config, home=home)
            return config
    config.trusted_clients.append(peer)
    save_config(config, home=home)
    return config
