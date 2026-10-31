"""Join Server, v4 TLS rollback.

The joiner does not dial the creator, because the creator may
be behind CGNAT and unreachable. The joiner waits, the creator
dials in, and the joiner presses Allow to accept the session.

Fix in v4: Allow/Deny are hidden until an incoming session
actually arrives, then hidden again after the decision. They
are not visible before an incoming request.
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..core.config import Peer, add_peer, load_config
from ..core.focus import focus_first, handle_arrow_key
from ..core.session import JoinListener
from ..theme import HEADER_LINES, TAGLINES


class JoinScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.config = load_config()
        self._pending: tuple[str, str] | None = None
        self._approve_event = threading.Event()
        self._approved = False
        self._listener: JoinListener | None = None
        self._allow_btn: Button | None = None
        self._deny_btn: Button | None = None

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("JOIN SERVER", classes="screen-title"),
            Static(TAGLINES["join"], classes="screen-desc"),
            Static("Waiting for a creator. Keep this screen open.", classes="success"),
            Static("Share your address with the creator. They dial you, you do not dial them.", classes="dim"),
            Static("No incoming session yet.", id="incoming"),
            Static("", id="fingerprint"),
            Button("Allow", id="allow", classes="allow"),
            Button("Deny", id="deny", classes="deny"),
            Static("[Esc] Back", classes="keymap-bar"),
        )

    def _set_allow_visible(self, visible: bool) -> None:
        for btn in (self._allow_btn, self._deny_btn):
            if btn is not None:
                try:
                    btn.styles.display = "block" if visible else "none"
                except Exception:
                    pass

    def _set_status(self, text: str) -> None:
        try:
            self.query_one("#incoming", Static).update(text)
        except Exception:
            pass

    def _approve(self, device: str, fingerprint: str) -> bool:
        self._pending = (device, fingerprint)
        self._approved = False
        self._approve_event.clear()
        try:
            self.app.call_from_thread(self.query_one("#incoming", Static).update, f"Incoming session from: {device}. Allow to join?")
            if fingerprint:
                self.app.call_from_thread(self.query_one("#fingerprint", Static).update, f"Fingerprint: {fingerprint[:32]}...")
            self.app.call_from_thread(self._set_allow_visible, True)
        except Exception:
            pass
        self._approve_event.wait(timeout=300)
        try:
            self.app.call_from_thread(self._set_allow_visible, False)
        except Exception:
            pass
        return self._approved

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "allow":
            self._approved = True
            self._approve_event.set()
            self._set_allow_visible(False)
        elif event.button.id == "deny":
            self._approved = False
            self._approve_event.set()
            self._set_allow_visible(False)
        elif event.button.id == "back":
            if self._listener is not None:
                self._listener.stop()
            self.app.pop_screen()

    def on_mount(self) -> None:
        try:
            self._allow_btn = self.query_one("#allow", Button)
            self._deny_btn = self.query_one("#deny", Button)
        except Exception:
            pass
        self._set_allow_visible(False)
        focus_first(self)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            self._listener = JoinListener(
                self.config.session_port, self.cwd, device=socket.gethostname(),
                approve=self._approve,
            )
            session = self._listener.wait_for_creator()
            if self._pending is not None:
                device, fp = self._pending
                if self.config.peer_for(device) is None:
                    add_peer(self.config, Peer(name=device, host=device, fingerprint=fp))
            self.app.call_from_thread(self._set_status, "Session live, opening...")
            from .session_screen import SessionScreen
            self.app.call_from_thread(self.app.push_screen, SessionScreen(session, "joiner"))
        except Exception as exc:
            self.app.call_from_thread(self._set_status, f"Failed: {exc}")

    async def on_key(self, event) -> None:
        if event.key == "escape":
            if self._listener is not None:
                self._listener.stop()
            self.app.pop_screen()
            return
        if handle_arrow_key(self, event.key):
            event.stop()
