from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList

from src.core.logger import get_logger

logger = get_logger("tui.onboarding")


class OnboardingScreen(ModalScreen):
    """Multi-step guided setup wizard for first-time use."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("enter", "next_step", "Next"),
    ]

    DEFAULT_CSS = """
    OnboardingScreen {
        align: center middle;
        background: $background;
    }
    #onboarding-dialog {
        width: 80%;
        max-width: 90;
        height: auto;
        min-height: 25;
        background: $panel;
        border: solid $primary;
        padding: 2 4;
    }
    .step-title {
        text-style: bold;
        color: $text;
        margin-bottom: 2;
        text-align: center;
    }
    .button-row {
        align: center bottom;
        margin-top: 2;
        height: auto;
    }
    .nav-btn {
        margin: 0 2;
    }
    .progress-dots {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    .opt-box {
        border: solid $secondary;
        padding: 1;
        margin-bottom: 1;
    }
    .key-input {
        width: 100%;
        margin-bottom: 1;
    }
    .key-status {
        width: 26;
        content-align: right middle;
    }
    .status-valid { color: $success; }
    .status-invalid { color: $error; }
    .status-checking { color: $primary; }
    .url-hint {
        color: $primary;
        text-style: underline;
        margin-bottom: 0;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.step = 1
        self.total_steps = 6
        self.path_chosen = None  # "byok", "subscribe", "explore"
        self.valid_keys = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="onboarding-dialog"):
            yield Label(self._get_dots(), classes="progress-dots", id="progress")
            yield Vertical(id="step-container")
            with Horizontal(classes="button-row"):
                yield Button("← Back", id="btn-back", classes="nav-btn", variant="default")
                yield Button("Skip for now", id="btn-skip", classes="nav-btn", variant="default")
                yield Button("Next →", id="btn-next", classes="nav-btn", variant="primary")

    def on_mount(self) -> None:
        self.render_step()

    def _get_dots(self) -> str:
        dots = []
        for i in range(1, self.total_steps + 1):
            if i == self.step:
                dots.append("●")
            else:
                dots.append("○")
        return " ".join(dots)

    def render_step(self) -> None:
        container = self.query_one("#step-container")
        container.remove_children()

        self.query_one("#progress", Label).update(self._get_dots())

        btn_next = self.query_one("#btn-next", Button)
        btn_next.label = "Next →" if self.step < 6 else "Start Coding →"

        btn_back = self.query_one("#btn-back", Button)
        btn_back.display = self.step > 1  # Only show Back after step 1

        if self.step == 1:
            self._render_step_1(container)
        elif self.step == 2:
            self._render_step_2_legal(container)
        elif self.step == 3:
            self._render_step_3(container)
        elif self.step == 4:
            if self.path_chosen == "subscribe":
                self._render_step_4_subscribe(container)
            else:
                self._render_step_4_byok(container)
        elif self.step == 5:
            self._render_step_5_prefs(container)
        elif self.step == 6:
            self._render_step_6_done(container)

    def _render_step_1(self, container):
        container.mount(Label("Welcome to gptcgt", classes="step-title"))
        container.mount(
            Label(
                "The multi-model AI coding terminal that runs multiple AIs on your code, picks the best solution with proof, and shows you exactly what it costs.\n\nLet's get you set up. This takes about 30 seconds."  # noqa: E501
            )
        )

    def _render_step_2_legal(self, container):
        container.mount(Label("Legal Agreements", classes="step-title"))
        container.mount(
            Label(
                "By using gptcgt you agree to our Terms of Service, Privacy Policy, "
                "and Acceptable Use Policy. Press Next → to accept."
            )
        )
        container.mount(Label("\nView documents (opens browser):", classes="text-secondary"))
        from textual.widgets import Button as _Btn

        container.mount(_Btn("Terms of Service", id="btn-tos", variant="default"))
        container.mount(_Btn("Privacy Policy", id="btn-privacy", variant="default"))
        container.mount(_Btn("Acceptable Use", id="btn-aup", variant="default"))

    def _render_step_3(self, container):
        container.mount(Label("How would you like to use gptcgt?", classes="step-title"))

        opts = OptionList(
            "🔑 Bring Your Own Keys (Free) — Use your existing API keys",
            "💳 Sign In (Managed Credits) — We handle API access & routing",
            "👀 Just explore (no API keys needed) — Browse the interface",
        )
        container.mount(opts)

    def _render_step_4_byok(self, container):
        container.mount(Label("Enter API Keys", classes="step-title"))
        container.mount(Label("Keys are stored securely in your OS keychain, never in files.\n"))

        self.key_inputs = {}
        for provider, var_name in [
            ("Anthropic (Claude)", "ANTHROPIC_API_KEY"),
            ("OpenAI (GPT)", "OPENAI_API_KEY"),
            ("Google (Gemini)", "GEMINI_API_KEY"),
            ("OpenRouter", "OPENROUTER_API_KEY"),
        ]:
            inp = Input(
                placeholder=f"Enter {provider} key",
                password=True,
                id=f"key-{var_name}",
                classes="key-input",
            )
            stat = Label("⬚ Optional", id=f"stat-{var_name}", classes="key-status")
            self.key_inputs[var_name] = (inp, stat)
            container.mount(inp)
            container.mount(stat)

    async def on_input_changed(self, event: Input.Changed) -> None:
        if not event.input.id or not event.input.id.startswith("key-"):
            return
        var_name = event.input.id.replace("key-", "")
        stat_label = self.query_one(f"#stat-{var_name}", Label)
        val = event.value.strip()

        if not val:
            stat_label.update("⬚ Optional")
            stat_label.remove_class("status-valid", "status-invalid", "status-checking")
            return

        stat_label.update("🔄 Checking...")
        stat_label.remove_class("status-valid", "status-invalid")
        stat_label.add_class("status-checking")

        # Run test in background
        logger.debug(f"Starting async verification for {var_name}")
        self.app.run_worker(self._validate_key(var_name, val, stat_label))

    async def _validate_key(self, var_name: str, key_val: str, stat_label: Label) -> None:
        try:
            from src.auth.key_validator import (
                KeyValidator,  # Lazy: only loaded when user validates a key
            )

            is_valid, msg = await KeyValidator.validate(var_name, key_val)

            if is_valid:
                stat_label.update("🔄 Testing API...")
                prov_map = {
                    "ANTHROPIC_API_KEY": "anthropic",
                    "OPENAI_API_KEY": "openai",
                    "GEMINI_API_KEY": "google",
                    "OPENROUTER_API_KEY": "openrouter",
                }
                provider_name = prov_map.get(var_name)

                from src.core.model_registry import ModelRegistry, Provider

                registry = ModelRegistry()
                # noqa: W293
                # Fetch provider models directly (bypass get_available_models since key isn't saved yet)
                try:
                    provider_enum = Provider(provider_name)
                    models = registry.get_by_provider(provider_enum)
                except ValueError:
                    models = []

                if models:
                    cheapest = min(models, key=lambda m: m.input_cost_per_mtok)
                    from src.agents.factory import AgentFactory

                    agent = AgentFactory.create_agent(cheapest, api_key=key_val)
                    health = await agent.health_check()
                    if health["reachable"]:
                        self._update_key_status(
                            stat_label,
                            True,
                            f"✅ Connected ({health['latency_ms']}ms)",
                            key_val,
                            var_name,
                        )
                    else:
                        self._update_key_status(stat_label, False, f"❌ Failed: {health.get('error', 'error')}", "", "")
                else:
                    self._update_key_status(stat_label, True, "✅ Valid", key_val, var_name)
            else:
                self._update_key_status(stat_label, False, f"❌ {msg}", "", "")
        except Exception as e:
            logger.error(f"Failed to validate {var_name}: {e}")
            self._update_key_status(stat_label, False, "❌ Error", "", "")

    def _update_key_status(self, stat_label: Label, is_valid: bool, text: str, key_val: str, var_name: str) -> None:
        stat_label.update(text)
        stat_label.remove_class("status-checking", "status-valid", "status-invalid")
        stat_label.add_class("status-valid" if is_valid else "status-invalid")

        if is_valid:
            if not hasattr(self, "_validated_providers"):
                self._validated_providers = set()
            if var_name not in self._validated_providers:
                self._validated_providers.add(var_name)
                self.valid_keys += 1
            # Import KeyChainManager here to avoid circular dep if it relies on app
            from src.auth.keychain import KeyChainManager

            KeyChainManager.set_key(var_name, key_val)

    def _render_step_4_subscribe(self, container):
        container.mount(Label("Sign In to gptcgt", classes="step-title"))
        container.mount(Label("Fetching login code...", id="auth-instruction"))

        # Start device flow async
        self.app.run_worker(self._start_auth_flow())

    async def _start_auth_flow(self):
        try:
            instruction_label = self.query_one("#auth-instruction", Label)
            flow_data = await self.app.auth_manager.start_device_flow()

            uri = flow_data.get("verification_uri", "https://gptcgt.ai/auth")
            code = flow_data.get("user_code", "ERROR")
            device_code = flow_data.get("device_code")

            instruction_label.update(
                f"1. Open this URL in your browser:\n   {uri}\n\n"
                f"2. Enter this code: [bold $primary]{code}[/]\n\n"
                f"Waiting for authentication...\n"
                f"(You can skip for now using the button below)"
            )

            # Poll for token
            success = await self.app.auth_manager.poll_device_flow(device_code)

            if success:
                email = self.app.auth_manager.email or "your account"
                plan = self.app.auth_manager.user_plan
                credits = self.app.auth_manager.credits_remaining
                instruction_label.update(
                    f"✅ Successfully signed in as {email}!\n\n"
                    f"Plan: {plan.title()}\n"
                    f"Credits: {credits}\n\n"
                    f"Click Next to continue."
                )
                self.valid_keys += 1  # Allows proceeding implicitly if we wanted to enforce it
            else:
                instruction_label.update("❌ Authentication failed or timed out. Please try again.")
        except Exception as e:
            logger.error(f"Auth flow error: {e}")
            try:
                instruction_label = self.query_one("#auth-instruction", Label)
                instruction_label.update(f"❌ Error starting auth flow: {e}")
            except Exception:
                pass

    def _render_step_5_prefs(self, container):
        container.mount(Label("Choose Your Defaults", classes="step-title"))
        container.mount(Label("Theme:"))
        container.mount(OptionList("🌙 Midnight", "☀️ Polar", "🌊 Slate", "🔥 Ember", "⚡ Neon", id="opt-theme"))
        container.mount(Label("\nQuality Tier:"))
        container.mount(OptionList("💡 Light", "⚡ Standard (recommended)", "🔥 Max", id="opt-tier"))

    def _render_step_6_done(self, container):
        container.mount(Label("You're all set! 🎉", classes="step-title"))
        container.mount(
            Label(
                "Quick reference:\n• Ctrl+P    Search files\n• Ctrl+B    Toggle file tree\n• Ctrl+J    Toggle chat panel\n• Ctrl+Q    Change quality tier\n• Ctrl+T    Change theme\n• Ctrl+,    Open settings\n• Ctrl+?    Help & all shortcuts\n• Tab       Cycle between panels\n\nType any of these to get started:\n"  # noqa: E501
            )
        )
        container.mount(Label('• "Explain what this codebase does"', classes="empty-prompt"))
        container.mount(Label('• "Find the main entry point"', classes="empty-prompt"))
        container.mount(Label('• "Add a ping endpoint"', classes="empty-prompt"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-skip":
            self.app.config.set_user("setup_completed", True)
            self.dismiss()
        elif event.button.id == "btn-back":
            if self.step > 1:
                self.step -= 1
                self.render_step()
        elif event.button.id == "btn-next":
            self.action_next_step()
        elif event.button.id == "btn-tos":
            import webbrowser

            webbrowser.open("https://gptcgt.ai/legal/terms")
        elif event.button.id == "btn-privacy":
            import webbrowser

            webbrowser.open("https://gptcgt.ai/legal/privacy")
        elif event.button.id == "btn-aup":
            import webbrowser

            webbrowser.open("https://gptcgt.ai/legal/aup")

    def action_next_step(self) -> None:
        if self.step == 2:
            # Legal Accepted
            self.app.config.set_user("tos_accepted", True)
            import datetime

            self.app.config.set_user("tos_accepted_at", datetime.datetime.now(datetime.timezone.utc).isoformat())
            self.app.config.set_user("tos_version", "1.0")

            # Send to backend if authenticated
            if hasattr(self.app, "auth_manager") and self.app.auth_manager.is_authenticated:

                async def _sync_tos():
                    try:
                        import httpx

                        from src.auth.keychain import KeyChainManager

                        access_token, _ = KeyChainManager.get_auth_tokens()
                        if access_token:
                            async with httpx.AsyncClient() as client:
                                await client.patch(
                                    f"{self.app.auth_manager.base_url}/user/me",
                                    json={"tos_version": "1.0"},
                                    headers={"Authorization": f"Bearer {access_token}"},
                                    timeout=10.0,
                                )
                    except Exception:
                        pass  # Best-effort sync, will retry on next login

                self.app.run_worker(_sync_tos())

        if self.step == 3:
            opts = self.query_one(OptionList)
            if opts.highlighted == 0:
                self.path_chosen = "byok"
            elif opts.highlighted == 1:
                self.path_chosen = "subscribe"
            else:
                self.path_chosen = "explore"
                self.step = 4  # jump over API keys (it will get += 1 to step 5 below)

        if self.step == 5:
            # Save preferences
            theme_opts = self.query_one("#opt-theme", OptionList)
            tier_opts = self.query_one("#opt-tier", OptionList)
            theme_map = {0: "midnight", 1: "polar", 2: "slate", 3: "ember", 4: "neon"}
            tier_map = {0: "light", 1: "standard", 2: "max"}

            theme = theme_map.get(theme_opts.highlighted, "midnight")
            tier = tier_map.get(tier_opts.highlighted, "standard")

            self.app.config.set_user("theme", theme)
            self.app._active_theme_name = theme
            self.app.config.set_user("default_tier", tier)

        if self.step < self.total_steps:
            self.step += 1
            self.render_step()
        else:
            self.app.config.set_user("setup_completed", True)
            self.dismiss()
