"""Saved connections and settings.

Location is always Path.home() / ".riptide" / "config.toml", on every OS.
Private keys are never stored here. If a value looks like a private key,
saving it is refused.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11, not supported by pyproject
    import tomli as tomllib  # type: ignore

# Standard SSH port. Kept in code/config only; the UI never renders it.
DEFAULT_SSH_PORT = 22
# Internal pairing listener port. Also never rendered in the UI.
DEFAULT_PAIRING_PORT = 49871


def config_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".riptide"


def config_path(home: Path | None = None) -> Path:
    return config_dir(home) / "config.toml"


@dataclass
class Peer:
    name: str
    user: str
    host: str
    fingerprint: str = ""
    allow_always: bool = False

    def label(self) -> str:
        return f"{self.user}@{self.host}"


@dataclass
class Config:
    peers: list[Peer] = field(default_factory=list)
    ssh_port: int = DEFAULT_SSH_PORT
    pairing_port: int = DEFAULT_PAIRING_PORT

    def peer_for(self, user: str, host: str) -> Peer | None:
        for peer in self.peers:
            if peer.user == user and peer.host == host:
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
            allow_always=bool(item.get("allow_always", False)),
        ))
    ssh_port = data.get("ssh_port", DEFAULT_SSH_PORT)
    pairing_port = data.get("pairing_port", DEFAULT_PAIRING_PORT)
    try:
        ssh_port = int(ssh_port)
    except Exception:
        ssh_port = DEFAULT_SSH_PORT
    try:
        pairing_port = int(pairing_port)
    except Exception:
        pairing_port = DEFAULT_PAIRING_PORT
    return Config(peers=peers, ssh_port=ssh_port, pairing_port=pairing_port)


def save_config(config: Config, home: Path | None = None) -> Path:
    for peer in config.peers:
        for value in (peer.name, peer.user, peer.host, peer.fingerprint):
            if _contains_private_key(value):
                raise ValueError("refusing to store a private key in config")
    directory = config_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f'ssh_port = {int(config.ssh_port)}', f'pairing_port = {int(config.pairing_port)}', ""]
    for peer in config.peers:
        lines.append("[[peer]]")
        lines.append(f'name = "{_escape(peer.name)}"')
        lines.append(f'user = "{_escape(peer.user)}"')
        lines.append(f'host = "{_escape(peer.host)}"')
        lines.append(f'fingerprint = "{_escape(peer.fingerprint)}"')
        lines.append(f'allow_always = {"true" if peer.allow_always else "false"}')
        lines.append("")
    path = config_path(home)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def add_peer(config: Config, peer: Peer, home: Path | None = None) -> Config:
    existing = config.peer_for(peer.user, peer.host)
    if existing is not None:
        existing.name = peer.name or existing.name
        existing.fingerprint = peer.fingerprint or existing.fingerprint
        existing.allow_always = peer.allow_always or existing.allow_always
    else:
        config.peers.append(peer)
    save_config(config, home=home)
    return config
