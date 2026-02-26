"""
Rules-based model router. Selects the appropriate model based on
the user's Quality Tier, task complexity, and intent. Tracks routing outcomes
to improve future selections.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.core.logger import get_logger
from src.core.model_registry import ModelDefinition, ModelRegistry, QualityTier
from src.core.workspace import Workspace

logger = get_logger("core.router")


@dataclass
class RoutingSignals:
    """Signals used by the router to make model decisions."""

    intent: str
    complexity: int
    file_count: int
    is_retry: bool = False
    previous_failures: int = 0


@dataclass
class RoutingOutcome:
    """Records the outcome of a routing decision."""

    timestamp: str
    task_id: str
    model_id: str
    intent: str
    complexity: int
    success: bool
    error_message: str | None = None
    fallback_used: bool = False


from enum import Enum  # noqa: E402


class TaskIntent(str, Enum):
    CHAT = "chat"
    QUESTION = "question"
    EDIT = "edit"
    CREATE = "create"
    DEBUG = "debug"
    ARCHITECT = "architect"

class CodingRouter:
    def __init__(self):
        self.registry = ModelRegistry()
        try:
            ws = Workspace.get_instance()
            self.history_file = ws.get_project_root() / ".gptcgt" / "routing_history.json"
        except Exception:
            self.history_file = Path(".gptcgt/routing_history.json")
        self.outcomes: list[RoutingOutcome] = self._load_history()
        self._elo_cache: dict[str, float] = {}      # model_id -> elo_rating
        self._elo_cache_ts: float = 0.0              # epoch seconds of last load

    def _load_history(self) -> list[RoutingOutcome]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r") as f:
                data = json.load(f)
            return [RoutingOutcome(**opt) for opt in data]
        except Exception:
            return []

    def _refresh_elo_cache(self) -> None:
        """
        Load ELO ratings from SQLite into an in-memory dict.

        Refreshed at most once every 60 seconds so routing performance
        is not penalised by repeated disk reads on every keystroke.
        """
        import time

        if time.time() - self._elo_cache_ts < 60:
            return
        try:
            from src.core.elo_tracker import EloTracker
            tracker = EloTracker()
            leaderboard = tracker.get_leaderboard()
            self._elo_cache = {row["id"]: row["elo_rating"] for row in leaderboard}
            self._elo_cache_ts = time.time()
            logger.debug(f"ELO cache refreshed: {len(self._elo_cache)} models tracked.")
        except Exception as e:
            logger.debug(f"ELO cache refresh skipped: {e}")

    def _apply_elo_sort(self, candidates: list[ModelDefinition]) -> list[ModelDefinition]:
        """
        Re-rank candidates using ELO data.

        Models with ELO > 1200 (above-average win rate) are sorted ahead
        of same-tier peers. Models with ELO < 1100 drop to the back.
        Models with no ELO history are treated as neutral (1200).
        """
        self._refresh_elo_cache()
        if not self._elo_cache:
            return candidates

        def elo_key(m: ModelDefinition) -> float:
            return self._elo_cache.get(m.id, 1200.0)

        # Within each tier, sort descending by ELO *then* ascending by cost as tiebreak
        return sorted(candidates, key=lambda m: (-elo_key(m), m.input_cost_per_mtok))

    def route_task(
        self,
        intent: str,
        complexity: int,
        global_tier: QualityTier,
        provider_family: str | None = None,
        role: str | None = None,
    ) -> ModelDefinition:
        """
        Determines the best model to use.

        Selection priority (highest to lowest):
        1. Explicit user-configured model for this role / global default
        2. Provider family override
        3. Complexity-gated tier selection (boosted by ELO leaderboard)
        4. Cheapest available fallback
        """
        # NOTE: RoutingSignals object intentionally not created here — signals
        # are passed directly as parameters; no side effects from construction.

        from src.core.config import ConfigManager
        config = ConfigManager()

        explicit_model_str = None
        if role:
            explicit_model_str = getattr(config.user, f"{role}_model", None)

        if not explicit_model_str:
            explicit_model_str = getattr(config.user, "default_model", None)

        if explicit_model_str and not provider_family:
            explicit_model = self.registry.get(explicit_model_str)
            if explicit_model:
                return explicit_model
            else:
                if "/" in explicit_model_str:
                    prov_str, name = explicit_model_str.split("/", 1)
                    from src.core.model_registry import Provider
                    try:
                        prov = Provider(prov_str.lower())
                    except ValueError:
                        prov = Provider.CUSTOM

                    return ModelDefinition(
                        id=explicit_model_str,
                        name=name,
                        provider=prov,
                        input_cost_per_mtok=0.0,
                        output_cost_per_mtok=0.0,
                        max_context_tokens=128000
                    )

        candidates = self.registry.get_available_models()
        if provider_family:
            candidates = [
                m for m in candidates if m.provider.value.lower() == provider_family.lower()
            ]

        if not candidates:
            # Fallback if the requested family has no models configured locally
            candidates = self.registry.get_available_models()

        if not candidates:
            # Absolute fallback if somehow no keys are configured (handled downstream by ChatPipeline)
            candidates = self.registry.get_all()

        # Apply ELO-based re-ranking to all candidate lists
        candidates = self._apply_elo_sort(candidates)

        # Simple questions or trivial coding tasks can explicitly drop to the cheapest tier
        if complexity <= 3:
            light_cands = [
                m
                for m in candidates
                if QualityTier.LIGHT.value in m.quality_tiers
            ]
            if light_cands:
                return light_cands[0]  # ELO-sorted, highest-rated first

            std_cands = [
                m
                for m in candidates
                if QualityTier.STANDARD.value in m.quality_tiers
            ]
            if std_cands:
                return std_cands[0]  # ELO-sorted

        # High complexity coding
        if (
            intent in [TaskIntent.EDIT.value, TaskIntent.CREATE.value, TaskIntent.DEBUG.value]
            and complexity > 7
        ):
            max_cands = [
                m for m in candidates if global_tier.value in m.quality_tiers
            ]
            if max_cands:
                # For max quality, take top ELO winner rather than most expensive
                return max_cands[0]

        # Fallback to current tier default
        tier_cands = [
            m for m in candidates if global_tier.value in m.quality_tiers
        ]
        if tier_cands:
            return tier_cands[0]  # ELO-sorted

        # Ultimate fallback
        if candidates:
            return candidates[0]  # ELO-sorted, cheapest of neutrals

        raise ValueError(
            "No models are available. Please add at least one API key in Settings (Ctrl+,) "
            "and ensure the selected Quality Tier has models configured."
        )

    def _save_history(self) -> None:
        """Persist the last 100 routing outcomes to disk for analytics."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w") as f:
                json.dump([vars(o) for o in self.outcomes[-100:]], f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save routing history: {e}")

    def get_parallel_models(self, count: int) -> list[ModelDefinition]:
        """Returns the top `count` distinct models available for parallel generation."""
        available = self.registry.get_available_models()
        # Sort by capability (heuristic: cost/tokens usually correlates)
        TIER_ORDER = {"max": 3, "standard": 2, "light": 1}
        available.sort(
            key=lambda m: (
                TIER_ORDER.get(m.quality_tiers[0] if m.quality_tiers else "", 0),
                m.input_cost_per_mtok,
            ),
            reverse=True,
        )
        # We need distinct providers/models for a good ensemble/battle
        selected = []
        seen_providers = set()
        for m in available:
            if m.provider.value not in seen_providers:
                selected.append(m)
                seen_providers.add(m.provider.value)
            if len(selected) == count:
                break

        # If we didn't get enough distinct providers, just take top N distinct models
        if len(selected) < count:
            selected = available[:count]

        return selected

    def record_outcome(
        self,
        task_id: str,
        model_id: str,
        intent: str,
        complexity: int,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """Records whether a model successfully completed a task or failed."""
        outcome = RoutingOutcome(
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
            model_id=model_id,
            intent=intent,
            complexity=complexity,
            success=success,
            error_message=error_message,
        )
        self.outcomes.append(outcome)
        self._save_history()
        logger.debug(f"Recorded routing outcome for task {task_id}: success={success}")
