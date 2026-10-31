"""Create Server: the CGNAT side, if one side is CGNAT.

The creator dials the joiner's address. That is the one network
rule that makes CGNAT work: the creator dials out, the joiner
does not dial the creator.

v3: file data goes over SSH/SFTP (port 22). TLS is only for
session establishment and SSH key exchange, with Allow buttons
and no code, no key pasting, no password:
1. Creator dials the joiner's TLS listener, joiner presses Allow,
   both sides exchange SSH public keys over TLS and add each
   other's key to authorized_keys.
2. Creator dials the joiner's SSH server with its riptide key.
   SSH host fingerprint is checked, Allow on first connect,
   abort if it changed.
3. Creator goes to the SSH session screen, where it can Send
   (SFTP upload) and Download (SFTP download) from the joiner.
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ..core.config import Peer, add_peer, load_config
from ..core.focus import focus_first, handle_arrow_key
from ..core.keys import ensure_keypair
from ..core.session import create_session
from ..core.ssh_client import RiptideSSH, UnknownHostError, parse_peer
from ..theme import HEADER_LINES


class CreateScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.config = load_config()
        self._approve_event = threading.Event()
        self._approved = False

    def compose(self) -> ComposeResult:
        known = ", ".join(p.label() for p in self.config.peers) or "No saved peers yet."
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static("CREATE SERVER", classes="accent"),
            Static(f"Known peers: {known}", classes="dim"),
            Static("Enter the joiner as user@host. This is the public side.", classes="dim"),
            Input(placeholder="Joiner: user@host", id="host"),
            Static("Status: idle", id="status"),
            Static("", id="fingerprint"),
            Button("Create", id="create"),
            Button("Allow", id="allow"),
            Button("Deny", id="deny"),
            Button("Back", id="back"),
            Static("You dial out, so this works from behind CGNAT. File data goes over SSH. No code to type.", classes="dim"),
        )

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(f"Status: {text}")
        except Exception:
            pass

    def _approve(self, fingerprint: str) -> bool:
        self._approved = False
        self._approve_event.clear()
        try:
            self.app.call_from_thread(self.query_one("#fingerprint", Static).update, f"Fingerprint: {fingerprint[:64]}... Allow to trust?")
        except Exception:
            pass
        self._approve_event.wait(timeout=120)
        return self._approved

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "host":
            self._start()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self._start()
        elif event.button.id == "allow":
            self._approved = True
            self._approve_event.set()
        elif event.button.id == "deny":
            self._approved = False
            self._approve_event.set()
        elif event.button.id == "back":
            self.app.pop_screen()

    def _start(self) -> None:
        try:
            text = self.query_one("#host", Input).value.strip()
        except Exception:
            text = ""
        if not text:
            self._set_status("Failed: enter the joiner as user@host first.")
            return
        self._set_status(f"Dialling {text}...")
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _worker(self, text: str) -> None:
        try:
            user, host = parse_peer(text)
            known = self.config.peer_for(host)
            known_fp = known.fingerprint if known else ""
            known_ssh_fp = known.ssh_fingerprint if known else ""
            self.app.call_from_thread(self._set_status, "Step 1: TLS session + SSH key exchange...")
            tls = create_session(
                host, self.config.session_port, self.cwd, device=socket.gethostname(),
                known_fingerprint=known_fp, approve_fingerprint=None if known_fp else self._approve,
                exchange_ssh_keys=True,
            )
            if known is None:
                add_peer(self.config, Peer(name=host, user=user, host=host, fingerprint=getattr(tls, "peer_fingerprint", "")))
                known = self.config.peer_for(host)
            self.app.call_from_thread(self._set_status, "Step 2: SSH to joiner...")
            private, _public = ensure_keypair()
            ssh = RiptideSSH(user, host, port=22, key_path=private, known_fingerprint=known_ssh_fp)
            try:
                ssh.connect(on_stage=lambda m: self.app.call_from_thread(self._set_status, m), allow_new_host=bool(known_ssh_fp))
            except UnknownHostError:
                if self._approve(ssh.fingerprint):
                    ssh.connect(on_stage=lambda m: self.app.call_from_thread(self._set_status, m), allow_new_host=True)
                else:
                    raise ConnectionError("SSH host fingerprint denied")
            if known is not None and ssh.fingerprint:
                known.ssh_fingerprint = ssh.fingerprint
                from ..core.config import save_config
                save_config(self.config)
            sftp = ssh.open_sftp()
            self.app.call_from_thread(self._set_status, "SSH session live, opening...")
            from .ssh_session import SSHSessionScreen
            self.app.call_from_thread(self.app.push_screen, SSHSessionScreen(tls, "creator", ssh=ssh.client, sftp=sftp))
        except Exception as exc:
            self.app.call_from_thread(self._set_status, f"Failed: {exc}")

    def on_mount(self) -> None:
        focus_first(self)

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
            return
        if handle_arrow_key(self, event.key):
            event.stop()
