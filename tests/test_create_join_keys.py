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
async def test_join_screen_redesign():
    """Verify join screen redesign:
    - Omit unnecessary text.
    - Highlight incoming connection.
    - Enter accepts, backspace denies.
    - No up/down arrow keys.
    - Buttons same size with green/red backgrounds.
    """
    from riptide.theme import TAGLINES
    from textual.widgets import Button

    app = _App(JoinScreen())
    async with app.run_test() as pilot:
        screen = app.screen

        # 1. Omit unnecessary text
        all_text = " ".join(node.render().plain for node in screen.query("Static, Label"))
        assert TAGLINES["join"] not in all_text
        assert "Waiting for a creator. Keep this screen open." not in all_text
        assert "Share your address with the creator." not in all_text

        # 2. Buttons same size and have green/red background
        btn_allow = screen.query_one("#allow", Button)
        btn_deny = screen.query_one("#deny", Button)
        assert btn_allow.styles.width == btn_deny.styles.width
        assert btn_allow.styles.height == btn_deny.styles.height
        assert btn_allow.styles.background.hex.upper() in ("#78DC8C", "#8EEC9F")
        assert btn_deny.styles.background.hex.upper() in ("#FF6B6B", "#FF8585")

        # 3. Highlight incoming connection
        card = screen.query_one("#incoming_card")
        assert "active" not in card.classes
        screen._show_incoming_connection("friend-pc", "abcd1234efgh5678")
        await pilot.pause()
        assert "active" in card.classes
        card_text = screen.query_one("#incoming").render().plain
        assert "INCOMING CONNECTION" in card_text
        assert "friend-pc" in card_text

        # 4. No up/down arrow keys
        focused_before = screen.focused
        await pilot.press("up")
        await pilot.press("down")
        assert screen.focused == focused_before

        # 5. Enter accepts, Backspace denies
        screen._awaiting_approval = True
        screen._approved = False
        await pilot.press("enter")
        assert screen._approved is True

        screen._awaiting_approval = True
        screen._approved = True
        await pilot.press("backspace")
        assert screen._approved is False
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
