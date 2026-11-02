from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .. import __version__
from ..core.focus import focus_first, handle_arrow_key
from ..theme import HEADER_BANNER, TAGLINES


class MenuScreen(Screen):
    def compose(self) -> ComposeResult:
        # Names swapped to match network roles, functionality unchanged:
        # Create Server listens (old JoinScreen), Join Server dials
        # (old CreateScreen). Create stays on top.
        options = [
            Option("❯  Create Server      Wait for incoming session (Requires Port Forwarding)", id="create"),
            Option("   Join Server        Dial out to peer (Required for CGNAT)", id="join"),
        ]
        yield Vertical(
            Static(HEADER_BANNER, classes="header"),
            Static(f"v{__version__}", classes="version-tag"),
            Static(TAGLINES["home"], classes="subheader"),
            OptionList(*options, id="menu_list"),
            Static(r"[↑/↓] Navigate   \[Enter] Select   [Esc/q] Quit", classes="keymap-bar"),
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from .create import CreateScreen
        from .join import JoinScreen
        from ..core.config import load_config, save_config
        from ..core.firewall import check_firewall_port, open_firewall_port

        # Class names are historical: JoinScreen is the listener,
        # CreateScreen is the dialler. The menu names are the swapped
        # ones the user sees.
        opt_id = event.option_id
        if opt_id == "create":
            config = load_config()
            port = config.session_port
            is_open = check_firewall_port(port)
            config.firewall_port_open = is_open
            save_config(config)

            port_was_closed = not is_open
            if port_was_closed:
                open_firewall_port(port)

            self.app.push_screen(JoinScreen(port_was_closed=port_was_closed))
        elif opt_id == "join":
            self.app.push_screen(CreateScreen())

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
