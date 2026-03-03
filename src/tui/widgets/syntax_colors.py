from __future__ import annotations

from pygments.formatters import TerminalFormatter
from pygments.formatters.terminal import TERMINAL_COLORS
from pygments.token import Token

_POLAR_COLORSCHEME = dict(TERMINAL_COLORS)
_POLAR_COLORSCHEME[Token.Comment] = ("teal", "teal")
_POLAR_COLORSCHEME[Token.Comment.Preproc] = ("blue", "blue")
_POLAR_COLORSCHEME[Token.Comment.Special] = ("teal", "teal")


def build_terminal_formatter(theme_name: str) -> TerminalFormatter:
    """Create a terminal formatter tuned for app themes."""
    if theme_name == "polar":
        return TerminalFormatter(bg="light", colorscheme=_POLAR_COLORSCHEME)
    return TerminalFormatter(bg="dark")
