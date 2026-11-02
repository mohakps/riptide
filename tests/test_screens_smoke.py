import pytest
from riptide.app import RiptideApp
from riptide.screens.menu import MenuScreen
from riptide.screens.join import JoinScreen
from riptide.screens.create import CreateScreen


class SmokeApp(RiptideApp):
    def on_mount(self):
        super().on_mount()


@pytest.mark.asyncio
async def test_screens_no_back_buttons():
    app = SmokeApp()
    async with app.run_test() as pilot:
        # JoinScreen (dialler)
        app.push_screen(JoinScreen())
        await pilot.pause()
        assert len(app.screen.query("#back")) == 0
        app.pop_screen()
        await pilot.pause()

        # CreateScreen (listener)
        app.push_screen(CreateScreen())
        await pilot.pause()
        assert len(app.screen.query("#back")) == 0
        app.pop_screen()
        await pilot.pause()
