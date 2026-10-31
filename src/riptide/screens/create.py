"""Create Server: the CGNAT side, if one side is CGNAT.

The creator dials the joiner's address. That is the one network
rule that makes CGNAT work: the creator dials out, the joiner
does not dial the creator. After the session is live, either
side can send or download.
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
from ..core.session import create_session
from ..theme import HEADER_LINES


class CreateScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.config = load_config()
        self._pending_fp: str | None = None
        self._approve_event = threading.Event()
        self._approved = False
        self._host = ""

    def compose(self) -> ComposeResult:
        known = ", ".join(p.label() for p in self.config.peers) or "No saved peers yet."
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static("CREATE SERVER", classes="accent"),
            Static(f"Known peers: {known}", classes="dim"),
            Static("Enter the joiner's address. This is the public side's address.", classes="dim"),
            Input(placeholder="Joiner address", id="host"),
            Static("Status: idle", id="status"),
            Static("", id="fingerprint"),
            Button("Create", id="create"),
            Button("Allow", id="allow"),
            Button("Deny", id="deny"),
            Button("Back", id="back"),
            Static("You dial out, so this works from behind CGNAT. No code to type.", classes="dim"),
        )

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(f"Status: {text}")
        except Exception:
            pass

    def _approve(self, fingerprint: str) -> bool:
        # Called in the dial thread. Show the fingerprint in the UI
        # and wait for the Allow / Deny buttons.
        self._pending_fp = fingerprint
        self._approved = False
        self._approve_event.clear()
        try:
            self.app.call_from_thread(self.query_one("#fingerprint", Static).update, f"Fingerprint: {fingerprint[:32]}... Allow to trust this joiner?")
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
            host = self.query_one("#host", Input).value.strip()
        except Exception:
            host = ""
        if not host:
            self._set_status("Failed: enter the joiner's address first.")
            return
        self._host = host
        self._set_status(f"Dialling {host}...")
        threading.Thread(target=self._worker, args=(host,), daemon=True).start()

    def _worker(self, host: str) -> None:
        try:
            known = self.config.peer_for(host)
            known_fp = known.fingerprint if known else ""
            session = create_session(
                host, self.config.session_port, self.cwd, device=socket.gethostname(),
                known_fingerprint=known_fp, approve_fingerprint=None if known_fp else self._approve,
            )
            if known is None and getattr(session, "peer_fingerprint", ""):
                add_peer(self.config, Peer(name=host, host=host, fingerprint=session.peer_fingerprint))
            self.app.call_from_thread(self._set_status, "Session live, opening...")
            from .session_screen import SessionScreen

            self.app.call_from_thread(self.app.push_screen, SessionScreen(session, "creator"))
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
