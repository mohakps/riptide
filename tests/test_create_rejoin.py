import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from textual.app import App
from textual.widgets import Static

from riptide.core.session import join_session
from riptide.screens.create import CreateScreen
from riptide.screens.session_screen import SessionScreen
from riptide.theme import CSS


class _App(App):
    CSS = CSS

    def __init__(self, screen):
        super().__init__()
        self._screen = screen

    def on_mount(self):
        self.push_screen(self._screen)


async def _wait_until(pilot, cond, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await pilot.pause()
        if cond():
            return True
    await pilot.pause()
    return cond()


def _dial(tmp_path, label, store):
    # A real client in a thread: TLS handshake, signed hello
    # challenge, then it waits for the host to approve.
    def run():
        try:
            client = join_session(
                "127.0.0.1", 50000, tmp_path / f"client-{label}", device=f"phone-{label}",
                home=tmp_path / f"chome-{label}", approve_fingerprint=lambda fp: True,
            )
            client.start()
            store["client"] = client
        except Exception as exc:  # noqa: BLE001 - collected, asserted below
            store["error"] = exc

    threading.Thread(target=run, daemon=True).start()


@pytest.mark.asyncio
async def test_create_rearms_listener_after_disconnect(tmp_path):
    # After a session ends, the Create screen must listen again, so
    # a peer can rejoin without restarting Create Server. Before
    # this fix wait_for_client ran once and the worker never looped.
    (tmp_path / "client-one").mkdir()
    (tmp_path / "client-two").mkdir()
    app = _App(CreateScreen())
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, CreateScreen)

        first = {}
        _dial(tmp_path, "one", first)
        assert await _wait_until(
            pilot, lambda: "INCOMING CONNECTION REQUEST" in screen.query_one("#incoming", Static).render().plain
        ), "first client did not reach the approval card"
        await pilot.press("enter")
        assert await _wait_until(pilot, lambda: isinstance(app.screen, SessionScreen)), "session screen did not open"
        assert first.get("client") is not None, first.get("error")

        # The phone taps Disconnect: bye, then the socket closes.
        # The PC must return to the Create screen, showing that the
        # peer disconnected, with the listener waiting again.
        first["client"].close()
        assert await _wait_until(pilot, lambda: isinstance(app.screen, CreateScreen)), "did not return to Create after disconnect"
        await pilot.pause()
        status = screen.query_one("#incoming", Static).render().plain
        assert "Peer disconnected" in status
        assert "Waiting for client" in status

        # A second client must reach the approval card again, with
        # no restart of Create Server, and be accepted the same way.
        second = {}
        _dial(tmp_path, "two", second)
        assert await _wait_until(
            pilot, lambda: "INCOMING CONNECTION REQUEST" in screen.query_one("#incoming", Static).render().plain
        ), "second client did not reach the approval card: listener was not re-armed"
        await pilot.press("enter")
        assert await _wait_until(pilot, lambda: isinstance(app.screen, SessionScreen)), "rejoined session screen did not open"
        assert second.get("client") is not None, second.get("error")

        second["client"].close()
        assert await _wait_until(pilot, lambda: isinstance(app.screen, CreateScreen)), "did not return to Create after second disconnect"
