from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Blur, Enter, Key, MouseDown
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label


@dataclass
class MenuItem:
    """A single item in a dropdown menu."""

    label: str = ""
    action: str | None = None
    shortcut: str | None = None
    icon: str | None = None
    is_active: bool = False
    is_disabled: bool = False
    submenu: list["MenuItem"] | None = None
    is_separator: bool = False
    is_toggle: bool = False
    toggle_state: bool = False
    is_editable: bool = False
    edit_value: str = ""
    # Optional callback for direct execution without global actions
    callback: Callable[[], None] | None = None


class MenuAction(Message):
    """Fired when a menu item is selected that has an action."""

    def __init__(self, action: str) -> None:
        super().__init__()
        self.action = action


class MenuToggle(Message):
    """Fired when a toggle item is clicked."""

    def __init__(self, label: str, new_state: bool) -> None:
        super().__init__()
        self.label = label
        self.new_state = new_state


class MenuEdit(Message):
    """Fired when an editable item's value changes."""

    def __init__(self, label: str, new_value: str) -> None:
        super().__init__()
        self.label = label
        self.new_value = new_value


class MenuItemWidget(Widget):
    """Renders a single MenuItem visually."""

    DEFAULT_CSS = """
    MenuItemWidget {
        height: 1;
        layout: horizontal;
        padding: 0 1;
        background: transparent;
        color: $text;
    }

    MenuItemWidget:hover, MenuItemWidget.-focused {
        background: $primary;
        color: $text;
    }

    MenuItemWidget.-disabled {
        color: $text-disabled;
    }
    MenuItemWidget.-disabled:hover {
        background: transparent;
    }

    MenuItemWidget.-separator {
        height: 1;
        background: transparent;
        padding: 0;
        margin: 0;
        color: $secondary;
        text-align: center;
    }
    MenuItemWidget.-separator:hover {
        background: transparent;
    }

    MenuItemWidget .menu-icon { width: 3; }
    MenuItemWidget .menu-label { width: 1fr; overflow: hidden; }
    MenuItemWidget .menu-shortcut { width: auto; color: $text-muted; }
    MenuItemWidget .menu-arrow { width: 2; text-align: right; }
    MenuItemWidget Input {
        width: 15;
        height: 1;
        border: none;
        background: $surface-lighten-1;
        padding: 0 1;
    }
    """

    def __init__(self, item: MenuItem, parent_menu: "DropdownMenu") -> None:
        super().__init__()
        self.item = item
        self.parent_menu = parent_menu
        if item.is_separator:
            self.add_class("-separator")
        elif item.is_disabled:
            self.add_class("-disabled")

    def compose(self) -> ComposeResult:
        if self.item.is_separator:
            yield Label("─" * 50, classes="menu-separator-line")
            return

        icon_str = " "
        if self.item.is_toggle:
            icon_str = "☑ " if self.item.toggle_state else "☐ "
        elif self.item.is_active:
            icon_str = "✓ "
        elif self.item.icon:
            icon_str = f"{self.item.icon} "

        yield Label(icon_str, classes="menu-icon")

        if self.item.is_editable:
            yield Label(self.item.label + ": ", classes="menu-label")
            inp = Input(value=self.item.edit_value)
            yield inp
        else:
            yield Label(self.item.label, classes="menu-label")

        if self.item.shortcut:
            yield Label(self.item.shortcut, classes="menu-shortcut")

        if self.item.submenu:
            yield Label("▶", classes="menu-arrow")

    def on_mouse_down(self, event: MouseDown) -> None:
        event.stop()
        if self.item.is_separator or self.item.is_disabled:
            return

        if self.item.submenu:
            # Dropdown menu handles hover mostly, but click can trigger it too
            self.parent_menu.open_submenu(self)
            return

        if self.item.is_toggle:
            self.item.toggle_state = not self.item.toggle_state
            self.app.post_message(MenuToggle(self.item.label, self.item.toggle_state))
            # Just close it for now to avoid dealing with re-render weirdness
            self.parent_menu.close_all()
            return

        if self.item.is_editable:
            return  # Let the input handle it

        if self.item.action:
            self.app.post_message(MenuAction(self.item.action))

        if self.item.callback:
            self.item.callback()

        self.parent_menu.close_all()

    def on_enter(self, event: Enter) -> None:
        """Mouse hover."""
        if not self.item.is_separator and not self.item.is_disabled:
            self.parent_menu.focus_item(self)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.item.is_editable:
            self.item.edit_value = event.value

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.item.is_editable:
            self.app.post_message(MenuEdit(self.item.label, self.item.edit_value))
            self.parent_menu.close_all()


class DropdownMenu(Vertical):
    """A floating menu that overlays the main screen."""

    can_focus = True

    DEFAULT_CSS = """
    DropdownMenu {
        layer: overlay;
        width: auto;
        min-width: 36;
        height: auto;
        background: $surface;
        border: solid $panel-lighten-2;
        padding: 0;
        margin: 0;
    }
    """

    def __init__(
        self,
        items: list[MenuItem],
        x: int = 0,
        y: int = 0,
        parent_dropdown: "DropdownMenu | None" = None,
        source_widget: Widget | None = None,
    ) -> None:
        super().__init__()
        self.items = items
        self.spawn_x = x
        self.spawn_y = y
        self.parent_dropdown = parent_dropdown
        self.source_widget = source_widget
        self.active_submenu: "DropdownMenu | None" = None
        self.focused_index: int = -1
        self._item_widgets: list[MenuItemWidget] = []

        self.styles.offset = (x, y)
        self.styles.position = "absolute"

    def compose(self) -> ComposeResult:
        for item in self.items:
            w = MenuItemWidget(item, self)
            self._item_widgets.append(w)
            yield w

    def on_mount(self) -> None:
        # Keep it on screen
        self.call_after_refresh(self._enforce_bounds)
        self.focus()

    def _enforce_bounds(self) -> None:
        """Ensure menu stays within terminal dimensions."""
        if not self.is_mounted:
            return

        try:
            term_width = self.screen.size.width
            term_height = self.screen.size.height
        except Exception:
            # Catch NoScreen if node isn't fully rooted
            return
        my_width = self.outer_size.width
        my_height = self.outer_size.height

        new_x = self.spawn_x
        new_y = self.spawn_y

        if new_x + my_width > term_width:
            new_x = max(0, term_width - my_width)
            # If it's a submenu and we hit the right wall, open to the left of the parent
            if self.parent_dropdown:
                new_x = max(0, self.parent_dropdown.styles.offset.x.value - my_width)

        if new_y + my_height > term_height:
            new_y = max(0, term_height - my_height)

        self.styles.offset = (new_x, new_y)

    def close_all(self) -> None:
        if self.parent_dropdown:
            self.parent_dropdown.close_all()
        else:
            self._close_tree()

    def _close_tree(self) -> None:
        if self.active_submenu:
            self.active_submenu._close_tree()
        self.remove()

    def close_submenu(self) -> None:
        if self.active_submenu:
            self.active_submenu._close_tree()
            self.active_submenu = None
            self.focus()

    def open_submenu(self, item_widget: MenuItemWidget) -> None:
        if not item_widget.item.submenu:
            self.close_submenu()
            return

        if (
            self.active_submenu
            and getattr(self.active_submenu, "_source_item", None) == item_widget.item
        ):
            return

        self.close_submenu()

        # Spawn submenu beside this item
        # Calculate global offset using Region
        region = item_widget.region
        x = region.x + region.width - 1
        y = region.y - 1

        submenu = DropdownMenu(
            item_widget.item.submenu, x=x, y=y, parent_dropdown=self, source_widget=item_widget
        )
        submenu._source_item = item_widget.item
        self.active_submenu = submenu
        self.screen.mount(submenu)

    def focus_item(self, item_widget: MenuItemWidget) -> None:
        """Highlights the specified item and opens submenu."""
        try:
            new_idx = self._item_widgets.index(item_widget)
        except ValueError:
            return

        if self.focused_index >= 0 and self.focused_index < len(self._item_widgets):
            self._item_widgets[self.focused_index].remove_class("-focused")

        self.focused_index = new_idx
        item_widget.add_class("-focused")

        if item_widget.item.submenu:
            # We defer to avoid layout thrashing
            self.set_timer(0.1, lambda: self.open_submenu(item_widget))
        else:
            self.close_submenu()

    def on_key(self, event: Key) -> None:

        if event.key == "escape":
            self.close_all()
            event.stop()
            return

        if event.key == "left":
            if self.parent_dropdown:
                self.parent_dropdown.close_submenu()
            event.stop()
            return

        if event.key == "right" and self.focused_index >= 0:
            w = self._item_widgets[self.focused_index]
            if w.item.submenu:
                self.open_submenu(w)
                if self.active_submenu:
                    self.active_submenu.focus()
            event.stop()
            return

        if event.key == "down":
            self._move_focus(1)
            event.stop()
            return

        if event.key == "up":
            self._move_focus(-1)
            event.stop()
            return

        if event.key == "enter" and self.focused_index >= 0:
            # Simulate a mouse click on the item
            w = self._item_widgets[self.focused_index]
            click = MouseDown(
                x=0,
                y=0,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=0,
                screen_y=0,
            )
            w.post_message(click)
            event.stop()
            return

        # Jump to letter
        if len(event.character or "") == 1 and event.character.isalpha():
            char = event.character.lower()
            start = self.focused_index + 1
            for i in range(len(self._item_widgets)):
                idx = (start + i) % len(self._item_widgets)
                w = self._item_widgets[idx]
                if (
                    w.item.label.lower().startswith(char)
                    and not w.item.is_disabled
                    and not w.item.is_separator
                ):
                    self.focus_item(w)
                    break

    def _move_focus(self, direction: int) -> None:
        if not self._item_widgets:
            return

        start = (
            self.focused_index
            if self.focused_index >= 0
            else (0 if direction > 0 else len(self._item_widgets) - 1)
        )
        curr = start

        for _ in range(len(self._item_widgets)):
            if self.focused_index == -1:
                # First move just focuses the first element
                pass
            else:
                curr = (curr + direction) % len(self._item_widgets)

            w = self._item_widgets[curr]
            if not w.item.is_separator and not w.item.is_disabled:
                self.focus_item(w)
                return

    def on_blur(self, event: Blur) -> None:
        # If we lost focus to something that isn't a submenu, close everything
        # This is essentially a click-outside detector when combined with screen clicks
        pass
