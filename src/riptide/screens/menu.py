from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from .. import __version__
from ..core.focus import focus_first, handle_arrow_key
from ..theme import HEADER_BANNER, TAGLINES


class MenuScreen(Screen):
    def compose(self) -> ComposeResult:
        # Create Server listens, Join Server dials. Create stays on top.
        options = [
            Option("❯  Create Server      Wait for incoming session (Requires Port Forwarding)", id="create"),
            Option("   Join Server        Dial out to peer (Required for CGNAT)", id="join"),
        ]
        yield Vertical(
            Static(HEADER_BANNER, classes="header"),
            Static(f"v{__version__}", classes="version-tag"),
            Static(TAGLINES["home"], classes="subheader"),
            OptionList(*options, id="menu_list"),
        )
        yield Horizontal(
            Label(r"[bold #E8E8E8]\[↑/↓][/] [dim #FFFFFF]Navigate[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E8E8E8]\[Enter][/] [dim #FFFFFF]Select[/]", classes="keymap-item"),
            Label(r"[bold #E8E8E8]\[Esc][/] [dim #FFFFFF]Quit[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from .create import CreateScreen
        from .join import JoinScreen
        from ..core.config import load_config, save_config
        from ..core.firewall import check_firewall_port, open_firewall_port

        opt_id = event.option_id
        if opt_id == "create":
            config = load_config()
            port = config.session_port
            # On clicking Create Server, check the OS firewall for the
            # session port and open it automatically if it is closed.
            # ensure_firewall_port uses sudo -n on Linux, so it fails
            # fast instead of hanging on a password prompt when the
            # user cannot open the firewall automatically. The Create
            # page then reports opened or failed, with the manual
            # command when opening failed.
            from ..core.firewall import ensure_firewall_port

            was_open, opened, is_open_now = ensure_firewall_port(port)
            config.firewall_port_open = is_open_now
            save_config(config)

            self.app.push_screen(
                CreateScreen(port_was_closed=not was_open, firewall_opened=opened)
            )
        elif opt_id == "join":
            self.app.push_screen(JoinScreen())

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        try:
            opt_list = self.query_one("#menu_list", OptionList)
            prompts = [
                ("create", "Create Server", "Wait for incoming session (Requires Port Forwarding)"),
                ("join", "Join Server", "Dial out to peer (Required for CGNAT)"),
            ]
            for idx, (oid, title, desc) in enumerate(prompts):
                prefix = "❯  " if idx == event.option_index else "   "
                opt_list.replace_option_prompt_at_index(idx, f"{prefix}{title:<18} {desc}")
        except Exception:
            pass

    def on_mount(self) -> None:
        try:
            self.query_one("#menu_list", OptionList).focus()
        except Exception:
            focus_first(self)

    async def on_key(self, event) -> None:
        if event.key in ("escape", "q"):
            self.app.exit()
            event.stop()
            return
        if event.key in ("down", "up") and not isinstance(self.focused, OptionList):
            if handle_arrow_key(self, event.key):
                event.stop()
