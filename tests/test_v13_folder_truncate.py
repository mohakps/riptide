from __future__ import annotations

from pathlib import Path

import pytest
from rich.cells import cell_len
from textual.app import App
from textual.widgets import Label

from riptide.screens.session_screen import (
    SessionScreen,
    _cell_len,
    _truncate_filename,
)
from riptide.theme import CSS


def test_truncate_counts_cells_not_characters():
    # 📁 is 1 character but 2 cells wide. A folder display
    # truncated to 32 characters was 33 cells wide, wrapped to
    # a second line, and the 1-line file row clipped it, so
    # folder names looked untruncated while file names fit.
    display = "📁 This_Is_A_Very_Long_Folder_Name_That_Should_Be_Truncated_When_Window_Is_Narrow/"
    truncated = _truncate_filename(display, 32)
    assert _cell_len(truncated) == 32
    assert cell_len(truncated) == 32
    assert "..." in truncated
    assert truncated.endswith("/")
    # Short names, and file names with no wide characters, unchanged.
    assert _truncate_filename("short.txt", 32) == "short.txt"
    assert _cell_len(_truncate_filename("a" * 100, 20)) == 20


class _DummySession:
    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.peer_device = "yoga"
        self.peer_host = "192.168.1.15"
        self.sock = None
        self.on_file_received = None
        self.on_ack = None
        self.on_error = None
        self.on_progress = None
        self.on_download_ask = None
        self.on_download_denied = None

    def start(self):
        pass

    def close(self):
        pass

    def send_file(self, path, on_progress=None):
        return True

    def request_download(self, name, request_id=""):
        return True


class _SessionApp(App):
    CSS = CSS

    def __init__(self, session):
        super().__init__()
        self._session = session

    def on_mount(self):
        self.push_screen(SessionScreen(self._session, "host"))


@pytest.mark.asyncio
async def test_folder_name_fits_one_line(tmp_path: Path):
    longfolder = "This_Is_A_Very_Long_Folder_Name_That_Should_Be_Truncated_When_Window_Is_Narrow"
    (tmp_path / longfolder).mkdir()
    (tmp_path / "short.txt").write_text("hi")
    app = _SessionApp(_DummySession(tmp_path))
    async with app.run_test(size=(80, 30)) as pilot:
        screen = app.screen
        await pilot.pause()
        for child in screen.query_one("#cwd_list").children:
            lab = child.query_one(".file-name", Label)
            txt = lab.render().plain
            if "Long_Folder" in txt or "..." in txt:
                # Fits its column in cells, and stays on one line.
                assert cell_len(txt) <= lab.region.width
                assert lab.region.height == 1
