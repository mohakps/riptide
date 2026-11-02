"""Create page must not show the menu's RIPTIDE logo through it.

Regression for v0.15.3, replacing the v0.15.2 opaque background
fix, which the user rejected. With a transparent screen
background, the menu's RIPTIDE logo showed through in the
1-row margin gap between the yellow firewall banner and the
CREATE header. The fix is a blank 1-row widget in place of
that margin: it writes blank spaces into the row, covering
the logo, while the screen stays transparent. Total height
before the CREATE header is unchanged, and the banner text
is not bold.
"""
from __future__ import annotations

import asyncio

import pytest
from textual.app import App
from textual.widgets import Static

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
async def test_create_banner_spacer_covers_logo_row_with_no_layout_change():
    app = _StackedApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        banner = app.screen.query_one("#router_banner", Static)
        spacer = app.screen.query_one("#router_banner_spacer", Static)
        header = app.screen.query_one("#session_header_row")
        assert banner.styles.display == "block"
        assert spacer.styles.display == "block"
        assert spacer.region.height == 1
        # Spacer sits exactly where the old margin gap was, and
        # the header is exactly where it was with banner + margin.
        assert spacer.region.y == banner.region.y + banner.region.height
        assert header.region.y == spacer.region.y + spacer.region.height
        assert header.region.y == 6
        # Banner text is not bold, and the screen stays transparent.
        assert not banner.styles.text_style.bold
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


@pytest.mark.asyncio
async def test_create_banner_spacer_hidden_when_banner_hidden():
    # No-banner layout must not gain an extra blank row.
    from textual.app import App as _App

    class _NoBannerApp(_App):
        CSS = CSS

        def on_mount(self):
            self.push_screen(CreateScreen())

    app = _NoBannerApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        spacer = app.screen.query_one("#router_banner_spacer", Static)
        assert spacer.styles.display == "none"
        app.exit()
