"""Resume state for interrupted transfers (Section 5).

Two kinds of state, both on disk so a resume survives an app restart:

- A sidecar file next to a receiver's ``name.part``, called
  ``name.part.json``. It records who sent the file, how big it
  is, and its SHA-256, so the receiver can tell whether a .part
  belongs to the file now arriving, or to a different peer, or
  to a file the sender changed since. The offset is never stored:
  it is the .part file's own size.

- A pending list on the sender side, at ``~/.riptide/pending.json``.
  One entry per interrupted transfer, with the peer fingerprint,
  file name, total size, SHA-256, local path, and updated-at time.
  When the same peer reconnects, the sender re-sends the file
  header for each pending transfer, so the resume starts
  automatically.

A .part is deleted when it can no longer be resumed: the peer
changed, it is older than 1 day, the final SHA-256 check failed,
the sender's file changed, or the receiver denied the resume.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

PART_EXPIRY_SECONDS = 24 * 3600  # 1 day
RESUME_DECISION_TIMEOUT = 30.0  # receiver waits this long for the resume card
RESUME_RESPONSE_TIMEOUT = 60.0  # sender waits this long for a resume response


def part_sidecar_path(part: Path) -> Path:
    return Path(part).parent / (Path(part).name + ".json")


def write_part_sidecar(part: Path, peer_fingerprint: str, name: str, size: int, sha256: str) -> None:
    """Write the sidecar for a .part file, atomically."""
    sidecar = {
        "peer_fingerprint": peer_fingerprint,
        "name": name,
        "size": int(size),
        "sha256": sha256,
        "updated_at": time.time(),
    }
    path = part_sidecar_path(part)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(sidecar))
    os.replace(tmp, path)


def read_part_sidecar(part: Path) -> dict | None:
    """Read the sidecar for a .part file, or None when missing or corrupt."""
    try:
        data = json.loads(part_sidecar_path(part).read_text())
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("peer_fingerprint"), str):
        return None
    if not isinstance(data.get("name"), str):
        return None
    if not isinstance(data.get("size"), int):
        return None
    if not isinstance(data.get("sha256"), str):
        return None
    if not isinstance(data.get("updated_at"), (int, float)):
        return None
    return data


def delete_part_and_sidecar(part: Path) -> None:
    for target in (part, part_sidecar_path(part)):
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass


def is_stale_sidecar(sidecar: dict, now: float | None = None) -> bool:
    return (now if now is not None else time.time()) - float(sidecar.get("updated_at", 0)) > PART_EXPIRY_SECONDS


def _pending_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".riptide" / "pending.json"


def load_pending(home: Path | None = None) -> list[dict]:
    """Load the sender's pending interrupted transfers.

    Entries older than 1 day, and entries missing a required
    field, are dropped. A missing or corrupt file is no pending
    transfers, not an error.
    """
    try:
        data = json.loads(_pending_path(home).read_text())
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    now = time.time()
    kept = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if not isinstance(entry.get("peer_fingerprint"), str):
            continue
        if not isinstance(entry.get("name"), str):
            continue
        if not isinstance(entry.get("size"), int):
            continue
        if not isinstance(entry.get("sha256"), str):
            continue
        if not isinstance(entry.get("path"), str):
            continue
        if not isinstance(entry.get("updated_at"), (int, float)):
            continue
        if now - float(entry["updated_at"]) > PART_EXPIRY_SECONDS:
            continue
        kept.append(entry)
    return kept


def _write_pending(home: Path | None, entries: list[dict]) -> None:
    path = _pending_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(entries))
    os.replace(tmp, path)


def save_pending(home: Path | None, entries: list[dict]) -> None:
    _write_pending(home, list(entries))


def _pending_key(entry: dict) -> tuple:
    return (
        entry.get("peer_fingerprint", ""),
        entry.get("name", ""),
        entry.get("size", -1),
        entry.get("sha256", ""),
    )


def add_pending(home: Path | None, entry: dict) -> None:
    """Add or replace a pending transfer, keyed by peer, name, size, and SHA."""
    entries = [e for e in load_pending(home) if _pending_key(e) != _pending_key(entry)]
    entries.append(dict(entry, updated_at=time.time()))
    _write_pending(home, entries)


def remove_pending(home: Path | None, peer_fingerprint: str, name: str, size: int, sha256: str) -> None:
    entries = [
        e
        for e in load_pending(home)
        if _pending_key(e) != (peer_fingerprint, name, size, sha256)
    ]
    _write_pending(home, entries)


def pending_for_peer(home: Path | None, peer_fingerprint: str) -> list[dict]:
    return [e for e in load_pending(home) if e.get("peer_fingerprint") == peer_fingerprint]


def cleanup_parts(cwd: Path, peer_fingerprint: str | None = None, now: float | None = None) -> list[str]:
    """Delete .part files in ``cwd`` that can no longer be resumed.

    Deletes a .part (and its sidecar) when it is stale (older
    than 1 day), and, when a peer fingerprint is given, when its
    sidecar belongs to a different peer, or when it has no sidecar
    at all and so cannot be attributed to a peer. Also deletes
    orphan sidecars whose .part is gone. Returns the names deleted.
    Only the current launch folder is scanned.
    """
    cwd = Path(cwd)
    now = now if now is not None else time.time()
    deleted: list[str] = []
    try:
        entries = list(cwd.iterdir())
    except Exception:
        return deleted
    for path in entries:
        if path.name.endswith(".part.json"):
            part = Path(str(path)[: -len(".json")])
            if not part.exists():
                try:
                    path.unlink()
                    deleted.append(path.name)
                except Exception:
                    pass
            continue
        if not path.name.endswith(".part"):
            continue
        sidecar = read_part_sidecar(path)
        stale = False
        if sidecar is not None:
            stale = is_stale_sidecar(sidecar, now=now)
        else:
            try:
                stale = now - path.stat().st_mtime > PART_EXPIRY_SECONDS
            except Exception:
                stale = False
        wrong_peer = False
        if peer_fingerprint is not None:
            if sidecar is None or sidecar.get("peer_fingerprint") != peer_fingerprint:
                wrong_peer = True
        if stale or wrong_peer:
            delete_part_and_sidecar(path)
            deleted.append(path.name)
    return deleted
