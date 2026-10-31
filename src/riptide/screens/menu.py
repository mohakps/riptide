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
            Static("Direct file transfer. No cloud in the middle.", classes="subheader"),
            Button("Create Server", id="create"),
            Button("Join Server", id="join"),
            Button("Exit", id="exit"),
            Static("Arrow keys + Enter to choose. Esc goes back.", classes="dim"),
            Static("Set-up is disabled in this version.", classes="dim"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from .create import CreateScreen
        from .join import JoinScreen

        button_id = event.button.id
        if button_id == "create":
            self.app.push_screen(CreateScreen())
        elif button_id == "join":
            self.app.push_screen(JoinScreen())
        elif button_id == "exit":
            self.app.exit()

    def on_mount(self) -> None:
        focus_first(self)

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.exit()
            return
        if handle_arrow_key(self, event.key):
            event.stop()
