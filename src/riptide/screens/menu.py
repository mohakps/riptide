from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option
from .. import __version__
from ..core.focus import focus_first, handle_arrow_key
from ..theme import HEADER_BANNER, TAGLINES

def _build_option_prompt(title: str, desc: str, active: bool) -> Text:
    t = Text()
    if active:
        t.append("❯  ", style="bold #FF6B6B")
        t.append(f"{title:<16}", style="bold #FFFFFF")
        t.append("  ·  ", style="#71717A")
        t.append(desc, style="not bold #E0E0E0")
    else:
        t.append("   ", style="#52525B")
        t.append(f"{title:<16}", style="bold #A1A1AA")
        t.append("  ·  ", style="#52525B")
        t.append(desc, style="not bold #71717A")
    return t


class MenuScreen(Screen):
    def compose(self) -> ComposeResult:
        # Names swapped to match network roles, functionality unchanged:
        # Create Server listens (old JoinScreen), Join Server dials
        # (old CreateScreen). Create stays on top.
        options = [
            Option(_build_option_prompt("Create Server", "Wait for incoming session (Requires Port Forwarding)", True), id="create"),
            Option(_build_option_prompt("Join Server", "Dial out to peer (Required for CGNAT)", False), id="join"),
        ]
        yield Vertical(
            Static(HEADER_BANNER, classes="header"),
            Static(f"v{__version__}", classes="version-tag"),
            Static(TAGLINES["home"], classes="subheader"),
            OptionList(*options, id="menu_list"),
        )
        yield Horizontal(
            Label(r"[bold #E0E0E0]\[↑/↓][/] [dim #FFFFFF]Navigate[/]", classes="keymap-item keymap-left"),
            Label(r"[bold #E0E0E0]\[Enter][/] [dim #FFFFFF]Select[/]", classes="keymap-item"),
            Label(r"[bold #E0E0E0]\[Esc/q][/] [dim #FFFFFF]Quit[/]", classes="keymap-item keymap-right"),
            id="footer_bar",
        )
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from .create import CreateScreen
        from .join import JoinScreen

        # Class names are historical: JoinScreen is the listener,
        # CreateScreen is the dialler. The menu names are the swapped
        # ones the user sees.
        opt_id = event.option_id
        if opt_id == "create":
            from ..core.config import load_config, save_config
            from ..core.firewall import check_firewall_port, open_firewall_port

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
                active = idx == event.option_index
                opt_list.replace_option_prompt_at_index(idx, _build_option_prompt(title, desc, active))
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
