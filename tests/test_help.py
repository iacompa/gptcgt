"""Tests for Help."""

from src.tui.overlays.help import HelpOverlay


def test_help_overlay_has_all_sections():
    # Structural check
    sections = set()
    for s, _, _ in HelpOverlay.SHORTCUTS:
        sections.add(s)

    assert "Navigation" in sections
    assert "AI & Tasks" in sections
    assert "Code Review" in sections
    assert "Settings" in sections
    assert "Slash Commands" in sections
