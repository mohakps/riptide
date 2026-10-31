from riptide.theme import CSS, HEADER_BANNER, HEADER_LINES, TAGLINES


def test_css_is_transparent():
    assert "background: transparent" in CSS
    assert "#1E1E1E" not in CSS
    assert "#2A2A2A" not in CSS


def test_ansi_header_present():
    assert "██████╗" in HEADER_BANNER
    assert len(HEADER_LINES) == 6
    assert "RIPTIDE" in TAGLINES["home"] or "file transfer" in TAGLINES["home"]


def test_screen_taglines_defined():
    for key in ("home", "create", "join", "session", "setup"):
        assert key in TAGLINES
        assert len(TAGLINES[key]) > 10
