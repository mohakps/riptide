from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Static

from riptide.core.config import DEFAULT_SESSION_PORT, load_config, save_config
from riptide.screens.create import CreateScreen
from riptide.theme import CSS


class _App(App):
    CSS = CSS
    def __init__(self, screen):
        super().__init__()
        self._screen = screen
    def on_mount(self):
        self.push_screen(self._screen)


def test_default_port_is_50000_and_custom_port_preserved(tmp_path):
    assert DEFAULT_SESSION_PORT == 50000
    assert load_config(home=tmp_path).session_port == 50000
    (tmp_path / ".riptide").mkdir()
    # No legacy migration any more: a saved port is kept as-is,
    # whether it is 49872 or any other custom port.
    (tmp_path / ".riptide" / "config.toml").write_text("session_port = 49872\n")
    assert load_config(home=tmp_path).session_port == 49872
    (tmp_path / ".riptide" / "config.toml").write_text("session_port = 49999\n")
    assert load_config(home=tmp_path).session_port == 49999


@pytest.mark.asyncio
async def test_create_page_shows_public_ip_widget():
    app = _App(CreateScreen())
    async with app.run_test(size=(100, 40)) as pilot:
        screen = app.screen
        widget = screen.query_one("#public_ip", Static)
        assert "Your public address" in widget.render().plain
        screen._update_public_ip("203.0.113.10")
        assert "203.0.113.10" in widget.render().plain
        screen._update_public_ip(None)
        assert "could not be determined" in widget.render().plain
