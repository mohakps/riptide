from __future__ import annotations

import platform
import threading

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..core import nat as nat_mod
from ..core.setup_linux import run_setup as linux_setup, steps as linux_steps
from ..core.setup_windows import run_setup as windows_setup, steps as windows_steps
from ..theme import HEADER_LINES


class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        system = platform.system()
        steps = windows_steps() if system == "Windows" else linux_steps()
        step_text = "\n".join(f"- {s['title']}: {s['detail']}" for s in steps)
        yield Vertical(
            Static("\n".join(HEADER_LINES), classes="header"),
            Static("SET-UP SSH", classes="accent"),
            Static(f"Detected system: {system}", classes="dim"),
            Static(step_text),
            Static("Output:", classes="accent"),
            Static("Not run yet.", id="output"),
            Button("Run set-up", id="run"),
            Button("Try automatic forwarding", id="upnp"),
            Button("Back", id="back"),
            Static(nat_mod.REVERSE_MODE_TEXT, classes="dim"),
            Static(nat_mod.manual_instructions(nat_mod.local_ip()), classes="dim"),
        )

    def _set_output(self, text: str) -> None:
        try:
            self.query_one("#output", Static).update(text)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self._set_output("Running set-up in the background. This may ask for Administrator or sudo.")
            threading.Thread(target=self._run_worker, daemon=True).start()
        elif event.button.id == "upnp":
            ok, message = nat_mod.upnp_attempt()
            self._set_output(f"Automatic forwarding: {message}")
        elif event.button.id == "back":
            self.app.pop_screen()

    def _run_worker(self) -> None:
        try:
            if platform.system() == "Windows":
                lines = windows_setup()
            else:
                lines = linux_setup()
            self.app.call_from_thread(self._set_output, "\n".join(lines))
        except Exception as exc:
            self.app.call_from_thread(self._set_output, f"Set-up failed: {exc}")

    async def on_key(self, event) -> None:
        if event.key == "escape":
            self.app.pop_screen()
