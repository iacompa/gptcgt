from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Label

__test__ = False


class TestApp(App):
    CSS = "Label { background: blue; padding: 2; }"
    BINDINGS = [Binding("t", "swap", "Swap")]

    def compose(self) -> ComposeResult:
        yield Label("Test")

    def action_swap(self):
        keys = list(self.stylesheet.source.keys())
        for k in keys:
            del self.stylesheet.source[k]
        self.stylesheet.add_source(
            "Label { background: red; padding: 4; }",
            read_from=("test", "test"),
            is_default_css=False,
            tie_breaker=0,
        )
        self.stylesheet.reparse()
        self.stylesheet.update(self)
        self.refresh(layout=True)
        self.exit()

if __name__ == "__main__":
    app = TestApp()
    async def test():
        async with app.run_test(headless=True) as pilot:
            await pilot.press("t")
            await pilot.pause()

    import asyncio
    asyncio.run(test())
