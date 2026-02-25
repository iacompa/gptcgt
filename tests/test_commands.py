import pytest

from src.core.commands import Command, CommandRegistry, register_default_commands


@pytest.fixture
def clean_registry():
    reg = CommandRegistry()
    reg._commands.clear()
    reg._by_shortcut.clear()
    reg._by_slash.clear()
    return reg


def test_registry_singleton(clean_registry):
    reg2 = CommandRegistry()
    assert clean_registry is reg2


def test_register_and_execute(clean_registry):
    executed = False

    def action():
        nonlocal executed
        executed = True

    cmd = Command("test.cmd", "Test", action, shortcut="ctrl+t", slash="/test")
    clean_registry.register(cmd)

    assert clean_registry.execute("test.cmd")
    assert executed


def test_execute_by_shortcut(clean_registry):
    executed = False

    def action():
        nonlocal executed
        executed = True

    cmd = Command("test.cmd", "Test", action, shortcut="ctrl+t", slash="/test")
    clean_registry.register(cmd)

    assert clean_registry.execute("ctrl+t")
    assert executed


def test_execute_by_slash(clean_registry):
    executed = False

    def action():
        nonlocal executed
        executed = True

    cmd = Command("test.cmd", "Test", action, shortcut="ctrl+t", slash="/test")
    clean_registry.register(cmd)

    assert clean_registry.execute("/test")
    assert executed


def test_search_commands(clean_registry):
    clean_registry.register(
        Command("file.new", "New File", lambda: None, description="Create file")
    )
    clean_registry.register(Command("file.save", "Save File", lambda: None))
    clean_registry.register(Command("settings", "Open Settings", lambda: None))

    res = clean_registry.search("file")
    assert len(res) == 2

    res = clean_registry.search("create")
    assert len(res) == 1
    assert res[0].id == "file.new"


def test_register_default_commands_integration(clean_registry):
    class MockChatStore:
        def new_session(self):
            pass

    class MockApp:
        def __init__(self):
            self.chat_store = MockChatStore()

        def action_toggle_left_panel(self):
            pass

        def action_toggle_right_panel(self):
            pass

        def action_toggle_zen_mode(self):
            pass

        def action_toggle_theme(self):
            pass

    app = MockApp()
    register_default_commands(app)

    assert len(clean_registry.get_all()) > 5
    assert clean_registry.execute("/zen") or clean_registry.execute("view.zen_mode")
