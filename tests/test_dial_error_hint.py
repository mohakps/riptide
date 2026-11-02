from __future__ import annotations

from riptide.screens.create import friendly_dial_error


def test_dial_timeout_hint_names_firewall_and_port():
    err = friendly_dial_error(OSError(10060, "A connection attempt failed"), 50000)
    assert "10060" in err
    assert "firewall" in err
    assert "50000" in err
    assert "Create Server" in err


def test_dial_timeout_hint_for_timeout_error():
    err = friendly_dial_error(TimeoutError("timed out"), 50000)
    assert "firewall" in err
    assert "50000" in err


def test_dial_refused_hint():
    err = friendly_dial_error(ConnectionRefusedError("refused"), 50000)
    assert "not listening" in err
    assert "50000" in err


def test_dial_other_error_unchanged():
    err = friendly_dial_error(ValueError("bad host"), 50000)
    assert err == "bad host"
