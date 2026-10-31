from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from riptide.screens.create import CreateScreen
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
async def test_join_footer_and_keys():
    app = _App(JoinScreen())
    async with app.run_test() as pilot:
        screen = app.screen
        footer = screen.query_one("#footer_bar")
        text = " ".join(node.render().plain for node in footer.query("Label"))
        assert "[Space]" in text and "[Enter]" in text and "[Backspace]" in text and "[Esc]" in text
        # Backspace denies when waiting, Enter allows when waiting.
        screen._awaiting_approval = True
        screen._approved = False
        await pilot.press("backspace")
        assert screen._approved is False
        # _approve_event was set by deny handler, even though no thread waited.
        screen._awaiting_approval = True
        await pilot.press("enter")
        assert screen._approved is True


@pytest.mark.asyncio
async def test_create_footer_and_keys():
    app = _App(CreateScreen())
    async with app.run_test() as pilot:
        screen = app.screen
        # Footer text updated. Note: Rich markup strips the [Space]
        # brackets in render().plain, so check the words, not brackets.
        from textual.widgets import Static
        footers = [n.render().plain for n in screen.query(Static)]
        assert any("Create / Allow" in f and "Deny" in f and "Select" in f for f in footers)
        # Backspace denies when waiting (input not focused).
        screen._awaiting_approval = True
        screen._approved = False
        # Focus a button, not the input, so backspace is a deny, not a delete.
        screen.query_one("#create").focus()
        await pilot.press("backspace")
        assert screen._approved is False
