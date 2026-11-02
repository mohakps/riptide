"""Create page must not show the menu's RIPTIDE logo through it.

Regression for v0.15.2: with a transparent screen background,
the menu's RIPTIDE logo showed through in empty rows on the
Create page, in particular the 1-row gap between the yellow
firewall banner and the CREATE header. The fix is an opaque
CreateScreen background, which changes no height or alignment.
"""
from __future__ import annotations

import asyncio

import pytest
from textual.app import App

from riptide.screens.create import CreateScreen
from riptide.screens.menu import MenuScreen
from riptide.theme import CSS


class _StackedApp(App):
    CSS = CSS

    async def on_mount(self):
        self.push_screen(MenuScreen())
        await asyncio.sleep(0.2)
        self.push_screen(CreateScreen(port_was_closed=True, firewall_opened=True))


@pytest.mark.asyncio
async def test_create_screen_background_is_opaque():
    app = _StackedApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert str(app.screen.styles.background) == "Color(18, 18, 18)"
        app.exit()


@pytest.mark.asyncio
async def test_create_banner_hides_menu_logo(tmp_path):
    app = _StackedApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        svg_path = tmp_path / "create.svg"
        app.save_screenshot(str(svg_path))
        text = svg_path.read_text()
        # One line of the RIPTIDE logo that used to peek through.
        assert "██╔══██╗██║██╔═══╝" not in text
        # The banner and the CREATE header are still there.
        assert "Firewall:" in text
        assert "________" in text
        app.exit()
