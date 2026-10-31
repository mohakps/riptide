from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..core.focus import focus_first, handle_arrow_key
from ..theme import HEADER_LINES


class MenuScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static("Direct, encrypted file transfer. No cloud in the middle.", classes="subheader"),
            Button("Send", id="send"),
            Button("Receive", id="receive"),
            Button("Set-up SSH", id="setup"),
            Button("Exit", id="exit"),
            Static("Arrow keys + Enter to choose. Esc goes back.", classes="dim"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from .receive import ReceiveScreen
        from .send import SendScreen
        from .setup import SetupScreen

        button_id = event.button.id
        if button_id == "send":
            self.app.push_screen(SendScreen())
        elif button_id == "receive":
            self.app.push_screen(ReceiveScreen())
        elif button_id == "setup":
            self.app.push_screen(SetupScreen())
        elif button_id == "exit":
            self.app.exit()

    def on_mount(self) -> None:
        # Without this, no button is focused at start and arrow keys
        # appear to do nothing. Focus Send first.
        focus_first(self)

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.exit()
            return
        if handle_arrow_key(self, event.key):
            event.stop()
