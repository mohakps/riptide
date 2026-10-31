"""Saved connections and settings, v2.

Location is always Path.home() / ".riptide" / "config.toml", on every OS.
Private keys and certificates are never stored here. A peer is identified
by host + TLS certificate fingerprint, approved in the UI on first connect.
Pairing codes are gone in v2; there is no pairing port.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11, not supported by pyproject
    import tomli as tomllib  # type: ignore

# Internal session port. Kept in code/config only; the UI never renders it.
DEFAULT_SESSION_PORT = 49872
# Standard SSH port, for file data in v3. Also never rendered in the UI.
DEFAULT_SSH_PORT = 22


def config_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".riptide"


def config_path(home: Path | None = None) -> Path:
    return config_dir(home) / "config.toml"


@dataclass
class Peer:
    name: str
    user: str = ""
    host: str = ""
    fingerprint: str = ""
    ssh_fingerprint: str = ""
    allow_always: bool = False

    def label(self) -> str:
        return self.host or self.name


@dataclass
class Config:
    peers: list[Peer] = field(default_factory=list)
    session_port: int = DEFAULT_SESSION_PORT

    def peer_for(self, host: str, user: str = "") -> Peer | None:
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
            user=str(item.get("user", "")),
            host=str(item.get("host", "")),
            fingerprint=str(item.get("fingerprint", "")),
            ssh_fingerprint=str(item.get("ssh_fingerprint", "")),
            allow_always=bool(item.get("allow_always", False)),
        ))
    session_port = data.get("session_port", DEFAULT_SESSION_PORT)
    try:
        session_port = int(session_port)
    except Exception:
        session_port = DEFAULT_SESSION_PORT
    return Config(peers=peers, session_port=session_port)


def save_config(config: Config, home: Path | None = None) -> Path:
    for peer in config.peers:
        for value in (peer.name, peer.user, peer.host, peer.fingerprint):
            if _contains_private_key(value):
                raise ValueError("refusing to store a private key in config")
    directory = config_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f"session_port = {int(config.session_port)}", ""]
    for peer in config.peers:
        lines.append("[[peer]]")
        lines.append(f'name = "{_escape(peer.name)}"')
        lines.append(f'user = "{_escape(peer.user)}"')
        lines.append(f'host = "{_escape(peer.host)}"')
        lines.append(f'fingerprint = "{_escape(peer.fingerprint)}"')
        lines.append(f'ssh_fingerprint = "{_escape(peer.ssh_fingerprint)}"')
        lines.append(f'allow_always = {"true" if peer.allow_always else "false"}')
        lines.append("")
    path = config_path(home)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def add_peer(config: Config, peer: Peer, home: Path | None = None) -> Config:
    existing = config.peer_for(peer.host) if peer.host else None
    if existing is not None:
        existing.name = peer.name or existing.name
        existing.fingerprint = peer.fingerprint or existing.fingerprint
        existing.allow_always = peer.allow_always or existing.allow_always
    else:
        config.peers.append(peer)
    save_config(config, home=home)
    return config
