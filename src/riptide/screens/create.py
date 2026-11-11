"""Create Server page: the listener.

Waits for an incoming connection from the client.
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
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static

from ..core.config import Peer, add_peer, load_config
from ..core.identity import cert_der_from_pem, cert_fingerprint, ensure_identity, fingerprint_code
from ..core.nat import public_ip, public_ipv6
from ..core.session import HostListener
from ..theme import BANNER_CREATE


class CreateScreen(Screen):
    def __init__(self, port_was_closed: bool = False, firewall_opened: bool = False, firewall_cancelled: bool = False) -> None:
        super().__init__()
        self.port_was_closed = port_was_closed
        self.firewall_opened = firewall_opened
        self.firewall_cancelled = firewall_cancelled
        # Watchdog state: a failed open is not retried every 20 s,
        # it is retried only after the port becomes open again and
        # then closes again. The banner kind tracks whether a
        # failure banner is currently shown, so it can be cleared
        # when the port opens again.
        self._firewall_banner_kind: str | None = (
            "success" if port_was_closed and firewall_opened
            else "cancelled" if port_was_closed and firewall_cancelled
            else "failed" if port_was_closed
            else None
        )
        self._firewall_watch_failed = port_was_closed and not firewall_opened
        self.cwd = Path.cwd()
        self.config = load_config()
        self._pending: tuple[str, str, str, str] | None = None
        self._approve_event = threading.Event()
        self._approved = False
        self._awaiting_approval = False
        self._listener: HostListener | None = None
        self._stopped = threading.Event()
        self._allow_btn: Button | None = None
        self._deny_btn: Button | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="router_banner")
        # Blank row in place of the banner's old bottom margin.
        # A margin row belongs to no widget, so the menu's
        # RIPTIDE logo underneath showed through it. This blank
        # widget writes spaces into that row, covering the logo,
        # while staying transparent itself. It is shown only
        # together with the banner, so the no-banner layout
        # does not gain an extra blank row.
        yield Static("", id="router_banner_spacer")
        # Plain Vertical, not VerticalScroll: this page is only a
        # header and a waiting card, it never needs scrolling, and
        # the scroll container was showing a vertical scrollbar
        # even when the terminal was tall enough for the content.
        yield Vertical(
            Horizontal(
                Static(BANNER_CREATE, classes="session-header-text", id="session_host_title"),
                Vertical(
                    Static(f"Port: {self.config.session_port}", id="peer_client_label"),
                    Static("[#E8E8E8]Listening[/] [bold #FFD166]○[/]", id="peer_status_label"),
                    id="session_peer_info",
                ),
                id="session_header_row",
            ),
            Vertical(
                Static("Your public address: checking…", id="public_ip"),
                Static("Your IPv6 address: checking…", id="public_ipv6"),
                Static("My code: checking…", id="my_code"),
                Static(
                    f"[dim]○[/] [bold #E8E8E8]Waiting for client on port {self.config.session_port}...[/]\n\n"
                    f"[dim]Share your IP or hostname with the client to initiate connection.[/]",
                    id="incoming",
                ),
                Horizontal(
                    Button("Accept", id="allow", classes="allow"),
                    Button("Deny", id="deny", classes="deny"),
                    id="create_actions",
                ),
                id="incoming_card",
            ),
            id="create_content",
        )
        yield Horizontal(
            Label(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Accept[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E8E8E8]\[Backspace][/] [dim #FFFFFF]Deny[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Space][/] [dim #FFFFFF]Select[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Esc][/] [dim #FFFFFF]Back[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
        )

    def _show_router_banner(self) -> None:
        try:
            from ..core.firewall import manual_firewall_command, windows_block_rule_exists

            banner = self.query_one("#router_banner", Static)
            port = self.config.session_port
            if self.firewall_opened:
                self._firewall_banner_kind = "success"
                banner.update(
                    f"Firewall: port {port} opened automatically. "
                    f"Please also forward port {port} (TCP) in your router settings."
                )
            elif windows_block_rule_exists(port):
                self._firewall_banner_kind = "failed"
                banner.update(
                    f"Firewall: port {port} is blocked by a block rule. "
                    f"An allow rule alone will not open it. "
                    f"Remove or disable the block rule for port {port} in Windows Defender Firewall, Advanced Settings, Inbound Rules. "
                    f"Then also forward port {port} (TCP) in your router settings."
                )
            elif self.firewall_cancelled:
                self._firewall_banner_kind = "cancelled"
                command = manual_firewall_command(port)
                banner.update(
                    f"Firewall: port {port} was not opened because you cancelled the admin prompt. "
                    f"Click Create Server again to try again, or run as administrator, or with sudo: {command} "
                    f"Then also forward port {port} (TCP) in your router settings."
                )
            else:
                self._firewall_banner_kind = "failed"
                command = manual_firewall_command(port)
                banner.update(
                    f"Firewall: port {port} was closed and could not be opened automatically. "
                    f"Run as administrator, or with sudo: {command} "
                    f"Then also forward port {port} (TCP) in your router settings."
                )
            banner.styles.display = "block"
            try:
                self.query_one("#router_banner_spacer", Static).styles.display = "block"
            except Exception:
                pass
        except Exception:
            pass

    def _show_profile_note(self) -> None:
        """Show the note for an old all-profile firewall rule.

        The port is open, but the rule covers all profiles,
        including Domain. Replacing it with a Private, Public
        rule needs riptide --cleanup first, which also deletes
        the identity and saved peers, so the note says so.
        """
        try:
            banner = self.query_one("#router_banner", Static)
            port = self.config.session_port
            self._firewall_banner_kind = "profile"
            banner.update(
                f"Firewall: port {port} is open on all profiles, including Domain. "
                f"To replace it with a Private, Public rule, run `riptide --cleanup` "
                f"(this also deletes your identity and saved peers), then click Create Server again."
            )
            banner.styles.display = "block"
            try:
                self.query_one("#router_banner_spacer", Static).styles.display = "block"
            except Exception:
                pass
        except Exception:
            pass

    def _set_firewall_banner(self, opened: bool) -> None:
        self.port_was_closed = True
        self.firewall_opened = opened
        self.firewall_cancelled = False
        self._show_router_banner()

    def _clear_firewall_banner(self) -> None:
        try:
            banner = self.query_one("#router_banner", Static)
            banner.update("")
            banner.styles.display = "none"
            self.query_one("#router_banner_spacer", Static).styles.display = "none"
        except Exception:
            pass
        self._firewall_banner_kind = None
        self.port_was_closed = False
        self.firewall_cancelled = False

    def _firewall_watch(self) -> None:
        """Re-check the firewall while Create Server waits.

        The menu check only runs when Create Server is clicked.
        If the rule is turned off after that, the host hears
        nothing, because a firewall drop never reaches the app,
        while the client times out after 30 s. This loop checks
        every 20 s, tries to open a newly closed port, and warns
        on the Create page when opening fails. It never prompts
        for elevation: it uses the plain ensure_firewall_port,
        not the menu elevation path, so a cancelled prompt is
        never re-prompted from here.
        """
        from ..core.firewall import check_firewall_port, ensure_firewall_port

        while not self._stopped.wait(timeout=20):
            try:
                port = self.config.session_port
                if check_firewall_port(port):
                    self._firewall_watch_failed = False
                    if self._firewall_banner_kind in ("failed", "cancelled"):
                        try:
                            self.app.call_from_thread(self._clear_firewall_banner)
                        except Exception:
                            pass
                    continue
                if self._firewall_watch_failed:
                    continue
                _was_open, opened, is_open_now = ensure_firewall_port(port)
                if is_open_now:
                    try:
                        self.app.call_from_thread(self._set_firewall_banner, True)
                    except Exception:
                        pass
                else:
                    self._firewall_watch_failed = True
                    try:
                        self.app.call_from_thread(self._set_firewall_banner, False)
                    except Exception:
                        pass
            except Exception:
                pass


    def _update_public_ip(self, ip: str | None) -> None:
        try:
            if ip:
                self.query_one("#public_ip", Static).update(
                    f"Your public address: [bold #FF6B6B]{ip}[/]"
                )
            else:
                self.query_one("#public_ip", Static).update(
                    "[dim]Your public address: could not be determined (check internet)[/]"
                )
        except Exception:
            pass

    def _update_public_ipv6(self, ip: str | None) -> None:
        # Shown only when the host has a public IPv6 address; with
        # none, the row hides instead of showing a dead line.
        try:
            widget = self.query_one("#public_ipv6", Static)
            if ip:
                widget.styles.display = "block"
                widget.update(f"Your IPv6 address: [bold #FF6B6B]{ip}[/]")
            else:
                widget.styles.display = "none"
        except Exception:
            pass

    def _fetch_public_ip(self) -> None:
        try:
            ip = public_ip()
        except Exception:
            ip = None
        try:
            ip6 = public_ipv6()
        except Exception:
            ip6 = None
        try:
            self.app.call_from_thread(self._update_public_ip, ip)
            self.app.call_from_thread(self._update_public_ipv6, ip6)
        except Exception:
            pass

    def _update_my_code(self, code: str | None) -> None:
        try:
            if code:
                self.query_one("#my_code", Static).update(
                    f"My code: [bold #FFD166]{code}[/]"
                )
            else:
                self.query_one("#my_code", Static).update(
                    "[dim]My code: could not be determined[/]"
                )
        except Exception:
            pass

    def _fetch_my_code(self) -> None:
        # Local identity only, no network. Shown on the Create
        # page at all times, so the host can answer when the
        # dialler asks, is your code XXX-XXX, without needing
        # a connection first.
        try:
            _key, cert_path = ensure_identity()
            code = fingerprint_code(cert_fingerprint(cert_der_from_pem(cert_path)))
        except Exception:
            code = None
        try:
            self.app.call_from_thread(self._update_my_code, code)
        except Exception:
            pass

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
        # Never clobber an active incoming-connection card with a
        # background status message. A queued worker failure from a
        # stale listener must not overwrite a decision the user is
        # looking at.
        try:
            card = self.query_one("#incoming_card", Vertical)
            if "active" in card.classes:
                return
        except Exception:
            pass
        try:
            self.query_one("#incoming", Static).update(text)
        except Exception:
            pass

    def _show_incoming_connection(self, device: str, fingerprint: str, status: str = "new", old_fingerprint: str = "") -> None:
        try:
            card = self.query_one("#incoming_card", Vertical)
            card.add_class("active")
            if fingerprint:
                fp_text = f"\n[dim]Fingerprint: {fingerprint[:32]}...[/]"
                code_text = f"\n[bold #FFD166]Peer code: {fingerprint_code(fingerprint)}[/]"
            else:
                # This should not happen in v1.1, because an empty
                # client fingerprint aborts before approval. Show
                # it explicitly if it ever does, instead of hiding it.
                fp_text = "\n[bold #FF6B6B]Fingerprint: missing, cannot authenticate[/]"
                code_text = "\n[bold #FF6B6B]Peer code: ------[/]"
            if status == "known":
                status_text = "\n[bold #78DC8C]Known peer: fingerprint matches saved[/]"
                question = "Accept connection from this known peer?"
            elif status == "changed":
                old_text = f"\n[dim]Old fingerprint: {old_fingerprint[:32]}...[/]" if old_fingerprint else ""
                old_code_text = f"\n[dim]Old peer code: {fingerprint_code(old_fingerprint)}[/]" if old_fingerprint else ""
                status_text = (
                    "\n[bold #FF6B6B]WARNING: Fingerprint changed for this device[/]"
                    f"{old_text}{old_code_text}"
                    "\n[#E8E8E8]Accept only if this peer reinstalled Riptide or deleted its identity. Accepting here replaces the saved fingerprint.[/]"
                )
                question = "Replace saved fingerprint and accept?"
            else:
                status_text = "\n[bold #FFD166]New peer: first time, compare peer code with the peer out of band before Accept[/]"
                question = "Accept connection from this peer?"
            msg = (
                f"[bold #78DC8C]● INCOMING CONNECTION REQUEST[/]\n\n"
                f"Peer Device: [bold #FFFFFF]{device}[/]{fp_text}{code_text}{status_text}\n\n"
                f"[#E8E8E8]{question}[/]"
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

    def _approve(self, device: str, fingerprint: str, status: str = "new", old_fingerprint: str = "") -> bool:
        self._pending = (device, fingerprint, status, old_fingerprint)
        self._approved = False
        self._awaiting_approval = True
        self._approve_event.clear()
        try:
            self.app.call_from_thread(self._show_incoming_connection, device, fingerprint, status, old_fingerprint)
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
        # Public IP, same timing, so the client has something to dial.
        threading.Thread(target=self._fetch_public_ip, daemon=True).start()
        threading.Thread(target=self._fetch_my_code, daemon=True).start()
        threading.Thread(target=self._worker, daemon=True).start()
        if self.port_was_closed:
            self._show_router_banner()
        else:
            # The port is open, but an old all-profile rule may
            # still be in place. Show the note so it can be
            # replaced with a Private, Public rule.
            try:
                from ..core.firewall import windows_riptide_rule_profile

                if windows_riptide_rule_profile(self.config.session_port) in ("any", "all"):
                    self._show_profile_note()
            except Exception:
                pass
        # Re-check while waiting, so turning the rule off after
        # clicking Create Server still warns and tries to open it.
        threading.Thread(target=self._firewall_watch, daemon=True).start()

    def on_unmount(self) -> None:
        # Free the listener port when leaving, otherwise a later
        # Create Server page in the same process cannot bind it.
        # Set the flag first, so a worker that has not bound yet
        # aborts instead of leaking a listener after this screen is gone.
        self._stopped.set()
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass

    def _worker(self) -> None:
        # Listen for clients until the screen is left. After each
        # session ends, listen again, so a peer can rejoin without
        # restarting Create Server. A denied peer still stops the
        # listener, as before: denying is a deliberate stop, while
        # a session ending is not.
        while not self._stopped.is_set():
            try:
                self._pending = None
                self._listener = HostListener(
                    self.config.session_port, self.cwd, device=socket.gethostname(),
                    approve=self._approve,
                )
                if self._stopped.is_set():
                    return
                session = self._listener.wait_for_client()
                if self._pending is not None:
                    # _pending is (device, fingerprint, status, old_fp).
                    # Keep the dial-back peer save separate from the
                    # host trusted client save, which HostListener
                    # already did after approval.
                    try:
                        device, fp, _status, _old_fp = self._pending
                    except Exception:
                        device, fp = self._pending[0], self._pending[1]
                    if self.config.peer_for(device) is None:
                        add_peer(self.config, Peer(name=device, host=device, fingerprint=fp))
                self.app.call_from_thread(self._set_status, "[bold #78DC8C]Connection accepted! Opening session...[/]")
                from .session_screen import SessionScreen
                self.app.call_from_thread(self.app.push_screen, SessionScreen(session, "host"))
                # The session runs on its own screen. Wait here until
                # it ends, then listen again.
                while not session.wait_ended(timeout=0.5):
                    if self._stopped.is_set():
                        return
                if self._stopped.is_set():
                    return
                self.app.call_from_thread(
                    self._set_status,
                    f"[dim]Peer disconnected.[/] [bold #E8E8E8]Waiting for client on port {self.config.session_port}...[/]",
                )
            except Exception as exc:
                # Do not overwrite an incoming-connection card that is
                # already on screen; a worker failure cannot happen while
                # an approval is pending in the real flow.
                if self._awaiting_approval:
                    return
                if self._stopped.is_set():
                    return
                try:
                    self.app.call_from_thread(self._set_status, f"[bold #FF6B6B]Failed: {exc}[/]")
                except Exception:
                    pass
                return

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self._stopped.set()
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
