"""Join Server, redesigned to match the file transfer page.

The joiner does not dial the creator, because the creator may
be behind CGNAT and unreachable. The joiner waits, the creator
dials in, and the joiner presses Allow to accept the session.

Design language, shared with the session screen:
- VerticalScroll page, plain bold header text (not block art),
  dim description, generous blank space between sections,
  and a docked footer bar with keys in brackets.
- Allow/Deny are hidden until an incoming session actually
  arrives, then hidden again after the decision. They are
  not visible before an incoming request.

Keys, shared with Create:
- Space: select the focused button, or focus Allow when a
  session is waiting and no button is focused.
- Enter: allow, when a session is waiting.
- Backspace: deny, when a session is waiting.
- Esc: back.
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Label, Static

from ..core.config import Peer, add_peer, load_config
from ..core.focus import focus_first, handle_arrow_key
from ..core.session import JoinListener
from ..theme import TAGLINES


class JoinScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.config = load_config()
        self._pending: tuple[str, str] | None = None
        self._approve_event = threading.Event()
        self._approved = False
        self._awaiting_approval = False
        self._listener: JoinListener | None = None
        self._allow_btn: Button | None = None
        self._deny_btn: Button | None = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(
            Horizontal(
                Static("JOIN SERVER", classes="session-header-text", id="session_host_title"),
                Vertical(
                    Static("Waiting for creator", classes="dim"),
                    Static("Keep this screen open", classes="dim"),
                    id="session_peer_info",
                ),
                id="session_header_row",
            ),
            Static(""),
            Static(TAGLINES["join"], classes="screen-desc"),
            Static(""),
            Static("Waiting for a creator. Keep this screen open.", classes="success"),
            Static(""),
            Static("Share your address with the creator. They dial you, you do not dial them.", classes="dim"),
            Static(""),
            Static("No incoming session yet.", id="incoming"),
            Static(""),
            Static("", id="fingerprint"),
            Static(""),
            Horizontal(
                Button("Allow", id="allow", classes="allow"),
                Button("Deny", id="deny", classes="deny"),
                id="join_actions",
            ),
            Static(""),
            id="session_scroll",
            can_focus=False,
        )
        yield Horizontal(
            Label(r"[bold #E8E8E8]\[Space][/] [dim]Select[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E8E8E8]\[Enter][/] [dim]Allow[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Backspace][/] [dim]Deny[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Esc][/] [dim]Back[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
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
        self._awaiting_approval = True
        self._approve_event.clear()
        try:
            self.app.call_from_thread(self.query_one("#incoming", Static).update, f"Incoming session from: {device}. Allow to join?")
            if fingerprint:
                self.app.call_from_thread(self.query_one("#fingerprint", Static).update, f"Fingerprint: {fingerprint[:32]}...")
            self.app.call_from_thread(self._set_allow_visible, True)
        except Exception:
            pass
        self._approve_event.wait(timeout=300)
        self._awaiting_approval = False
        try:
            self.app.call_from_thread(self._set_allow_visible, False)
        except Exception:
            pass
        return self._approved

    def _handle_button_id(self, bid: str) -> bool:
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
            if self._listener is not None:
                self._listener.stop()
            self.app.pop_screen()
            return True
        return False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._handle_button_id(event.button.id or "")

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
            try:
                self.app.call_from_thread(self._set_status, f"Failed: {exc}")
            except Exception:
                pass

    async def on_key(self, event) -> None:
        if event.key == "escape":
            if self._listener is not None:
                self._listener.stop()
            self.app.pop_screen()
            return
        # Backspace: deny, when a session is waiting.
        if event.key == "backspace" and self._awaiting_approval:
            event.stop()
            self._handle_button_id("deny")
            return
        # Enter: allow, when a session is waiting, unless the user
        # is on Deny (which activates itself as a deny).
        if event.key == "enter" and self._awaiting_approval and not (isinstance(self.focused, Button) and self.focused.id == "deny"):
            event.stop()
            self._handle_button_id("allow")
            return
        # Space: select the focused button, or focus Allow when waiting.
        if event.key == "space":
            focused = self.focused
            if isinstance(focused, Button):
                event.stop()
                self._handle_button_id(focused.id or "")
                return
            if self._awaiting_approval and self._allow_btn is not None:
                event.stop()
                try:
                    self._allow_btn.focus()
                except Exception:
                    pass
                return
        if handle_arrow_key(self, event.key):
            event.stop()
