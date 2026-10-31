import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riptide.core.focus import focus_first, handle_arrow_key, move_focus


class FakeWidget:
    def __init__(self, name):
        self.name = name
        self.disabled = False


class FakeApp:
    def __init__(self, screen):
        self.screen = screen

    def set_focus(self, widget):
        self.screen.focused = widget


class FakeScreen:
    def __init__(self, widgets):
        self.widgets = widgets
        self.focused = None
        self.app = FakeApp(self)

    def query(self, selector):
        return list(self.widgets)


def make_screen():
    return FakeScreen([FakeWidget("send"), FakeWidget("receive"), FakeWidget("setup")])


def test_down_moves_and_wraps():
    screen = make_screen()
    assert focus_first(screen)
    assert screen.focused.name == "send"
    assert handle_arrow_key(screen, "down")
    assert screen.focused.name == "receive"
    assert handle_arrow_key(screen, "down")
    assert screen.focused.name == "setup"
    assert handle_arrow_key(screen, "down")
    assert screen.focused.name == "send"


def test_up_wraps_from_first():
    screen = make_screen()
    focus_first(screen)
    assert handle_arrow_key(screen, "up")
    assert screen.focused.name == "setup"


def test_no_focus_starts_at_first_on_down():
    screen = make_screen()
    assert move_focus(screen, +1)
    assert screen.focused.name == "send"


def test_other_keys_not_handled():
    screen = make_screen()
    assert not handle_arrow_key(screen, "left")
