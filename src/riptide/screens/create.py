"""Create Server, v4 TLS rollback.

The creator dials the joiner. That is the one network rule that
makes CGNAT work: the creator dials out, the joiner does not
dial the creator. After the session is live, either side can
send or download, over TLS.

Fixes in v4:
- Allow/Deny are hidden until a fingerprint actually needs
  approval, then hidden again after the decision. They are
  not always visible.
- Past hostnames are buttons: pressing one fills the address
  input, so the creator does not retype a known host.
- The address input accepts a hostname, an IPv4 address, an
  IPv6 address (with or without brackets), or user@host.
  See core.session.parse_host_input.
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ..core.config import Peer, add_peer, load_config
from ..core.focus import focus_first, handle_arrow_key
from ..core.session import create_session, parse_host_input
from ..theme import HEADER_LINES, TAGLINES

class CreateScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.config = load_config()
        self._approve_event = threading.Event()
        self._approved = False
        self._awaiting_approval = False
        self._allow_btn: Button | None = None
        self._deny_btn: Button | None = None

    def compose(self) -> ComposeResult:
        peers = [Button(p.host, id=f"peer_{i}") for i, p in enumerate(self.config.peers) if p.host]
        yield Vertical(
            Static("CREATE SERVER", classes="screen-title"),
            Static(TAGLINES["create"], classes="screen-desc"),
            Static("Recent peers · select to autofill destination:", classes="dim") if peers else Static(""),
            Horizontal(*peers) if peers else Static(""),
            Input(placeholder="Joiner address: hostname, IPv4, or IPv6", id="host"),
            Static("Status: idle", id="status"),
            Static("", id="fingerprint"),
            Button("Create Server", id="create", classes="primary"),
            Button("Allow", id="allow", classes="allow"),
            Button("Deny", id="deny", classes="deny"),
            Static("[Space] Select   [Enter] Create / Allow   [Backspace] Deny   [Esc] Back", classes="keymap-bar"),
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
            self.query_one("#status", Static).update(f"Status: {text}")
        except Exception:
            pass

    def _approve(self, fingerprint: str) -> bool:
        self._approved = False
        self._awaiting_approval = True
        self._approve_event.clear()
        try:
            self.app.call_from_thread(self.query_one("#fingerprint", Static).update, f"Fingerprint: {fingerprint[:32]}... Allow to trust this joiner?")
            self.app.call_from_thread(self._set_allow_visible, True)
        except Exception:
            pass
        self._approve_event.wait(timeout=120)
        self._awaiting_approval = False
        try:
            self.app.call_from_thread(self._set_allow_visible, False)
        except Exception:
            pass
        return self._approved

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "host":
            self._start()

    def _handle_button_id(self, bid: str) -> bool:
        if bid.startswith("peer_"):
            try:
                idx = int(bid.split("_", 1)[1])
                host = self.config.peers[idx].host
                self.query_one("#host", Input).value = host
                self._set_status(f"Selected past host: {host}")
            except Exception:
                pass
            return True
        if bid == "create":
            self._start()
            return True
        if bid == "allow":
            self._approved = True
            self._approve_event.set()
            self._set_allow_visible(False)
            return True
        if bid == "deny":
            self._approved = False
            self._approve_event.set()
            self._set_allow_visible(False)
            return True
        if bid == "back":
            self.app.pop_screen()
            return True
        return False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._handle_button_id(event.button.id or "")

    def _start(self) -> None:
        try:
            text = self.query_one("#host", Input).value.strip()
        except Exception:
            text = ""
        if not text:
            self._set_status("Failed: enter the joiner's address first.")
            return
        try:
            host = parse_host_input(text)
        except Exception as exc:
            self._set_status(f"Failed: {exc}")
            return
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
        try:
            self._allow_btn = self.query_one("#allow", Button)
            self._deny_btn = self.query_one("#deny", Button)
        except Exception:
            pass
        self._set_allow_visible(False)
        try:
            self.query_one("#host", Input).focus()
        except Exception:
            focus_first(self)

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
            return
        focused = self.focused
        # Backspace: deny, when a fingerprint is waiting, and the
        # host input is not focused (there, Backspace deletes text).
        if event.key == "backspace" and self._awaiting_approval and not isinstance(focused, Input):
            event.stop()
            self._handle_button_id("deny")
            return
        # Enter: allow, when a fingerprint is waiting and the user
        # is not already on a button (which activates itself).
        if event.key == "enter" and self._awaiting_approval and not isinstance(focused, Button):
            event.stop()
            self._handle_button_id("allow")
            return
        # Space: select the focused button. In the host input, let
        # Space type normally.
        if event.key == "space" and isinstance(focused, Button):
            event.stop()
            self._handle_button_id(focused.id or "")
            return
        if handle_arrow_key(self, event.key):
            event.stop()
