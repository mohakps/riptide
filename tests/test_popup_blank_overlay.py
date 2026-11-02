"""Popup overlays are blank outside the card, not solid grey.

Regression for v0.15.4: the fingerprint and download modal
overlays used a solid #27272A background. The user asked for
blank spaces instead, as with the Create banner spacer. The
overlay widget still covers the full screen and writes blank
spaces outside the card, covering the page below, while its
background stays transparent, so the outside area is the
terminal background. The card itself stays solid #3F3F46.
"""
from __future__ import annotations

import pytest
from textual.app import App
from textual.containers import Vertical
from textual.widgets import Static

from riptide.screens.join import JoinScreen
from riptide.theme import CSS


@pytest.mark.asyncio
async def test_fingerprint_overlay_is_transparent_and_hides_page(tmp_path):
    class _App(App):
        CSS = CSS

        def on_mount(self):
            self.push_screen(JoinScreen())

    app = _App()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        overlay = app.screen.query_one("#fingerprint_modal_overlay", Vertical)
        card = app.screen.query_one("#fingerprint_modal_card", Vertical)
        assert overlay.styles.background.a == 0
        assert str(card.styles.background) == "Color(63, 63, 70)"
        app.screen.query_one("#fingerprint_modal_body", Static).update("Fingerprint:\nABCDEF\n\nAllow?")
        overlay.add_class("active")
        overlay.styles.display = "block"
        await pilot.pause()
        svg_path = tmp_path / "popup.svg"
        app.save_screenshot(str(svg_path))
        text = svg_path.read_text()
        assert "FINGERPRINT" in text
        # The Join page underneath is covered by blank spaces.
        assert "________" not in text
        app.exit()


@pytest.mark.asyncio
async def test_download_overlay_is_transparent():
    class _App(App):
        CSS = CSS

        def compose(self):
            yield Vertical(id="download_modal_overlay")

    app = _App()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        overlay = app.screen.query_one("#download_modal_overlay", Vertical)
        assert overlay.styles.background.a == 0
        app.exit()
