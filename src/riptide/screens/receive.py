from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..core.config import Peer, add_peer, load_config
from ..core.pairing import PairingCode, PairingServer, generate_code, remove_authorized_key
from ..theme import HEADER_LINES


class ReceiveScreen(Screen):
    def __init__(self) -> None:
        super().__init__()
        self.cwd = Path.cwd()
        self.config = load_config()
        self.code = PairingCode(generate_code())
        self.server: PairingServer | None = None
        self.pending: tuple[str, str] | None = None
        self.allow_once_keys: list[str] = []

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static("RECEIVE", classes="accent"),
            Static("Listening for SSH. Keep this screen open.", classes="success"),
            Static(f"Your pairing code (valid 5 minutes): {self.code.code}", id="code"),
            Static("Share only this code with the sender. Never share a full public key by hand.", classes="dim"),
            Static("No incoming pairing yet.", id="incoming"),
            Button("New pairing code", id="new_code"),
            Button("Allow always", id="allow_always"),
            Button("Allow once", id="allow_once"),
            Button("Deny", id="deny"),
            Static(f"Files will go to: {self.cwd}", classes="dim"),
            Static("Partial files are saved with a .part suffix until verified.", classes="dim"),
            Button("Back", id="back"),
        )

    def on_mount(self) -> None:
        self._start_server()

    def _start_server(self) -> None:
        self._stop_server()
        authorized_keys = Path.home() / ".ssh" / "authorized_keys"
        self.server = PairingServer(
            self.code, authorized_keys,
            port=self.config.pairing_port,
            on_success=lambda device, key: self.app.call_from_thread(self._on_pairing, device, key),
        )
        try:
            self.server.start()
        except Exception as exc:
            try:
                self.query_one("#incoming", Static).update(f"Pairing listener failed to start: {exc}")
            except Exception:
                pass

    def _stop_server(self) -> None:
        if self.server is not None:
            try:
                self.server.stop()
            except Exception:
                pass
            self.server = None

    def _on_pairing(self, device: str, public_key: str) -> None:
        self.pending = (device, public_key)
        try:
            self.query_one("#incoming", Static).update(
                f"Incoming pairing from: {device}. Choose Allow always, Allow once, or Deny."
            )
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "new_code":
            self.code = PairingCode(generate_code())
            try:
                self.query_one("#code", Static).update(
                    f"Your pairing code (valid 5 minutes): {self.code.code}"
                )
            except Exception:
                pass
            self._start_server()
        elif button_id in ("allow_always", "allow_once"):
            if self.pending is None:
                return
            device, public_key = self.pending
            # The key was already added by the pairing listener. Record the peer.
            add_peer(self.config, Peer(name=device, user=device, host=device,
                                       fingerprint="", allow_always=(button_id == "allow_always")))
            if button_id == "allow_once":
                self.allow_once_keys.append(public_key)
            try:
                self.query_one("#incoming", Static).update(f"Allowed: {device} ({button_id.replace('_', ' ')})")
            except Exception:
                pass
            self.pending = None
        elif button_id == "deny":
            if self.pending is not None:
                device, public_key = self.pending
                remove_authorized_key(Path.home() / ".ssh" / "authorized_keys", public_key)
                try:
                    self.query_one("#incoming", Static).update(f"Denied: {device}")
                except Exception:
                    pass
                self.pending = None
        elif button_id == "back":
            self._cleanup_once()
            self._stop_server()
            self.app.pop_screen()

    def _cleanup_once(self) -> None:
        authorized_keys = Path.home() / ".ssh" / "authorized_keys"
        for key in self.allow_once_keys:
            remove_authorized_key(authorized_keys, key)
        self.allow_once_keys.clear()

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self._cleanup_once()
            self._stop_server()
            self.app.pop_screen()
