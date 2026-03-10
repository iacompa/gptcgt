from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from src.core.logger import get_logger

logger = get_logger("billing.costs")


@dataclass
class ModelUsage:
    """Token and cost tracking for a single model within a single task."""

    model_id: str
    model_display_name: str
    provider: str
    role: str
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    duration_seconds: float = 0.0
    was_refusal: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class TaskCostBreakdown:
    """Complete cost breakdown for a single task."""

    task_id: str
    task_title: str
    operation_mode: str
    quality_tier: str
    credits_used: int
    model_usages: list[ModelUsage] = field(default_factory=list)
    _total_cost_override: float | None = field(default=None)

    @property
    def total_cost(self) -> float:
        if self._total_cost_override is not None:
            return self._total_cost_override
        return sum(m.total_cost for m in self.model_usages if not m.was_refusal)

    @property
    def total_input_tokens(self) -> int:
        return sum(m.input_tokens for m in self.model_usages)

    @property
    def total_output_tokens(self) -> int:
        return sum(m.output_tokens for m in self.model_usages)

    @property
    def total_duration(self) -> float:
        return sum(m.duration_seconds for m in self.model_usages)

    @property
    def most_expensive_model(self) -> ModelUsage | None:
        if not self.model_usages:
            return None
        return max(self.model_usages, key=lambda m: m.total_cost)

    def format_breakdown(self) -> str:
        lines = [
            "── Task Cost Breakdown ─────────────────────────",
            f"{self.task_title} │ {self.operation_mode.capitalize()} │ {self.quality_tier.capitalize()} Tier",  # noqa: E501
            "",
            "Model                │ Tokens In/Out │  Cost  │ Time",
            "─────────────────────┼───────────────┼────────┼──────",
        ]

        for m in self.model_usages:
            in_k = m.input_tokens / 1000
            out_k = m.output_tokens / 1000
            time_str = f"{m.duration_seconds:.1f}s"
            # format columns
            name_padded = f"{m.model_display_name} ({m.role[:4]})".ljust(20)
            tokens_padded = f"{in_k:.1f}K / {out_k:.1f}K".center(15)
            cost_padded = f"${m.total_cost:.3f}".center(8)
            time_padded = time_str.ljust(6)
            lines.append(f"{name_padded} │ {tokens_padded} │ {cost_padded} │ {time_padded}")

        lines.append("─────────────────────┼───────────────┼────────┼──────")
        tot_in_k = self.total_input_tokens / 1000
        tot_out_k = self.total_output_tokens / 1000
        lines.append(
            f"{'Total'.ljust(20)} │ {f'{tot_in_k:.1f}K / {tot_out_k:.1f}K'.center(15)} │ {f'${self.total_cost:.3f}'.center(8)} │ {f'{self.total_duration:.1f}s'.ljust(6)}"  # noqa: E501
        )
        lines.append(f"Credits used: {self.credits_used}")
        return "\n".join(lines)


@dataclass
class DailySpend:
    date: date
    task_count: int = 0
    total_cost: float = 0.0
    total_credits: int = 0
    by_model: dict[str, float] = field(default_factory=dict)
    by_mode: dict[str, float] = field(default_factory=dict)


class CostBreakdownTracker:
    def __init__(self, storage_path: str | None = None) -> None:
        self._today: DailySpend = DailySpend(date=date.today())
        self._current_task: TaskCostBreakdown | None = None
        self._task_history: list[TaskCostBreakdown] = []
        self._session_start_idx: int = 0  # Track where this session starts in history

        # Local JSON state
        import os
        from pathlib import Path

        if storage_path:
            self._storage_path = Path(storage_path)
        elif os.environ.get("ENVIRONMENT") == "testing":
            self._storage_path = Path("/tmp/gptcgt_test_spending.json")
        else:
            self._storage_path = Path.home() / ".gptcgt" / "spending.json"

        self.load_from_disk()

    def start_task(self, task_id: str, title: str, mode: str, tier: str, credits: int) -> None:
        self._current_task = TaskCostBreakdown(
            task_id=task_id,
            task_title=title,
            operation_mode=mode,
            quality_tier=tier,
            credits_used=credits,
        )
        logger.info(
            f"Started task costing: {title}",
            extra={"structured_data": {"mode": mode, "tier": tier, "credits": credits}},
        )

    def record_model_usage(self, usage: ModelUsage) -> None:
        if self._current_task:
            self._current_task.model_usages.append(usage)

            # Update running totals
            self._today.total_cost += usage.total_cost
            self._today.by_model[usage.model_id] = self._today.by_model.get(usage.model_id, 0.0) + usage.total_cost
            self._today.by_mode[self._current_task.operation_mode] = (
                self._today.by_mode.get(self._current_task.operation_mode, 0.0) + usage.total_cost
            )

    def finish_task(self) -> TaskCostBreakdown:
        if not self._current_task:
            # Fallback if finished without start
            return TaskCostBreakdown("unknown", "Unknown", "standard", "standard", 0)

        self._today.task_count += 1
        self._today.total_credits += self._current_task.credits_used
        self._task_history.append(self._current_task)
        res = self._current_task
        self._current_task = None
        self.save_to_disk()

        # Broadcast the credits ping so the status bar updates
        try:
            import textual.app as _tapp

            from src.core.events import CreditsUpdated

            _cur_app = _tapp.active_app.get()
            # Use real values from auth_manager if available, else fall back to 0
            credits_remaining = 0
            credits_monthly = 0
            if hasattr(_cur_app, "auth_manager"):
                credits_remaining = getattr(_cur_app.auth_manager, "credits_remaining", 0)
                credits_monthly = getattr(_cur_app.auth_manager, "credits_monthly", 0)
            _cur_app.post_message(
                CreditsUpdated(
                    credits_remaining=credits_remaining,
                    credits_monthly=credits_monthly,
                )
            )
        except Exception as e:
            logger.debug(f"Could not post CreditsUpdated event: {e}")

        return res

    def get_today_spend(self) -> DailySpend:
        return self._today

    def get_monthly_spend(self) -> float:
        today = date.today()
        return (
            sum(
                t.total_cost
                for t in self._task_history
                if hasattr(t, "_recorded_date")
                and t._recorded_date
                and t._recorded_date.month == today.month
                and t._recorded_date.year == today.year
            )
            or self._today.total_cost
        )  # fallback to today if no date metadata

    def get_session_spend(self) -> float:
        return sum(t.total_cost for t in self._task_history[self._session_start_idx :])

    def get_model_ranking(self) -> list[dict]:
        # Based on today only for now in local state
        ranking = []
        for model_id, cost in self._today.by_model.items():
            ranking.append(
                {
                    "model": model_id,
                    "total_cost": cost,
                    "task_count": self._today.task_count,  # approximation
                }
            )
        return sorted(ranking, key=lambda x: x["total_cost"], reverse=True)

    def save_to_disk(self) -> None:
        try:
            import json

            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "date": self._today.date.isoformat(),
                "task_count": self._today.task_count,
                "total_cost": self._today.total_cost,
                "total_credits": self._today.total_credits,
                "by_model": self._today.by_model,
                "by_mode": self._today.by_mode,
                # Persist last 90 days of task history for the monthly spend view
                "task_history": [
                    {
                        "task_id": t.task_id,
                        "task_title": t.task_title,
                        "operation_mode": t.operation_mode,
                        "quality_tier": t.quality_tier,
                        "credits_used": t.credits_used,
                        "total_cost": t.total_cost,
                    }
                    for t in self._task_history[-270:]  # ~90 days * 3 tasks/day
                ],
            }
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save local spending data: {e}")

    def load_from_disk(self) -> None:
        try:
            import json

            if self._storage_path.exists():
                with open(self._storage_path, "r") as f:
                    data = json.load(f)

                # Restore today's running totals if the file is from today
                if data.get("date") == self._today.date.isoformat():
                    self._today.task_count = data.get("task_count", 0)
                    self._today.total_cost = data.get("total_cost", 0.0)
                    self._today.total_credits = data.get("total_credits", 0)
                    self._today.by_model = data.get("by_model", {})
                    self._today.by_mode = data.get("by_mode", {})

                # Restore historical task records (for monthly spend view)
                for rec in data.get("task_history", []):
                    try:
                        task = TaskCostBreakdown(
                            task_id=rec["task_id"],
                            task_title=rec["task_title"],
                            operation_mode=rec["operation_mode"],
                            quality_tier=rec["quality_tier"],
                            credits_used=rec["credits_used"],
                        )
                        # CRITICAL: Restore total_cost so get_monthly_spend() sums correctly.
                        # Using override because total_cost is a computed property.
                        task._total_cost_override = rec.get("total_cost", 0.0)
                        self._task_history.append(task)
                    except Exception as e:
                        logger.debug(f"Skipping malformed history record: {e}")
        except Exception as e:
            logger.warning(f"Failed to load local spending data: {e}")
