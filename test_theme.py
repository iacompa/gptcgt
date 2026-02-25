from textual.app import App, ComposeResult
from textual.widgets import Label


class TestApp(App):
    CSS_PATH = "src/tui/themes/midnight.tcss"
    def compose(self) -> ComposeResult:
        yield Label("Test Label")

    def on_mount(self):
        print(f"CSS sources: {list(self.stylesheet.source.keys())}")
        self.exit()

if __name__ == "__main__":
    TestApp().run(headless=True)
