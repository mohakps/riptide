import pytest
from riptide.app import RiptideApp
from riptide.screens.menu import MenuScreen
from riptide import __version__


class DummyApp(RiptideApp):
    def on_mount(self):
        super().on_mount()

@pytest.mark.asyncio
async def test_menu_screen_composition():
    app = DummyApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, MenuScreen)
        # Check version is rendered
        labels = [node.render().plain for node in screen.query("Static, Label")]
        full_text = " ".join(labels)
        assert f"v{__version__}" in full_text
        assert "Zero cloud storage" in full_text
        # Ensure Exit button is removed
        assert len(screen.query("#exit")) == 0
        # Ensure option list exists
        assert len(screen.query("#menu_list")) == 1

@pytest.mark.asyncio
async def test_menu_arrow_keys_navigate():
    app = DummyApp()
    async with app.run_test() as pilot:
        screen = app.screen
        opt_list = screen.query_one("#menu_list")
        assert opt_list.highlighted == 0
        await pilot.press("down")
        assert opt_list.highlighted == 1
        await pilot.press("up")
        assert opt_list.highlighted == 0


@pytest.mark.asyncio
async def test_transparent_compositor_strips():
    app = DummyApp()
    async with app.run_test() as pilot:
        screen = app.screen
        strips = screen._compositor.render_strips()
        for strip in strips:
            for seg in strip:
                if seg.style:
                    assert seg.style.bgcolor is None, f"Found unexpected background: {seg.style.bgcolor}"
