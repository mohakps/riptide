import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from textual.app import App
from textual.widgets import Static

from riptide.core.identity import fingerprint_code
from riptide.screens.create import CreateScreen
from riptide.theme import CSS


class _App(App):
    CSS = CSS

    def __init__(self, screen):
        super().__init__()
        self._screen = screen

    def on_mount(self):
        self.push_screen(self._screen)


@pytest.mark.asyncio
async def test_create_shows_peer_code_and_my_code():
    app = _App(CreateScreen())
    async with app.run_test() as pilot:
        screen = app.screen
        # My code widget exists on the Create page.
        my_code = screen.query_one("#my_code", Static)
        assert "My code" in my_code.render().plain
        # New peer card shows peer code, fingerprint, and comparison note.
        fp = "123456" + "ab" * 29
        screen._show_incoming_connection("friend-pc", fp, "new", "")
        await pilot.pause()
        card_text = screen.query_one("#incoming").render().plain
        assert f"Peer code: {fingerprint_code(fp)}" in card_text
        assert "friend-pc" in card_text
        assert "compare peer code" in card_text.lower()
        # Known peer card shows the same code as a confirmation.
        screen._show_incoming_connection("friend-pc", fp, "known", "")
        await pilot.pause()
        card_text = screen.query_one("#incoming").render().plain
        assert "Known peer" in card_text
        assert f"Peer code: {fingerprint_code(fp)}" in card_text
        # Changed peer card shows new code and old code.
        old_fp = "abcdef" + "00" * 29
        screen._show_incoming_connection("friend-pc", fp, "changed", old_fp)
        await pilot.pause()
        card_text = screen.query_one("#incoming").render().plain
        assert "Fingerprint changed" in card_text
        assert f"Peer code: {fingerprint_code(fp)}" in card_text
        assert f"Old peer code: {fingerprint_code(old_fp)}" in card_text
