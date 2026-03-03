"""Tests for CommandRegistry.resolve_slash and new slash command registrations."""

import pytest

from src.core.commands import Command, CommandRegistry


@pytest.fixture(autouse=True)
def fresh_registry():
    """Reset the singleton so each test starts clean."""
    CommandRegistry._instance = None
    yield
    CommandRegistry._instance = None


class TestResolveSlash:
    """Tests for the argument-aware slash dispatch method."""

    def test_known_command_no_args(self):
        reg = CommandRegistry()
        reg.register(Command(
            id="chat.help", title="Help", action=lambda: None, slash="/help"
        ))
        cmd, args = reg.resolve_slash("/help")
        assert cmd is not None
        assert cmd.id == "chat.help"
        assert args == []

    def test_known_command_with_args(self):
        reg = CommandRegistry()
        reg.register(Command(
            id="chat.mode", title="Mode", action=lambda: None, slash="/mode"
        ))
        cmd, args = reg.resolve_slash("/mode architect")
        assert cmd is not None
        assert cmd.id == "chat.mode"
        assert args == ["architect"]

    def test_known_command_with_multiple_args(self):
        reg = CommandRegistry()
        reg.register(Command(
            id="test.multi", title="Multi", action=lambda: None, slash="/multi"
        ))
        cmd, args = reg.resolve_slash("/multi arg1 arg2 arg3")
        assert args == ["arg1", "arg2", "arg3"]

    def test_unknown_command_returns_none(self):
        reg = CommandRegistry()
        cmd, args = reg.resolve_slash("/nonexistent")
        assert cmd is None
        assert args == []

    def test_case_insensitive(self):
        reg = CommandRegistry()
        reg.register(Command(
            id="chat.help", title="Help", action=lambda: None, slash="/help"
        ))
        cmd, args = reg.resolve_slash("/HELP")
        assert cmd is not None
        assert cmd.id == "chat.help"

    def test_empty_string(self):
        reg = CommandRegistry()
        cmd, args = reg.resolve_slash("")
        assert cmd is None
        assert args == []

    def test_quoted_args(self):
        reg = CommandRegistry()
        reg.register(Command(
            id="test.quoted", title="Quoted", action=lambda: None, slash="/test"
        ))
        cmd, args = reg.resolve_slash('/test "hello world"')
        assert args == ["hello world"]


class TestGetSlashCommands:
    """Tests for the get_slash_commands helper."""

    def test_returns_only_slash_commands(self):
        reg = CommandRegistry()
        reg.register(Command(id="file.new", title="New", action=lambda: None, shortcut="ctrl+n"))
        reg.register(Command(id="chat.help", title="Help", action=lambda: None, slash="/help"))
        slashes = reg.get_slash_commands()
        assert len(slashes) == 1
        assert slashes[0].id == "chat.help"

    def test_excludes_invisible_commands(self):
        reg = CommandRegistry()
        reg.register(Command(
            id="hidden", title="Hidden", action=lambda: None, slash="/hidden", visible=False
        ))
        slashes = reg.get_slash_commands()
        assert len(slashes) == 0


class TestNewCommandRegistrations:
    """Ensure the new commands from register_default_commands are present."""

    def test_register_default_commands_includes_new_slashes(self):
        from unittest.mock import MagicMock

        from src.core.commands import register_default_commands

        app = MagicMock()
        app.chat_store = MagicMock()
        app.chat_store.new_session = MagicMock()
        register_default_commands(app)

        reg = CommandRegistry()
        expected_slashes = {"/export", "/compact", "/cost", "/context", "/mode"}
        registered_slashes = {cmd.slash for cmd in reg.get_all() if cmd.slash}
        assert expected_slashes.issubset(registered_slashes)
