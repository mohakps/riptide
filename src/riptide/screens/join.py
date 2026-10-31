"""Join Server, redesigned for clarity and user-friendliness.

Waits for an incoming connection from the creator.
- Omits unnecessary/redundant text.
- Prominently highlights the incoming connection request in a dedicated card.
- Enter key to accept the connection, Backspace to deny.
- Blocks up/down arrow keys.
- Buttons (Accept/Deny) are equal sized with green/red backgrounds.
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
from ..core.session import JoinListener


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
                    Static(f"Port: {self.config.session_port}", id="peer_client_label"),
                    Static("[#E8E8E8]Listening[/] [bold #FFD166]○[/]", id="peer_status_label"),
                    id="session_peer_info",
                ),
                id="session_header_row",
            ),
            Vertical(
                Static(
                    f"[dim]○[/] [bold #E8E8E8]Waiting for creator on port {self.config.session_port}...[/]\n\n"
                    f"[dim]Share your IP or hostname with the creator to initiate connection.[/]",
                    id="incoming",
                ),
                Horizontal(
                    Button("Accept", id="allow", classes="allow"),
                    Button("Deny", id="deny", classes="deny"),
                    id="join_actions",
                ),
                id="incoming_card",
            ),
            id="session_scroll",
            can_focus=False,
        )
        yield Horizontal(
            Label(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Accept[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E8E8E8]\[Backspace][/] [dim #FFFFFF]Deny[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Space][/] [dim #FFFFFF]Select[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Esc][/] [dim #FFFFFF]Back[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
        )

    def _set_allow_visible(self, visible: bool) -> None:
        try:
            actions = self.query_one("#join_actions", Horizontal)
            actions.styles.display = "block" if visible else "none"
        except Exception:
            pass
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

    def _show_incoming_connection(self, device: str, fingerprint: str) -> None:
        try:
            card = self.query_one("#incoming_card", Vertical)
            card.add_class("active")
            fp_text = f"\n[dim]Fingerprint: {fingerprint[:32]}...[/]" if fingerprint else ""
            msg = (
                f"[bold #78DC8C]● INCOMING CONNECTION REQUEST[/]\n\n"
                f"Peer Device: [bold #FFFFFF]{device}[/]{fp_text}\n\n"
                f"[#E8E8E8]Accept connection from this peer?[/]"
            )
            self.query_one("#incoming", Static).update(msg)
            self._set_allow_visible(True)
            if self._allow_btn is not None:
                self._allow_btn.focus()
        except Exception:
            pass

    def _reset_incoming_card(self) -> None:
        try:
            card = self.query_one("#incoming_card", Vertical)
            card.remove_class("active")
            self._set_allow_visible(False)
        except Exception:
            pass

    def _approve(self, device: str, fingerprint: str) -> bool:
        self._pending = (device, fingerprint)
        self._approved = False
        self._awaiting_approval = True
        self._approve_event.clear()
        try:
            self.app.call_from_thread(self._show_incoming_connection, device, fingerprint)
        except Exception:
            pass
        self._approve_event.wait(timeout=300)
        self._awaiting_approval = False
        try:
            self.app.call_from_thread(self._reset_incoming_card)
        except Exception:
            pass
        return self._approved

    def _handle_button_id(self, bid: str) -> bool:
        if bid == "allow":
            self._approved = True
            self._approve_event.set()
            self._reset_incoming_card()
            return True
        if bid == "deny":
            self._approved = False
            self._approve_event.set()
            self._reset_incoming_card()
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
            self.app.call_from_thread(self._set_status, "[bold #78DC8C]Connection accepted! Opening session...[/]")
            from .session_screen import SessionScreen
            self.app.call_from_thread(self.app.push_screen, SessionScreen(session, "joiner"))
        except Exception as exc:
            try:
                self.app.call_from_thread(self._set_status, f"[bold #FF6B6B]Failed: {exc}[/]")
            except Exception:
                pass

    async def on_key(self, event) -> None:
        if event.key == "escape":
            if self._listener is not None:
                self._listener.stop()
            self.app.pop_screen()
            return

        # Up/down arrow keys are blocked
        if event.key in ("up", "down"):
            event.stop()
            return

        # Backspace: deny connection
        if event.key == "backspace" and self._awaiting_approval:
            event.stop()
            self._handle_button_id("deny")
            return

        # Enter: accept connection
        if event.key == "enter" and self._awaiting_approval:
            event.stop()
            self._handle_button_id("allow")
            return

        # Space: activate focused button, or accept if awaiting
        if event.key == "space":
            focused = self.focused
            if isinstance(focused, Button):
                event.stop()
                self._handle_button_id(focused.id or "")
                return
            if self._awaiting_approval:
                event.stop()
                self._handle_button_id("allow")
                return

        # Left / Right / Tab to switch focus between Accept and Deny buttons
        if event.key in ("left", "right", "tab"):
            event.stop()
            if self._awaiting_approval:
                if self.focused == self._deny_btn and self._allow_btn is not None:
                    self._allow_btn.focus()
                elif self._allow_btn is not None and self._deny_btn is not None:
                    if self.focused == self._allow_btn:
                        self._deny_btn.focus()
                    else:
                        self._allow_btn.focus()
            return
