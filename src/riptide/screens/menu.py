from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option

from .. import __version__
from ..core.focus import focus_first, handle_arrow_key
from ..core.resume import cleanup_parts
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

        opt_id = event.option_id
        if opt_id == "create":
            config = load_config()
            port = config.session_port
            # Windows: reading the firewall rule state needs no
            # admin (netsh show rule runs for a normal user), so
            # check the port on every Create click and re-open it
            # if the rule is gone. Linux: the check needs root to
            # read ufw status, so the port is set up once, on the
            # first Create click, and the config record is trusted
            # after that. While the record does not say open, this
            # click runs the setup.
            firewall_opened = False
            firewall_cancelled = False
            port_was_closed = False
            from ..core.firewall import check_firewall_port, get_os, setup_firewall_port

            run_setup = False
            if get_os() == "windows":
                if check_firewall_port(port):
                    # Port is open. Sync the record so config
                    # matches reality; no banner, no prompt.
                    if config.firewall_port_open is not True:
                        config.firewall_port_open = True
                        save_config(config)
                else:
                    run_setup = True
            elif config.firewall_port_open is not True:
                run_setup = True
            if run_setup:
                result = setup_firewall_port(port)
                port_was_closed = True
                if result == "opened":
                    config.firewall_port_open = True
                    firewall_opened = True
                elif result == "cancelled":
                    config.firewall_port_open = False
                    firewall_cancelled = True
                else:
                    config.firewall_port_open = False
                save_config(config)
            self.app.push_screen(
                CreateScreen(
                    port_was_closed=port_was_closed,
                    firewall_opened=firewall_opened,
                    firewall_cancelled=firewall_cancelled,
                )
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
        # A .part older than 1 day can no longer be resumed, so
        # it is deleted at app launch, in the launch folder.
        try:
            cleanup_parts(Path.cwd())
        except Exception:
            pass
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
