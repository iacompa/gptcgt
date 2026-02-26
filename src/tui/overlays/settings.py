from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Select,
    TabbedContent,
    TabPane,
)

from src.auth.keychain import KeyChainManager
from src.core.logger import get_logger
from src.tui.panels.chat import apply_brand_colors

logger = get_logger("tui.settings")


class SettingsScreen(ModalScreen):
    """Tabbed settings screen (API keys, Appearance, Behavior, Billing, About)."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close Settings"),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
        background: $background 80%;
    }
    #settings-dialog {
        width: 95%;
        max-width: 120;
        height: 85%;
        background: $panel;
        border: solid $secondary;
        padding: 1 2;
    }
    .settings-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
        border-bottom: solid $secondary;
        padding-bottom: 1;
    }
    .provider-row {
        height: auto;
        min-height: 3;
        margin-bottom: 1;
        align: left middle;
    }
    .provider-name {
        width: 14;
        content-align: left middle;
    }
    .provider-input {
        width: 1fr;
        min-width: 15;
    }
    .provider-status {
        width: 22;
        content-align: right middle;
    }
    .provider-btns {
        width: 9;
        min-width: 9;
        height: 3;
        margin-left: 1;
        content-align: center middle;
    }
    .provider-validate-btn {
        width: 11;
        min-width: 11;
        height: 3;
        margin-left: 1;
        content-align: center middle;
    }
    .settings-actions {
        height: auto;
        min-height: 4;
        margin-top: 1;
        border-top: solid $secondary;
        padding-top: 1;
        dock: bottom;
        width: 100%;
        align: center middle;
    }
    .settings-actions Button {
        margin: 0 2;
        content-align: center middle;
    }
    .section-label {
        color: $primary;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }
    .hint-text {
        color: $text-muted;
        padding-left: 1;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Label("Settings", classes="settings-title")
            with TabbedContent(initial="tab-api"):
                with TabPane("API Keys", id="tab-api"):
                    with VerticalScroll():
                        yield from self._compose_api_tab()
                with TabPane("Models", id="tab-models"):
                    with VerticalScroll():
                        yield from self._compose_models_tab()
                with TabPane("Appearance", id="tab-appearance"):
                    with VerticalScroll():
                        yield from self._compose_appearance_tab()
                with TabPane("Behavior", id="tab-behavior"):
                    with VerticalScroll():
                        yield from self._compose_behavior_tab()
                with TabPane("Billing", id="tab-billing"):
                    with VerticalScroll():
                        yield from self._compose_billing_tab()
                with TabPane("About", id="tab-about"):
                    with VerticalScroll():
                        yield from self._compose_about_tab()

            with Horizontal(classes="settings-actions"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Save & Close", id="btn-save", variant="primary")

    def _compose_api_tab(self):
        yield Label(
            "🔐 Keys are stored in your OS keychain, never in plain files.", classes="text-secondary"
        )
        yield Label(
            "Paste a key and click [bold]Test[/bold] to validate it live against the API.",
            classes="hint-text",
        )
        providers = [
            ("Anthropic", "ANTHROPIC_API_KEY", "https://console.anthropic.com/settings/keys"),
            ("OpenAI", "OPENAI_API_KEY", "https://platform.openai.com/api-keys"),
            ("Google", "GEMINI_API_KEY", "https://aistudio.google.com/app/apikey"),
            ("xAI", "XAI_API_KEY", "https://console.x.ai/"),
            ("DeepSeek", "DEEPSEEK_API_KEY", "https://platform.deepseek.com/api_keys"),
            ("OpenRouter", "OPENROUTER_API_KEY", "https://openrouter.ai/keys"),
        ]

        mapping = {
            "Anthropic": "Claude",
            "OpenAI": "GPT",
            "Google": "Gemini",
            "xAI": "Grok",
        }

        for name, var_name, _docs_url in providers:
            with Horizontal(classes="provider-row"):
                display_name = mapping.get(name, name)
                colored_name = apply_brand_colors(display_name)
                yield Label(colored_name, classes="provider-name")
                existing_key = KeyChainManager.get_key(var_name)
                stat_text = "✅ Saved" if existing_key else "⬚ Not set"
                placeholder = "sk-ant-••••••••" if existing_key else f"Enter {name} key"
                yield Input(
                    placeholder=placeholder,
                    password=True,
                    classes="provider-input",
                    id=f"settings-key-{var_name}",
                )
                yield Label(stat_text, classes="provider-status", id=f"settings-stat-{var_name}")
                yield Button(
                    "Test", id=f"btn-test-{var_name}", classes="provider-validate-btn", variant="default"
                )
                yield Button(
                    "🗑", id=f"btn-clear-{var_name}", classes="provider-btns", variant="default"
                )

    def _compose_models_tab(self):
        yield Label("Model Overrides", classes="section-label")
        yield Label(
            "Enter any valid LiteLLM model ID. These override automatic tier routing.\n"
            "Leave blank to use the default for your tier.",
            classes="hint-text",
        )

        c = self.app.config.user

        yield Label("Orchestrator Model:")
        yield Input(
            value=getattr(c, "orchestrator_model", ""),
            placeholder="e.g. openai/gpt-4o  or  anthropic/claude-3-5-sonnet-20241022",
            id="settings-orchestrator"
        )

        yield Label("Coder Model:")
        yield Input(
            value=getattr(c, "coder_model", ""),
            placeholder="e.g. anthropic/claude-3-5-sonnet-20241022  or  openai/o3-mini",
            id="settings-coder"
        )

        yield Label("Arbiter (Judge) Model:")
        yield Input(
            value=getattr(c, "arbiter_model", ""),
            placeholder="e.g. openrouter/meta-llama/llama-3-70b-instruct",
            id="settings-arbiter"
        )

        yield Label("Architect (Planning) Model:")
        yield Input(
            value=getattr(c, "architect_model", ""),
            placeholder="e.g. anthropic/claude-3-7-sonnet-20250219",
            id="settings-architect"
        )

        yield Label("Scout (Exploration) Model:")
        yield Input(
            value=getattr(c, "scout_model", ""),
            placeholder="e.g. openai/o3-mini",
            id="settings-scout"
        )

        yield Label("Tester (QA) Model:")
        yield Input(
            value=getattr(c, "tester_model", ""),
            placeholder="e.g. google/gemini-2.5-pro",
            id="settings-tester"
        )

        yield Label("\nFallback Quality Tier (when model fields above are blank):")
        tier_opts = [
            ("💡 Light — Fast & cheap (~$0.01/task)", "light"),
            ("⚡ Standard — Balanced (~$0.04/task)", "standard"),
            ("🔥 Max — Best quality (~$0.12/task)", "max"),
        ]
        current_tier = getattr(self.app.config.user, "quality_tier", "standard")
        yield Select(tier_opts, value=current_tier, id="settings-tier")

    def _compose_appearance_tab(self):
        yield Label("Theme:")
        theme = self.app.config.user.theme
        opts = [(t.capitalize(), t) for t in ["midnight", "polar", "slate", "ember", "neon"]]
        yield Select(opts, value=theme, id="settings-theme")

        yield Label("\nLayout Sequence (Restart Required):")
        layout = getattr(self.app.config.user, "layout_order", "files_code_chat")
        layout_opts = [
            ("Files | Code | Chat (Default)", "files_code_chat"),
            ("Code | Chat | Files", "code_chat_files"),
            ("Chat | Code | Files", "chat_code_files"),
            ("Files | Chat | Code", "files_chat_code"),
            ("Chat | Files | Code", "chat_files_code"),
            ("Code | Files | Chat", "code_files_chat"),
        ]
        yield Select(layout_opts, value=layout, id="settings-layout")

    def _compose_behavior_tab(self):
        c = self.app.config.user
        yield Checkbox(
            "Confirm before writing files to disk",
            value=c.confirm_before_apply,
            id="settings-confirm",
        )
        yield Checkbox(
            "Run auto security scan on AI code", value=c.auto_security_scan, id="settings-scan"
        )
        yield Checkbox(
            "Show cost breakdown after each task", value=c.show_cost_after_task, id="settings-cost"
        )

    def _compose_billing_tab(self):
        c = self.app.config.user

        # Plan header
        import textual.app as _tapp
        try:
            current_app = _tapp.active_app.get()
            am = getattr(current_app, "auth_manager", None)
            plan = getattr(am, "user_plan", "byok").upper() if am else "BYOK"
            credits = getattr(am, "credits_remaining", None)
            month_credits = getattr(am, "credits_monthly", None)
            is_auth = getattr(am, "is_authenticated", False)
        except Exception:
            plan, credits, month_credits, is_auth = "BYOK", None, None, False

        if is_auth and credits is not None:
            yield Label(f"Plan: [bold]{plan}[/bold]  •  {credits}/{month_credits} credits remaining", classes="section-label")
        else:
            yield Label("Plan: [bold]Bring Your Own Keys[/bold] (Free)", classes="section-label")
            yield Label(
                "Sign in at gptcgt.ai/pricing for managed credits and Pro plan.",
                classes="hint-text",
            )

        yield Label("\nSpend Controls:", classes="section-label")
        yield Checkbox(
            "Enable overage billing (pay-as-you-go beyond plan)",
            value=c.overage_enabled,
            id="settings-overage",
        )
        yield Checkbox(
            "Auto-downgrade to Light tier when limit is reached",
            value=c.auto_downgrade_on_limit,
            id="settings-downgrade",
        )

        yield Label("\nHistory & Receipts:", classes="section-label")
        yield Button("View Receipt History", id="btn-receipts", variant="default")
        yield Button("Open Billing Portal →", id="btn-billing-portal", variant="default")

    def _compose_about_tab(self):
        yield Label("gptcgt by IA Compa LLC", classes="text-style-bold")
        yield Label("Version 0.1.0")
        yield Label("The multi-model AI coding terminal.\n", classes="text-secondary")
        yield Button("View Documentation →", id="btn-docs", variant="default")
        yield Button("Report an Issue →", id="btn-issues", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-save":
            self._save_settings()
            self.dismiss()
        elif event.button.id and event.button.id.startswith("btn-clear-"):
            var_name = event.button.id.replace("btn-clear-", "")
            KeyChainManager.clear_key(var_name)
            self.query_one(f"#settings-stat-{var_name}", Label).update("⬚ Not set")
            self.query_one(f"#settings-key-{var_name}", Input).value = ""
        elif event.button.id and event.button.id.startswith("btn-test-"):
            var_name = event.button.id.replace("btn-test-", "")
            inp = self.query_one(f"#settings-key-{var_name}", Input)
            stat = self.query_one(f"#settings-stat-{var_name}", Label)
            key_val = inp.value.strip() or KeyChainManager.get_key(var_name) or ""
            if not key_val:
                stat.update("⬚ No key entered")
                return
            stat.update("🔄 Testing...")
            self.app.run_worker(self._validate_key_live(var_name, key_val, stat))
        elif event.button.id == "btn-receipts":
            from src.tui.overlays.receipt import ReceiptOverlay
            try:
                self.app.push_screen(ReceiptOverlay())
            except Exception:
                from src.tui.widgets.toast import notify
                notify(self.app, "Receipts", "No receipt history yet.", "info")
        elif event.button.id == "btn-billing-portal":
            import webbrowser
            webbrowser.open("https://gptcgt.ai/billing")
        elif event.button.id == "btn-docs":
            import webbrowser
            webbrowser.open("https://docs.gptcgt.ai")
        elif event.button.id == "btn-issues":
            import webbrowser
            webbrowser.open("https://github.com/your/repo/issues")

    async def _validate_key_live(
        self, var_name: str, key_val: str, stat_label: Label
    ) -> None:
        """Live API key validation matching the onboarding flow."""
        try:
            from src.auth.key_validator import KeyValidator
            is_valid, msg = await KeyValidator.validate(var_name, key_val)

            if not is_valid:
                stat_label.update(f"❌ {msg}")
                return

            stat_label.update("🔄 Testing API...")
            prov_map = {
                "ANTHROPIC_API_KEY": "anthropic",
                "OPENAI_API_KEY": "openai",
                "GEMINI_API_KEY": "google",
                "XAI_API_KEY": "xai",
                "DEEPSEEK_API_KEY": "deepseek",
                "OPENROUTER_API_KEY": "openrouter",
            }
            provider_name = prov_map.get(var_name)

            from src.core.model_registry import ModelRegistry
            registry = ModelRegistry()
            models = [m for m in registry.get_available_models() if m.provider.value == provider_name]

            if models:
                cheapest = min(models, key=lambda m: m.input_cost_per_mtok)
                from src.agents.factory import AgentFactory
                agent = AgentFactory.create_agent(cheapest, api_key=key_val)
                health = await agent.health_check()
                if health["reachable"]:
                    stat_label.update(f"✅ Live ({health['latency_ms']}ms)")
                    KeyChainManager.set_key(var_name, key_val)
                else:
                    stat_label.update(f"❌ {health.get('error', 'Unreachable')}")
            else:
                stat_label.update("✅ Valid")
                KeyChainManager.set_key(var_name, key_val)
        except Exception as e:
            logger.error(f"Settings key validation failed: {e}")
            stat_label.update(f"❌ Error: {e}")

    def _save_settings(self) -> None:
        logger.info("Saving user settings.")
        # Save keys
        for var_name in [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "XAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENROUTER_API_KEY",
        ]:
            inp = self.query_one(f"#settings-key-{var_name}", Input)
            if inp.value.strip():
                KeyChainManager.set_key(var_name, inp.value.strip())

        # Save model selection
        try:
            orch = self.query_one("#settings-orchestrator", Input).value
            self.app.config.set_user("orchestrator_model", orch.strip())
            coder = self.query_one("#settings-coder", Input).value
            self.app.config.set_user("coder_model", coder.strip())
            arbiter = self.query_one("#settings-arbiter", Input).value
            self.app.config.set_user("arbiter_model", arbiter.strip())
            architect = self.query_one("#settings-architect", Input).value
            self.app.config.set_user("architect_model", architect.strip())
            scout = self.query_one("#settings-scout", Input).value
            self.app.config.set_user("scout_model", scout.strip())
            tester = self.query_one("#settings-tester", Input).value
            self.app.config.set_user("tester_model", tester.strip())
        except Exception:
            pass

        try:
            tier = self.query_one("#settings-tier", Select).value
            if tier:
                self.app.config.set_user("quality_tier", tier)
        except Exception:
            pass

        # Save appearance
        theme = self.query_one("#settings-theme", Select).value
        self.app.config.set_user("theme", theme)
        self.app._apply_theme(theme)

        layout_changed = False
        try:
            new_layout = self.query_one("#settings-layout", Select).value
            old_layout = getattr(self.app.config.user, "layout_order", "files_code_chat")
            if new_layout != old_layout:
                self.app.config.set_user("layout_order", new_layout)
                self._layout_changed_flag = True
        except Exception:
            pass

        # Save behavior
        self.app.config.set_user(
            "confirm_before_apply", self.query_one("#settings-confirm", Checkbox).value
        )
        self.app.config.set_user(
            "auto_security_scan", self.query_one("#settings-scan", Checkbox).value
        )
        self.app.config.set_user(
            "show_cost_after_task", self.query_one("#settings-cost", Checkbox).value
        )

        # Save billing
        self.app.config.set_user(
            "overage_enabled", self.query_one("#settings-overage", Checkbox).value
        )
        self.app.config.set_user(
            "auto_downgrade_on_limit", self.query_one("#settings-downgrade", Checkbox).value
        )
        from src.tui.widgets.toast import notify

        layout_changed = getattr(self, "_layout_changed_flag", False)
        if layout_changed:
            notify(self.app, "Settings Saved", "Please restart the application to apply the new layout sequence.", "warning")
            self._layout_changed_flag = False
        else:
            notify(self.app, "Settings Saved", "Your preferences have been updated.", "success")

        self.dismiss()
