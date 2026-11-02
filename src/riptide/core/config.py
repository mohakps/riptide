"""Saved connections and settings.

Location is always Path.home() / ".riptide" / "config.toml", on every OS.
Private keys and certificates are never stored here. A peer is identified
by host + TLS certificate fingerprint, approved in the UI on first connect.
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
    session_port: int = DEFAULT_SESSION_PORT
    firewall_port_open: bool | None = None
    def peer_for(self, host: str) -> Peer | None:
        for peer in self.peers:
            if peer.host == host:
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
    session_port = data.get("session_port", DEFAULT_SESSION_PORT)
    try:
        session_port = int(session_port)
    except Exception:
        session_port = DEFAULT_SESSION_PORT
    firewall_val = data.get("firewall_port_open")
    firewall_port_open = bool(firewall_val) if firewall_val is not None else None
    return Config(peers=peers, session_port=session_port, firewall_port_open=firewall_port_open)


def save_config(config: Config, home: Path | None = None) -> Path:
    for peer in config.peers:
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
