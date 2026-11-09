from __future__ import annotations

import ipaddress
import struct

import pytest
from textual.app import App
from textual.widgets import Static

from riptide.core.config import DEFAULT_SESSION_PORT, load_config, save_config
from riptide.core.nat import _xor_mapped_address
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


def _stun_response_for(ip: str) -> bytes:
    # A synthetic Binding Success Response carrying one
    # XOR-MAPPED-ADDRESS attribute for the given address, with the
    # same all-zero transaction ID the client sends.
    addr = ipaddress.ip_address(ip)
    tid = bytes(12)
    key = struct.pack(">I", 0x2112A442) + tid
    if addr.version == 4:
        xaddr = bytes(b ^ k for b, k in zip(addr.packed, struct.pack(">I", 0x2112A442)))
        val = b"\x00\x01" + struct.pack(">H", 50000 ^ 0x2112) + xaddr
    else:
        xaddr = bytes(b ^ key[i] for i, b in enumerate(addr.packed))
        val = b"\x00\x02" + struct.pack(">H", 50000 ^ 0x2112) + xaddr
    header = struct.pack(">HHI", 0x0101, len(val) + 4, 0x2112A442) + tid
    return header + struct.pack(">HH", 0x0020, len(val)) + val


def test_xor_mapped_address_ipv4():
    assert _xor_mapped_address(_stun_response_for("203.0.113.10"), bytes(12)) == "203.0.113.10"


def test_xor_mapped_address_ipv6():
    assert (
        _xor_mapped_address(_stun_response_for("240b:1:2:3:4:5:6:7"), bytes(12))
        == "240b:1:2:3:4:5:6:7"
    )


def test_xor_mapped_address_absent():
    header = struct.pack(">HHI", 0x0101, 0, 0x2112A442) + bytes(12)
    assert _xor_mapped_address(header, bytes(12)) is None


@pytest.mark.asyncio
async def test_create_page_shows_public_ipv6_widget():
    app = _App(CreateScreen())
    async with app.run_test(size=(100, 40)) as pilot:
        screen = app.screen
        widget = screen.query_one("#public_ipv6", Static)
        assert "Your IPv6 address" in widget.render().plain
        screen._update_public_ipv6("240b:1:2:3:4:5:6:7")
        assert widget.display is True
        assert "240b:1:2:3:4:5:6:7" in widget.render().plain
        # No IPv6 on the host: the row hides instead of showing a
        # dead line, so the screen stays IPv4-only.
        screen._update_public_ipv6(None)
        assert widget.display is False
