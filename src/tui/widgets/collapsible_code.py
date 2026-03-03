"""
Collapsible code block widget for agent responses.

Parses streaming or static markdown to identify code blocks and render them
using Textual's Collapsible widget containing a Static widget with syntax highlighting.
"""

from __future__ import annotations

from dataclasses import dataclass

from pygments import highlight
from pygments.lexers import TextLexer, get_lexer_by_name
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Collapsible, Static

from src.core.logger import get_logger
from src.tui.widgets.syntax_colors import build_terminal_formatter

logger = get_logger("tui.collapsible_code")


@dataclass
class ParsedBlock:
    """Represents a block of parsed markdown (either text or code)."""

    is_code: bool
    content: str
    language: str = ""


class CollapsibleCodeBlock(Vertical):
    """
    A wrapper around Textual's Collapsible for code blocks.

    Syntax highlights the code based on the provided language and
    provides a copy mechanism (if needed) or just syntax-colored display.
    """

    DEFAULT_CSS = """
    CollapsibleCodeBlock {
        width: auto;
        min-width: 100%;
        height: auto;
        margin: 1 0;
    }
    .collapsible-code-content {
        padding: 1 2;
        background: $surface;
        border: solid $secondary;
        width: auto;
        min-width: 100%;
        height: auto;
    }
    """

    def __init__(self, language: str, code: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._language = language
        self._code = code

    def compose(self) -> ComposeResult:
        try:
            lexer = get_lexer_by_name(self._language)
        except Exception:
            lexer = TextLexer()

        formatter = build_terminal_formatter(getattr(self.app, "theme", "midnight"))
        highlighted = highlight(self._code, lexer, formatter)

        title = f"Code: {self._language}" if self._language else "Code"
        with Collapsible(title=title, collapsed=True):
            yield Static(highlighted, classes="collapsible-code-content")


def parse_agent_response(text: str) -> list[ParsedBlock]:
    """Parse a complete markdown string into alternating text and code blocks."""
    blocks = []
    lines = text.split("\n")
    in_code_block = False
    current_content = []
    current_language = ""

    for line in lines:
        if line.startswith("```"):
            if in_code_block:
                # End of code block
                blocks.append(
                    ParsedBlock(
                        is_code=True,
                        content="\n".join(current_content),
                        language=current_language,
                    )
                )
                current_content = []
                current_language = ""
                in_code_block = False
            else:
                # Start of code block
                if current_content:
                    blocks.append(
                        ParsedBlock(
                            is_code=False,
                            content="\n".join(current_content),
                        )
                    )
                    current_content = []
                in_code_block = True
                current_language = line[3:].strip()
        else:
            current_content.append(line)

    # Any remaining content
    if current_content:
        blocks.append(
            ParsedBlock(
                is_code=in_code_block,
                content="\n".join(current_content),
                language=current_language if in_code_block else "",
            )
        )

    return blocks


class StreamingCodeParser:
    """
    Stateful parser for identifying code blocks during a streaming response.

    Yields chunks of text or metadata indicating code block transitions so the
    UI can mount Textual `CollapsibleCodeBlock` widgets dynamically.
    """

    def __init__(self) -> None:
        self.in_code_block: bool = False
        self.current_language: str = ""
        self.buffer: str = ""
        self.code_buffer: list[str] = []

    def feed(self, chunk: str) -> list[tuple[str, str | dict]]:
        """
        Feed a new chunk of raw text and return parsed events.

        Events format:
            ("text", "normal text chunk")
            ("code_start", {"language": "python"})
            ("code_chunk", "print('hello')")
            ("code_end", {"full_code": "...code...", "language": "python"})
        """
        self.buffer += chunk
        events = []

        # Keep processing complete lines
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)

            if line.startswith("```"):
                if self.in_code_block:
                    # End of code block
                    self.in_code_block = False
                    full_code = "\n".join(self.code_buffer)
                    events.append(
                        (
                            "code_end",
                            {"full_code": full_code, "language": self.current_language},
                        )
                    )
                    self.code_buffer = []
                    self.current_language = ""
                    # Also append a newline for text to space out the block
                    events.append(("text", "\n"))
                else:
                    # Start of code block
                    self.in_code_block = True
                    self.current_language = line[3:].strip()
                    events.append(("code_start", {"language": self.current_language}))
            else:
                if self.in_code_block:
                    self.code_buffer.append(line)
                    # We can optionally emit live code chunks here
                    # Events.append(("code_chunk", line + "\n"))
                else:
                    events.append(("text", line + "\n"))

        return events

    def finalize(self) -> list[tuple[str, str | dict]]:
        """Process any remaining buffer at the end of the stream."""
        events = []
        if self.buffer:
            if self.in_code_block:
                self.code_buffer.append(self.buffer)
                full_code = "\n".join(self.code_buffer)
                events.append(
                    (
                        "code_end",
                        {"full_code": full_code, "language": self.current_language},
                    )
                )
            else:
                events.append(("text", self.buffer))
        self.buffer = ""
        self.code_buffer = []
        self.in_code_block = False
        return events
