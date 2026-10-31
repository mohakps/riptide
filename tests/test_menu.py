import pytest
from textual.app import App
from riptide.screens.menu import MenuScreen
from riptide import __version__


class DummyApp(App):
    def on_mount(self):
        self.push_screen(MenuScreen())


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
