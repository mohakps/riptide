"""Join Server screen (dialler), redesigned for clarity, usability, and clean keyboard workflow.

NOTE: the class is still called CreateScreen for historical reasons.
After the name swap, this dial-out page is shown as "Join Server"
in the UI, and the listener page is shown as "Create Server".
Functionality is unchanged, only the displayed name swapped.


- Omit unnecessary text; highlight important headers and active selection.
- Saved devices rendered as an unordered list instead of buttons.
- Default selection: first saved device (index 0).
- Up/Down arrow keys navigate between saved devices.
- Grey font color by default (#71717A), red for the focused device (#FF6B6B).
- Hostname input positioned at 3/4 vertically and centered horizontally.
- Tab cycles between saved devices and the hostname input field.
- Enter connects with the selected device / entered hostname.
- Saved devices are unhighlighted (all grey) whenever the hostname input is focused.
- Modern docked footer with clear shortcut keys.
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from ..core.config import Peer, add_peer, load_config
from ..core.focus import focus_first
from ..core.session import create_session, parse_host_input
from ..theme import BANNER_JOIN


class SavedDevicesList(Vertical):
    """Focusable unordered list of saved peers."""

    can_focus = True

    def __init__(self, peers: list[Peer], **kwargs) -> None:
        super().__init__(**kwargs)
        self.peers = peers
        self.selected_index = 0 if peers else -1

    def compose(self) -> ComposeResult:
        for i, peer in enumerate(self.peers):
            text = peer.name if peer.name and peer.name != peer.host else peer.host
            yield Static(f"• {text}", id=f"device_item_{i}", classes="device-item")

    @property
    def selected_device(self) -> Peer | None:
        if 0 <= self.selected_index < len(self.peers):
            return self.peers[self.selected_index]
        return None

    def _on_focus(self, event: events.Focus) -> None:
        super()._on_focus(event)
        self.refresh_items()

    def _on_blur(self, event: events.Blur) -> None:
        super()._on_blur(event)
        self.refresh_items()

    def refresh_items(self) -> None:
        is_focused = self.has_focus
        for i, peer in enumerate(self.peers):
            try:
                st = self.query_one(f"#device_item_{i}", Static)
                text = peer.name if peer.name and peer.name != peer.host else peer.host
                if is_focused and i == self.selected_index:
                    st.update(f"[bold #FF6B6B]• {text}[/]")
                else:
                    st.update(f"[#D7D7D7]• {text}[/]")
            except Exception:
                pass

    def move_up(self) -> None:
        if self.peers and self.selected_index > 0:
            self.selected_index -= 1
            self.refresh_items()
            self._scroll_to_selected()

    def move_down(self) -> None:
        if self.peers and self.selected_index < len(self.peers) - 1:
            self.selected_index += 1
            self.refresh_items()
            self._scroll_to_selected()

    def _scroll_to_selected(self) -> None:
        try:
            item = self.query_one(f"#device_item_{self.selected_index}", Static)
            item.scroll_visible()
        except Exception:
            pass

    def on_click(self, event: events.Click) -> None:
        self.focus()
        for i in range(len(self.peers)):
            try:
                w = self.query_one(f"#device_item_{i}", Static)
                if w.region.contains(event.screen_x, event.screen_y):
                    self.selected_index = i
                    self.refresh_items()
                    break
            except Exception:
                pass


class CreateScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.config = load_config()
        self._peers: list[Peer] = [p for p in self.config.peers if p.host]
        self._approve_event = threading.Event()
        self._approved = False
        self._awaiting_approval = False
        self._allow_btn: Button | None = None
        self._deny_btn: Button | None = None

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static(BANNER_JOIN, classes="session-header-text", id="session_host_title"),
            Vertical(
                Static(f"Port: {self.config.session_port}", id="peer_client_label"),
                Static("[#E8E8E8]Ready[/] [bold #78DC8C]○[/]", id="peer_status_label"),
                id="session_peer_info",
            ),
            id="session_header_row",
        )
        yield Vertical(
            Vertical(
                Static("[bold #E8E8E8]SAVED DEVICES[/]", classes="create-section-title"),
                SavedDevicesList(self._peers, id="saved_devices")
                if self._peers
                else Static("[dim]No saved devices found[/]", id="empty_devices"),
                id="create_top_section",
            ),
            Vertical(
                Static("HOSTNAME  ·  creator address", classes="composer-label"),
                Input(placeholder="Creator address: hostname, IPv4, or IPv6", id="host"),
                Static("Enter the address of the device waiting on Create Server", classes="composer-hint"),
                id="create_input_section",
            ),
            Vertical(
                Static("Status: idle", id="status"),
                Static("", id="fingerprint"),
                Horizontal(
                    Button("Allow", id="allow", classes="allow"),
                    Button("Deny", id="deny", classes="deny"),
                    id="create_actions",
                ),
                Button("Join Server", id="create", classes="primary"),
                id="create_bottom_section",
            ),
            id="create_body",
        )
        yield Horizontal(
            Label(r"[bold #E8E8E8]\[↑/↓][/] [dim #FFFFFF]Select[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E8E8E8]\[Tab][/] [dim #FFFFFF]Switch[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Connect / Allow[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Backspace][/] [dim #FFFFFF]Deny[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Esc][/] [dim #FFFFFF]Back[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
        )

    def _set_allow_visible(self, visible: bool) -> None:
        try:
            actions = self.query_one("#create_actions", Horizontal)
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
            self.query_one("#status", Static).update(f"Status: {text}")
            lower = text.lower()
            if "dial" in lower:
                self.query_one("#peer_status_label", Static).update("[#E8E8E8]Dialling[/] [bold #FFD166]○[/]")
            elif "live" in lower or "connected" in lower:
                self.query_one("#peer_status_label", Static).update("[#E8E8E8]Connected[/] [bold #78DC8C]●[/]")
            elif "fail" in lower:
                self.query_one("#peer_status_label", Static).update("[#FF6B6B]Failed[/] [bold #FF6B6B]⊗[/]")
            else:
                self.query_one("#peer_status_label", Static).update("[#E8E8E8]Ready[/] [bold #78DC8C]○[/]")
        except Exception:
            pass

    def _approve(self, fingerprint: str) -> bool:
        self._approved = False
        self._awaiting_approval = True
        self._approve_event.clear()
        try:
            self.app.call_from_thread(
                self.query_one("#fingerprint", Static).update,
                f"Fingerprint: {fingerprint[:32]}... Allow to trust this creator?",
            )
            self.app.call_from_thread(self._set_allow_visible, True)
        except Exception:
            pass
        self._approve_event.wait(timeout=120)
        self._awaiting_approval = False
        try:
            self.app.call_from_thread(self.query_one("#fingerprint", Static).update, "")
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

    def _start(self, host_override: str | None = None) -> None:
        if host_override:
            text = host_override.strip()
        elif isinstance(self.focused, SavedDevicesList):
            dev = self.query_one(SavedDevicesList).selected_device
            text = dev.host.strip() if dev and dev.host else ""
        else:
            try:
                text = self.query_one("#host", Input).value.strip()
            except Exception:
                text = ""
        if not text and self._peers:
            try:
                dev = self.query_one(SavedDevicesList).selected_device
                text = dev.host.strip() if dev and dev.host else ""
            except Exception:
                pass
        if not text:
            self._set_status("Failed: enter the creator's address first.")
            return
        try:
            host = parse_host_input(text)
        except Exception as exc:
            self._set_status(f"Failed: {exc}")
            return
        try:
            self.query_one("#host", Input).value = host
        except Exception:
            pass
        self._set_status(f"Dialling {host}...")
        threading.Thread(target=self._worker, args=(host,), daemon=True).start()

    def _worker(self, host: str) -> None:
        try:
            known = self.config.peer_for(host)
            known_fp = known.fingerprint if known else ""
            session = create_session(
                host,
                self.config.session_port,
                self.cwd,
                device=socket.gethostname(),
                known_fingerprint=known_fp,
                approve_fingerprint=None if known_fp else self._approve,
            )
            if known is None and getattr(session, "peer_fingerprint", ""):
                add_peer(self.config, Peer(name=host, host=host, fingerprint=session.peer_fingerprint))
            self.app.call_from_thread(self._set_status, "Session live, opening...")
            from .session_screen import SessionScreen
            self.app.call_from_thread(self.app.push_screen, SessionScreen(session, "joiner"))
        except Exception as exc:
            self.app.call_from_thread(self._set_status, f"Failed: {exc}")

    def on_mount(self) -> None:
        try:
            self._allow_btn = self.query_one("#allow", Button)
            self._deny_btn = self.query_one("#deny", Button)
        except Exception:
            pass
        self._set_allow_visible(False)
        if self._peers:
            try:
                self.query_one(SavedDevicesList).focus()
            except Exception:
                focus_first(self)
        else:
            try:
                self.query_one("#host", Input).focus()
            except Exception:
                focus_first(self)

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        try:
            if self._peers:
                self.query_one(SavedDevicesList).refresh_items()
        except Exception:
            pass

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        try:
            if self._peers:
                self.query_one(SavedDevicesList).refresh_items()
        except Exception:
            pass

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
            return
        focused = self.focused

        # Tab cycling between SavedDevicesList and Input
        if event.key in ("tab", "back_tab", "shift+tab"):
            if isinstance(focused, Input):
                if self._peers:
                    event.stop()
                    self.query_one(SavedDevicesList).focus()
                    return
            elif isinstance(focused, SavedDevicesList):
                event.stop()
                self.query_one("#host", Input).focus()
                return

        # Up/Down navigation between saved devices
        if event.key == "up":
            if isinstance(focused, SavedDevicesList):
                event.stop()
                focused.move_up()
                return
            if isinstance(focused, Input):
                event.stop()
                return
        elif event.key == "down":
            if isinstance(focused, SavedDevicesList):
                event.stop()
                focused.move_down()
                return
            if isinstance(focused, Input):
                event.stop()
                return

        # Backspace: deny when awaiting approval and host input is not focused
        if event.key == "backspace" and self._awaiting_approval and not isinstance(focused, Input):
            event.stop()
            self._handle_button_id("deny")
            return

        # Enter: allow when awaiting approval; else connect with selected device or entered hostname
        if event.key == "enter":
            if self._awaiting_approval and not isinstance(focused, Button):
                event.stop()
                self._handle_button_id("allow")
                return
            if isinstance(focused, SavedDevicesList):
                event.stop()
                dev = focused.selected_device
                if dev and dev.host:
                    self._start(dev.host)
                return
            if isinstance(focused, Input):
                event.stop()
                self._start()
                return
