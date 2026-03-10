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
        Binding("q", "dismiss", "Close Settings"),
        Binding("ctrl+tab", "next_tab", "Next Tab"),
        Binding("ctrl+shift+tab", "prev_tab", "Previous Tab"),
        Binding("ctrl+s", "save", "Save"),
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
        margin-bottom: 0;
        text-align: center;
        width: 100%;
        border-bottom: solid $secondary;
        padding-bottom: 0;
    }
    .settings-subtitle {
        color: $text-muted;
        text-align: center;
        margin-bottom: 1;
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
            yield Label("Esc/Q: close • Ctrl+Tab: next tab • Ctrl+S: save", classes="settings-subtitle")
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
                with TabPane("Integrations", id="tab-integrations"):
                    with VerticalScroll():
                        yield from self._compose_integrations_tab()
                with TabPane("About", id="tab-about"):
                    with VerticalScroll():
                        yield from self._compose_about_tab()

            with Horizontal(classes="settings-actions"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Save & Close", id="btn-save", variant="primary")

    def action_save(self) -> None:
        self._save_settings()

    def action_next_tab(self) -> None:
        self._cycle_tab(1)

    def action_prev_tab(self) -> None:
        self._cycle_tab(-1)

    def _cycle_tab(self, step: int) -> None:
        tabs = self.query_one(TabbedContent)
        pane_ids = [pane.id for pane in tabs.query(TabPane) if pane.id]
        if not pane_ids:
            return
        active = tabs.active if tabs.active in pane_ids else pane_ids[0]
        idx = pane_ids.index(active)
        tabs.active = pane_ids[(idx + step) % len(pane_ids)]

    def on_mount(self) -> None:
        """Fetch OpenRouter models in the background if key exists."""
        from src.auth.keychain import KeyChainManager
        if KeyChainManager.get_key("OPENROUTER_API_KEY"):
            # Delay slightly so UI can render first
            self.set_timer(0.5, lambda: self.app.run_worker(self._fetch_and_populate_openrouter_dropdowns()))

    async def _fetch_and_populate_openrouter_dropdowns(self) -> None:
        from src.core.model_registry import ModelRegistry
        registry = ModelRegistry()
        data = await registry.fetch_openrouter_models()
        if not data:
            return

        openrouter_opts = []
        for m in data:
            name = m.get("name", m.get("id"))
            m_id = "openrouter/" + m.get("id")
            openrouter_opts.append((f"🐋 {name} (openrouter)", m_id))

        self._update_select_options(openrouter_opts)

    def _update_select_options(self, extra_opts: list[tuple[str, str]]) -> None:
        import re
        def natural_sort_key(text: str) -> list:
            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

        def key_fn(opt):
            lbl, val = opt
            if not val:
                return ("000_default", [])
            if val.startswith("openrouter/"):
                parts = val.replace("openrouter/", "").split("/")
                provider = parts[0].lower() if len(parts) >= 2 else "openrouter"
            elif "/" in val:
                provider = val.split("/")[0].lower()
            else:
                provider = "zzz_other"
            return (provider, natural_sort_key(lbl))

        for select_id in ["#settings-orchestrator", "#settings-coder", "#settings-arbiter", "#settings-architect", "#settings-scout", "#settings-tester"]:  # noqa: E501
            try:
                sel = self.query_one(select_id, Select)
                existing_vals = {opt[1] for opt in sel._options}
                new_options = list(sel._options)
                for lbl, val in extra_opts:
                    if val not in existing_vals:
                        new_options.append((lbl, val))
                sel.set_options(sorted(new_options, key=key_fn))
            except Exception:
                pass

    def _get_model_options(self, current_val: str) -> list[tuple[str, str]]:
        from src.core.model_registry import ModelRegistry
        opts = [("Default (Auto)", "")]
        av_models = ModelRegistry().get_available_models()
  # noqa: W293
        seen = set()
        for m in av_models:
            if m.id not in seen:
                opts.append((f"{m.display_emoji} {m.name} ({m.provider.value})", m.id))
                seen.add(m.id)
  # noqa: W293
        if current_val and current_val not in seen:
            opts.append((f"⚙️ Custom ({current_val})", current_val))
  # noqa: W293

        import re
        def natural_sort_key(text: str) -> list:
            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

        def key_fn(opt):
            lbl, val = opt
            if not val:
                return ("000_default", [])
            if val.startswith("openrouter/"):
                parts = val.replace("openrouter/", "").split("/")
                provider = parts[0].lower() if len(parts) >= 2 else "openrouter"
            elif "/" in val:
                provider = val.split("/")[0].lower()
            else:
                provider = "zzz_other"
            return (provider, natural_sort_key(lbl))

        return sorted(opts, key=key_fn)

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
            ("E2B", "E2B_API_KEY", "https://e2b.dev/docs/getting-started/api-key"),
        ]

        mapping = {
            "Anthropic": "Claude",
            "OpenAI": "GPT",
            "Google": "Gemini",
            "xAI": "Grok",
            "E2B": "E2B Sandbox",
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
            "Select specific models. These override automatic tier routing.\n"
            "Choose 'Default (Auto)' to use the best model for your tier.",
            classes="hint-text",
        )

        c = self.app.config.user

        yield Label("Orchestrator Model:")
        v = getattr(c, "orchestrator_model", "")
        yield Select(self._get_model_options(v), value=v, id="settings-orchestrator")

        yield Label("Coder Model:")
        v = getattr(c, "coder_model", "")
        yield Select(self._get_model_options(v), value=v, id="settings-coder")

        yield Label("Arbiter (Judge) Model:")
        v = getattr(c, "arbiter_model", "")
        yield Select(self._get_model_options(v), value=v, id="settings-arbiter")

        yield Label("Architect (Planning) Model:")
        v = getattr(c, "architect_model", "")
        yield Select(self._get_model_options(v), value=v, id="settings-architect")

        yield Label("Scout (Exploration) Model:")
        v = getattr(c, "scout_model", "")
        yield Select(self._get_model_options(v), value=v, id="settings-scout")

        yield Label("Tester (QA) Model:")
        v = getattr(c, "tester_model", "")
        yield Select(self._get_model_options(v), value=v, id="settings-tester")

        yield Label("\nFallback Quality Tier (when model fields above are blank):")
        tier_opts = [
            ("💡 Light — Fast & cheap (~$0.01/task)", "light"),
            ("⚡ Standard — Balanced (~$0.04/task)", "standard"),
            ("🔥 Max — Best quality (~$0.12/task)", "max"),
        ]
        current_tier = getattr(self.app.config.user, "default_quality_tier", "standard")
        yield Select(tier_opts, value=current_tier, id="settings-tier")

    def _compose_appearance_tab(self):
        c = self.app.config.user

        yield Label("Theme:", classes="section-label")
        theme_opts = [
            ("🌙 Midnight", "midnight"),
            ("☀️ Polar", "polar"),
            ("🪨 Slate", "slate"),
            ("🔥 Ember", "ember"),
            ("💜 Neon", "neon"),
        ]
        current_theme = getattr(c, "theme", "midnight")
        yield Select(theme_opts, value=current_theme, id="settings-theme")

        yield Label("\nLayout Configuration:", classes="section-label")
        yield Label(
            "Design how panels are arranged on your screen.\nChanges apply instantly without restarting.",
            classes="hint-text"
        )
        yield Button("Open Visual Layout Editor", id="btn-open-layout-editor", variant="primary")

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
        yield Checkbox(
            "Store chat history on disk", value=c.store_chat_on_disk, id="settings-store-chat"
        )
        yield Checkbox(
            "Enable anonymous telemetry", value=c.telemetry_enabled, id="settings-telemetry"
        )
        yield Checkbox(
            "Show tier comparison after tasks", value=c.show_tier_comparison, id="settings-tier-cmp"
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
            yield Label(f"Plan: [bold]{plan}[/bold]  •  {credits}/{month_credits} credits remaining", classes="section-label")  # noqa: E501
        else:
            yield Label("Plan: [bold]Bring Your Own Keys[/bold] (Free)", classes="section-label")
            yield Label(
                "Sign in at gptcgt.ai/pricing for managed credits and Pro plan.",
                classes="hint-text",
            )

        # Security info
        yield Label("\n🔒 Security:", classes="section-label")
        yield Label("AI is sandboxed to your project folder. It cannot access files outside.", classes="hint-text")

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
        yield Label("\nDaily spend limit ($):")
        yield Input(
            str(c.daily_spend_limit),
            placeholder="e.g. 10.00",
            id="settings-daily-limit",
        )
        yield Label("Daily spending warning threshold ($):")
        yield Input(
            str(c.daily_spending_warning),
            placeholder="e.g. 5.00",
            id="settings-daily-warn",
        )

        # Phase 9: Per-task budget controls
        yield Label("\nPer-Task Limits:", classes="section-label")
        yield Label("Max USD per task/iteration:")
        yield Input(
            str(c.max_spend_per_task),
            placeholder="e.g. 2.00",
            id="settings-task-spend-limit",
        )


        # Phase 9: Autonomous controls
        yield Label("\nAutonomous Mode:", classes="section-label")
        yield Checkbox(
            "Allow AI to auto-scale models (upgrade/downgrade by complexity)",
            value=c.allow_auto_tiering,
            id="settings-auto-tiering",
        )
        yield Label("Max autonomous iterations:")
        yield Input(
            str(c.max_autonomous_iterations),
            placeholder="e.g. 50",
            id="settings-max-iterations",
        )

        yield Label("\nHistory & Receipts:", classes="section-label")
        yield Button("View Receipt History", id="btn-receipts", variant="default")
        yield Button("Open Billing Portal →", id="btn-billing-portal", variant="default")

    def _compose_integrations_tab(self):
        c = self.app.config.user
        yield Label("🔌 MCP Server Integrations", classes="section-label")
        yield Label(
            "Connect external tools (GitHub, databases, etc.) via Model Context Protocol.",
            classes="hint-text",
        )

        yield Label("\nConnected Servers:", classes="section-label")

        # Show existing MCP server configs
        mcp_servers = getattr(c, "mcp_servers", [])
        if mcp_servers:
            for i, server in enumerate(mcp_servers):
                name = server.get("name", f"Server {i+1}")
                transport = server.get("transport", "stdio")
                enabled = server.get("enabled", True)
                status = "🟢 Active" if enabled else "🔴 Disabled"
                yield Label(f"  {status} {name} ({transport})")
        else:
            yield Label("  No MCP servers configured.", classes="hint-text")

        yield Label("\nAdd MCP Server (JSON):", classes="section-label")
        yield Label(
            'Example: {"name": "github", "transport": "stdio", '
            '"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], '
            '"env": {"GITHUB_TOKEN": "..."}}',
            classes="hint-text",
        )
        from textual.widgets import TextArea
        yield TextArea(
            "",
            id="settings-mcp-json",
        )
        with Horizontal(classes="mcp-actions"):
            yield Button("Add Server", id="btn-add-mcp", variant="primary")
            yield Button("Test Connections", id="btn-test-mcp", variant="default")
            yield Button("📋 Template: GitHub", id="btn-quick-github", variant="default")

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
            webbrowser.open("https://github.com/gptcgt/gptcgt/issues")
        elif event.button.id == "btn-add-mcp":
            self._add_mcp_server()
        elif event.button.id == "btn-test-mcp":
            self._test_mcp_servers()
        elif event.button.id == "btn-quick-github":
            try:
                from textual.widgets import TextArea
                ta = self.query_one("#settings-mcp-json", TextArea)
                import json
                ta.text = json.dumps({
                    "name": "github",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR_TOKEN_HERE"
                    }
                }, indent=2)
            except Exception:
                pass
        elif event.button.id == "btn-open-layout-editor":
            self.app.action_show_layout_editor()

    def _add_mcp_server(self) -> None:
        try:
            from textual.widgets import TextArea
            ta = self.query_one("#settings-mcp-json", TextArea)
            if not ta.text.strip():
                return
            import json
            server_cfg = json.loads(ta.text)
            c = self.app.config.user
            mcp_servers = getattr(c, "mcp_servers", [])
            mcp_servers.append(server_cfg)
            self.app.config.set_user("mcp_servers", mcp_servers)
            from src.tui.widgets.toast import notify
            notify(self.app, "MCP", f"Added {server_cfg.get('name')}", "success")
            ta.text = ""
        except Exception as e:
            from src.tui.widgets.toast import notify
            notify(self.app, "MCP Error", f"Invalid JSON: {e}", "error")

    def _test_mcp_servers(self) -> None:
        from src.core.mcp_client import MCPManager
        from src.tui.widgets.toast import notify
        c = self.app.config.user
        mcp_servers = getattr(c, "mcp_servers", [])
        if not mcp_servers:
            notify(self.app, "MCP", "No servers to test.", "warning")
            return
  # noqa: W293
        async def run_tests():
            for s in mcp_servers:
                if not s.get("enabled", True):
                    continue
                try:
                    import asyncio
                    tools = await asyncio.to_thread(MCPManager.discover, s)
                    self.app.call_after_refresh(notify, self.app, "MCP Success", f"{s.get('name')}: found {len(tools)} tools.", "success")  # noqa: E501
                except Exception as e:
                    self.app.call_after_refresh(notify, self.app, "MCP Failed", f"{s.get('name')}: {e}", "error")

        self.app.run_worker(run_tests(), exclusive=False)

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

            if var_name == "E2B_API_KEY":
                stat_label.update("✅ Valid Sandbox Key")
                KeyChainManager.set_key(var_name, key_val)
                return

            provider_name = prov_map.get(var_name)

            from src.core.model_registry import ModelRegistry, Provider
            registry = ModelRegistry()
  # noqa: W293
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
            "E2B_API_KEY",
        ]:
            inp = self.query_one(f"#settings-key-{var_name}", Input)
            if inp.value.strip():
                KeyChainManager.set_key(var_name, inp.value.strip())

        # Save model selection
        try:
            orch = self.query_one("#settings-orchestrator", Select).value
            self.app.config.set_user("orchestrator_model", str(orch).strip() if orch and orch != Select.BLANK else "")
            coder = self.query_one("#settings-coder", Select).value
            self.app.config.set_user("coder_model", str(coder).strip() if coder and coder != Select.BLANK else "")
            arbiter = self.query_one("#settings-arbiter", Select).value
            self.app.config.set_user("arbiter_model", str(arbiter).strip() if arbiter and arbiter != Select.BLANK else "")  # noqa: E501
            architect = self.query_one("#settings-architect", Select).value
            self.app.config.set_user("architect_model", str(architect).strip() if architect and architect != Select.BLANK else "")  # noqa: E501
            scout = self.query_one("#settings-scout", Select).value
            self.app.config.set_user("scout_model", str(scout).strip() if scout and scout != Select.BLANK else "")
            tester = self.query_one("#settings-tester", Select).value
            self.app.config.set_user("tester_model", str(tester).strip() if tester and tester != Select.BLANK else "")
        except Exception:
            pass

        try:
            tier = self.query_one("#settings-tier", Select).value
            if tier:
                self.app.config.set_user("default_quality_tier", tier)
        except Exception:
            pass

        # Layout is now managed instantly by LayoutEditorOverlay

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
        self.app.config.set_user(
            "store_chat_on_disk", self.query_one("#settings-store-chat", Checkbox).value
        )
        self.app.config.set_user(
            "telemetry_enabled", self.query_one("#settings-telemetry", Checkbox).value
        )
        self.app.config.set_user(
            "show_tier_comparison", self.query_one("#settings-tier-cmp", Checkbox).value
        )

        # Save appearance (theme)
        try:
            theme_val = self.query_one("#settings-theme", Select).value
            if theme_val and theme_val != Select.BLANK:
                self.app.config.set_user("theme", str(theme_val))
                if hasattr(self.app, "_apply_theme"):
                    self.app._apply_theme(str(theme_val))
        except Exception:
            pass

        # Save billing
        self.app.config.set_user(
            "overage_enabled", self.query_one("#settings-overage", Checkbox).value
        )
        self.app.config.set_user(
            "auto_downgrade_on_limit", self.query_one("#settings-downgrade", Checkbox).value
        )
        try:
            dsl = self.query_one("#settings-daily-limit", Input).value.strip()
            if dsl:
                self.app.config.set_user("daily_spend_limit", float(dsl))
        except Exception:
            pass
        try:
            dsw = self.query_one("#settings-daily-warn", Input).value.strip()
            if dsw:
                self.app.config.set_user("daily_spending_warning", float(dsw))
        except Exception:
            pass

        # Phase 9: Per-task limits
        try:
            tsl = self.query_one("#settings-task-spend-limit", Input).value.strip()
            if tsl:
                self.app.config.set_user("max_spend_per_task", float(tsl))
        except Exception:
            pass


        # Phase 9: Autonomous controls
        try:
            self.app.config.set_user(
                "allow_auto_tiering", self.query_one("#settings-auto-tiering", Checkbox).value
            )
        except Exception:
            pass
        try:
            mi = self.query_one("#settings-max-iterations", Input).value.strip()
            if mi:
                self.app.config.set_user("max_autonomous_iterations", int(mi))
        except Exception:
            pass
        from src.tui.widgets.toast import notify
        notify(self.app, "Settings Saved", "Your preferences have been updated.", "success")

        self.dismiss()
