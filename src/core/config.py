from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import tempfile

import tomli_w

from src.core.logger import get_logger

logger = get_logger("core.config")


@dataclass
class UserConfig:
    """Global user preferences stored in ~/.gptcgt/global.toml"""

    # Setup
    setup_completed: bool = False

    # Appearance
    theme: str = "midnight"

    # Defaults
    default_quality_tier: str = "standard"
    default_operation_mode: str = "standard"

    # Layout State
    panel_positions: dict = field(default_factory=lambda: {"files": "left", "code": "center", "chat": "right"})
    panel_sizes: dict = field(default_factory=lambda: {"files": 0.2, "code": 0.6, "chat": 0.2})
    visible_panels: dict = field(default_factory=lambda: {"files": True, "code": True, "chat": True})

    # Models
    coder_model: str = ""
    orchestrator_model: str = ""
    arbiter_model: str = ""
    architect_model: str = ""
    scout_model: str = ""
    tester_model: str = ""
    openrouter_active_models: list[str] = field(default_factory=list)
    custom_models: list[dict] = field(default_factory=list)

    # Privacy
    telemetry_enabled: bool = False
    store_chat_on_disk: bool = True
    session_retention_days: int = 90

    # Legal
    tos_accepted: bool = False
    tos_accepted_at: str | None = None
    tos_version: str | None = None

    # Billing
    overage_enabled: bool = False
    auto_downgrade_on_limit: bool = True
    monthly_spending_cap: float | None = None
    daily_spending_warning: float = 5.0
    daily_spend_limit: float = 10.0  # BYOK daily hard stop limit
    max_spend_per_task: float = 2.0  # USD cap per individual task/iteration
    max_tokens_per_task: int = 500_000  # Token cap per task

    # Autonomous
    allow_auto_tiering: bool = True  # Let agents pick their own model tier
    max_autonomous_iterations: int = 50  # Hard cap on autonomous loop
    max_autonomous_budget: float = 20.0  # USD cap for entire autonomous session

    # API
    api_base_url: str = "https://gptcgt.ai/api"  # Base URL for proxy API

    # Token Efficiency
    max_context_tokens_per_agent: int = 100_000  # Context budget per agent

    # Integrations
    mcp_servers: list = field(default_factory=list)  # MCP server configs

    # Behavior
    confirm_before_apply: bool = True
    auto_security_scan: bool = True
    show_cost_after_task: bool = True
    show_tier_comparison: bool = True


@dataclass
class ProjectConfig:
    """Per-project settings stored in .gptcgt/config.toml"""

    # Project identity
    project_name: str = ""
    project_description: str = ""

    # Languages and tools
    primary_language: str = ""
    test_command: str = ""
    lint_command: str = ""
    build_command: str = ""

    # File handling
    always_include_in_context: list[str] = field(default_factory=list)
    never_include_in_context: list[str] = field(default_factory=list)
    custom_ignore_patterns: list[str] = field(default_factory=list)

    # Agent preferences
    preferred_orchestrator_model: str = ""
    preferred_coding_model: str = ""

    # Git integration
    auto_branch_for_changes: bool = False
    branch_prefix: str = "gptcgt/"


class ConfigManager:
    """
    Loads, saves, and merges global + project configs.
    Project settings override global settings where both define the same key.

    Singleton: use ConfigManager.get_instance() for shared access.
    Use ConfigManager(project_root) for explicit first initialization.
    """

    _instance: "ConfigManager | None" = None

    def __init__(self, project_root: Path | None = None) -> None:
        self.GLOBAL_PATH = Path.home() / ".gptcgt" / "global.toml"
        self._user_config = UserConfig()
        self._project_config = ProjectConfig()
        self._project_root = project_root or Path.cwd()
        self.project_path = self._project_root / ".gptcgt" / "config.toml"
        self._load()
        ConfigManager._instance = self

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """Return the singleton instance, creating with defaults if needed."""
        if cls._instance is None:
            cls()
        return cls._instance  # type: ignore

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (primarily for testing)."""
        cls._instance = None

    def _load(self) -> None:
        """Load global config, then project config as override."""
        # Load user config
        if self.GLOBAL_PATH.exists():
            try:
                with open(self.GLOBAL_PATH, "rb") as f:
                    data = tomllib.load(f)
                    # Update dataclass with loaded values
                    for k, v in data.items():
                        if hasattr(self._user_config, k):
                            setattr(self._user_config, k, v)
                    logger.debug(f"Loaded global config from {self.GLOBAL_PATH}")
            except Exception as e:
                logger.warning(f"Failed to load global config from {self.GLOBAL_PATH}: {e}")
                pass  # Fallback to defaults

        # Load project config
        if self.project_path.exists():
            try:
                with open(self.project_path, "rb") as f:
                    data = tomllib.load(f)
                    for k, v in data.items():
                        if hasattr(self._project_config, k):
                            setattr(self._project_config, k, v)
            except Exception:
                pass

    def _atomic_write(self, filepath: Path, data: dict) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=filepath.parent, prefix=".tmp_")
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(data, f)
        os.replace(temp_path, filepath)

    def _save_global(self) -> None:
        """Write global config to ~/.gptcgt/global.toml using atomic write."""
        data = {k: v for k, v in asdict(self._user_config).items() if v is not None}
        self._atomic_write(self.GLOBAL_PATH, data)

    def _save_project(self) -> None:
        """Write project config to .gptcgt/config.toml using atomic write."""
        data = {k: v for k, v in asdict(self._project_config).items() if v is not None}
        self._atomic_write(self.project_path, data)

    @property
    def user(self) -> UserConfig:
        return self._user_config

    @property
    def project(self) -> ProjectConfig:
        return self._project_config

    def get(self, key: str) -> Any:
        """Get a config value. Project config overrides global."""
        has_proj = hasattr(self._project_config, key)
        has_user = hasattr(self._user_config, key)

        if has_proj and has_user:
            val = getattr(self._project_config, key)
            return val if val is not None else getattr(self._user_config, key)

        if has_proj:
            return getattr(self._project_config, key)

        if has_user:
            return getattr(self._user_config, key)

        return None

    def set_user(self, key: str, value: Any) -> None:
        """Update a global preference and save."""
        if hasattr(self._user_config, key):
            setattr(self._user_config, key, value)
            self._save_global()

    def set_project(self, key: str, value: Any) -> None:
        """Update a project setting and save."""
        if hasattr(self._project_config, key):
            setattr(self._project_config, key, value)
            self._save_project()

    def auto_detect_project(self) -> None:
        """Auto-detect project settings from the codebase."""
        # Project name
        if not self._project_config.project_name:
            self._project_config.project_name = self._project_root.name

        # Language detection (basic)
        if not self._project_config.primary_language:
            exts = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "typescript",
                ".go": "go",
                ".rs": "rust",
            }
            counts = {lang: 0 for lang in exts.values()}
            for ext, lang in exts.items():
                counts[lang] = len(list(self._project_root.glob(f"**/*{ext}")))
            best_lang = max(counts.items(), key=lambda x: x[1])
            if best_lang[1] > 0:
                self._project_config.primary_language = best_lang[0]

        # Test/Lint commands (basic heuristics)
        if not self._project_config.test_command:
            pyproject = self._project_root / "pyproject.toml"
            if (self._project_root / "pytest.ini").exists() or (
                pyproject.exists() and "pytest" in pyproject.read_text(errors="ignore")
            ):
                self._project_config.test_command = "pytest"
            elif (self._project_root / "package.json").exists():
                self._project_config.test_command = "npm test"

        if not self._project_config.lint_command:
            pyproject = self._project_root / "pyproject.toml"
            if (self._project_root / "ruff.toml").exists() or (
                pyproject.exists() and "ruff" in pyproject.read_text(errors="ignore")
            ):
                self._project_config.lint_command = "ruff check ."
            elif (self._project_root / ".eslintrc").exists():
                self._project_config.lint_command = "eslint ."

        self._save_project()
