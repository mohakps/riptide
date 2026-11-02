from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from riptide.screens.join import JoinScreen
from riptide.screens.create import CreateScreen
from riptide.theme import CSS


class _App(App):
    CSS = CSS
    def __init__(self, screen):
        super().__init__()
        self._screen = screen
    def on_mount(self):
        self.push_screen(self._screen)


@pytest.mark.asyncio
async def test_create_footer_and_keys():
    app = _App(CreateScreen())
    async with app.run_test() as pilot:
        screen = app.screen
        footer = screen.query_one("#footer_bar")
        text = " ".join(node.render().plain for node in footer.query("Label"))
        assert "[Space]" in text and "[Enter]" in text and "[Backspace]" in text and "[Esc]" in text
        # Backspace denies when waiting, Enter allows when waiting.
        screen._awaiting_approval = True
        screen._approved = False
        await pilot.press("backspace")
        assert screen._approved is False
        # _approve_event was set by deny handler, even though no thread waited.
        screen._awaiting_approval = True
        await pilot.press("enter")
        assert screen._approved is True


@pytest.mark.asyncio
async def test_create_screen_redesign():
    """Verify create screen redesign:
    - Omit unnecessary text.
    - Highlight incoming connection.
    - Enter accepts, backspace denies.
    - No up/down arrow keys.
    - Buttons same size with green/red backgrounds.
    """
    from textual.widgets import Button

    app = _App(CreateScreen())
    async with app.run_test() as pilot:
        screen = app.screen

        # 1. Omit unnecessary text
        all_text = " ".join(node.render().plain for node in screen.query("Static, Label"))

        # 2. Buttons same size and have green/red background
        btn_allow = screen.query_one("#allow", Button)
        btn_deny = screen.query_one("#deny", Button)
        assert btn_allow.styles.width == btn_deny.styles.width
        assert btn_allow.styles.height == btn_deny.styles.height
        assert btn_allow.styles.background.hex.upper() in ("#78DC8C", "#8EEC9F")
        assert btn_deny.styles.background.hex.upper() in ("#FF6B6B", "#FF8585")

        # 3. Highlight incoming connection
        card = screen.query_one("#incoming_card")
        assert "active" not in card.classes
        screen._show_incoming_connection("friend-pc", "abcd1234efgh5678")
        await pilot.pause()
        assert "active" in card.classes
        card_text = screen.query_one("#incoming").render().plain
        assert "INCOMING CONNECTION" in card_text
        assert "friend-pc" in card_text

        # 4. No up/down arrow keys
        focused_before = screen.focused
        await pilot.press("up")
        await pilot.press("down")
        assert screen.focused == focused_before

        # 5. Enter accepts, Backspace denies
        screen._awaiting_approval = True
        screen._approved = False
        await pilot.press("enter")
        assert screen._approved is True

        screen._awaiting_approval = True
        screen._approved = True
        await pilot.press("backspace")
        assert screen._approved is False
@pytest.mark.asyncio
async def test_join_footer_and_keys():
    app = _App(JoinScreen())
    async with app.run_test() as pilot:
        screen = app.screen
        footer = screen.query_one("#footer_bar")
        text = " ".join(node.render().plain for node in footer.query("Label"))
        assert "[↑/↓]" in text and "[Tab]" in text and "[Enter]" in text and "[Backspace]" in text and "[Esc]" in text
        # Backspace denies when waiting (input not focused).
        screen._awaiting_approval = True
        screen._approved = False
        # Focus something not input, so backspace is a deny, not a delete.
        screen.query_one("#join").focus()
        await pilot.press("backspace")
        assert screen._approved is False


@pytest.mark.asyncio
async def test_join_screen_redesign():
    """Verify join screen redesign:
    - Omit unnecessary text.
    - Saved devices is an unordered list, not buttons.
    - By default, select the first saved device.
    - Up/down navigates between saved devices.
    - Grey font color by default, red for focused device.
    - Position hostname input field at 3/4 vertically and centered horizontally.
    - Tab cycles between saved devices and hostname input field.
    - When hostname input is focused, saved devices are not highlighted.
    - Enter establishes connection with selected device or entered hostname.
    """
    from riptide.core.config import Peer
    from riptide.screens.join import SavedDevicesList
    from textual.widgets import Button, Input, Static

    screen = JoinScreen()
    # Inject test peers to test full device list functionality
    screen._peers = [
        Peer(name="alpha", host="192.168.1.10"),
        Peer(name="beta", host="192.168.1.20"),
        Peer(name="gamma", host="192.168.1.30"),
    ]
    screen.config.peers = list(screen._peers)

    app = _App(screen)
    async with app.run_test(size=(100, 40)) as pilot:
        cs = app.screen

        # 1. Unnecessary text is removed
        all_text = " ".join(node.render().plain for node in cs.query("Static, Label"))
        assert "Recent peers · select to autofill destination:" not in all_text

        # 2. Saved devices is an unordered list instead of buttons
        assert not any((b.id or "").startswith("peer_") for b in cs.query(Button))
        dev_list = cs.query_one("#saved_devices", SavedDevicesList)
        dev_items = dev_list.query(".device-item")
        assert len(dev_items) == 3
        for item in dev_items:
            assert item.render().plain.startswith("• ")

        # 3. By default, select first saved device
        assert cs.focused == dev_list
        assert dev_list.selected_index == 0
        item0 = cs.query_one("#device_item_0", Static)
        item1 = cs.query_one("#device_item_1", Static)
        item2 = cs.query_one("#device_item_2", Static)

        # 4. Red for focused device, grey by default
        assert any(span.style == "bold #FF6B6B" for span in item0.render().spans)
        assert any(span.style == "#D7D7D7" for span in item1.render().spans)
        assert any(span.style == "#D7D7D7" for span in item2.render().spans)

        # 5. Up/down navigates between devices
        await pilot.press("down")
        assert dev_list.selected_index == 1
        assert any(span.style == "#D7D7D7" for span in item0.render().spans)
        assert any(span.style == "bold #FF6B6B" for span in item1.render().spans)

        await pilot.press("down")
        assert dev_list.selected_index == 2
        assert any(span.style == "bold #FF6B6B" for span in item2.render().spans)

        await pilot.press("up")
        assert dev_list.selected_index == 1
        assert any(span.style == "bold #FF6B6B" for span in item1.render().spans)

        # 6. Tab to cycle between saved devices and hostname input
        host_input = cs.query_one("#host", Input)
        await pilot.press("tab")
        assert cs.focused == host_input

        # 7. When hostname input is focused, don't highlight saved devices (all grey)
        assert any(span.style == "#D7D7D7" for span in item0.render().spans)
        assert any(span.style == "#D7D7D7" for span in item1.render().spans)
        assert any(span.style == "#D7D7D7" for span in item2.render().spans)
        assert not any(span.style == "bold #FF6B6B" for span in item1.render().spans)

        # Tab back to saved devices
        await pilot.press("tab")
        assert cs.focused == dev_list
        # Highlight restored to selected device
        assert any(span.style == "bold #FF6B6B" for span in item1.render().spans)

        # 8. Hostname input positioned at 3/4 vertically and centered horizontally,
        # now larger: 80 wide, 5 tall, with a label above it.
        region = host_input.region
        # Centered horizontally: 100 screen width, input width 80, so x should be around (100-80)/2 = 10
        assert 5 <= region.x <= 15
        assert region.width == 80
        assert region.height == 5
        # 3/4 vertically: 40 screen height, 3/4 is 30, region.y + region.height is around 30
        assert 20 <= region.y <= 30

        # 9. Enter to establish connection with selected device or entered hostname
        started_hosts: list[str] = []
        cs._start = lambda host_override=None: started_hosts.append(
            host_override or (dev_list.selected_device.host if cs.focused == dev_list else host_input.value.strip())
        )
        # With dev_list focused:
        await pilot.press("enter")
        assert started_hosts[-1] == "192.168.1.20"

        # Focus host input, enter custom hostname, press enter:
        await pilot.press("tab")
        host_input.value = "10.0.0.99"
        await pilot.press("enter")
        assert started_hosts[-1] == "10.0.0.99"
