import pytest
from riptide.app import RiptideApp
from riptide.screens.menu import MenuScreen
from riptide.screens.create import CreateScreen
from riptide.screens.join import JoinScreen
from riptide.screens.setup import SetupScreen
from riptide.theme import TAGLINES


class SmokeApp(RiptideApp):
    def on_mount(self):
        super().on_mount()


@pytest.mark.asyncio
async def test_screen_taglines_and_no_back_buttons():
    app = SmokeApp()
    async with app.run_test() as pilot:
        # CreateScreen
        app.push_screen(CreateScreen())
        await pilot.pause()
        cs = app.screen
        labels = " ".join(node.render().plain for node in cs.query("Static, Label"))
        assert TAGLINES["create"] not in labels
        assert len(cs.query("#back")) == 0
        app.pop_screen()
        await pilot.pause()

        # SetupScreen
        app.push_screen(SetupScreen())
        await pilot.pause()
        ss = app.screen
        labels = " ".join(node.render().plain for node in ss.query("Static, Label"))
        assert TAGLINES["setup"] in labels
        assert len(ss.query("#back")) == 0
        app.pop_screen()
        await pilot.pause()
