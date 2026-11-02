from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button

from riptide.screens.join import JoinScreen
from riptide.theme import CSS


class _App(App):
    CSS = CSS

    def __init__(self, screen):
        super().__init__()
        self._screen = screen

    def on_mount(self):
        self.push_screen(self._screen)


@pytest.mark.asyncio
async def test_join_server_button_is_hidden():
    # Regression for v0.14.0: the rename changed the button id
    # from "create" to "join", but the CSS hide rule still said
    # #join_bottom_section #create, so it matched nothing and
    # the button appeared on the Join Server page. The button
    # is unnecessary: Enter connects, and the footer says so.
    app = _App(JoinScreen())
    async with app.run_test() as pilot:
        await pilot.pause()
        button = app.screen.query_one("#join", Button)
        assert button.styles.display == "none"
