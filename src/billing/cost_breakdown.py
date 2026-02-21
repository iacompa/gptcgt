from dataclasses import dataclass, field
from datetime import datetime, date

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

    @property
    def total_cost(self) -> float:
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
            f"{self.task_title} │ {self.operation_mode.capitalize()} │ {self.quality_tier.capitalize()} Tier",
            "",
            "Model                │ Tokens In/Out │  Cost  │ Time",
            "─────────────────────┼───────────────┼────────┼──────"
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
        lines.append(f"{'Total'.ljust(20)} │ {f'{tot_in_k:.1f}K / {tot_out_k:.1f}K'.center(15)} │ {f'${self.total_cost:.3f}'.center(8)} │ {f'{self.total_duration:.1f}s'.ljust(6)}")
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
    def __init__(self) -> None:
        self._today: DailySpend = DailySpend(date=date.today())
        self._current_task: TaskCostBreakdown | None = None
        self._task_history: list[TaskCostBreakdown] = []

    def start_task(self, task_id: str, title: str, mode: str, tier: str, credits: int) -> None:
        self._current_task = TaskCostBreakdown(
            task_id=task_id,
            task_title=title,
            operation_mode=mode,
            quality_tier=tier,
            credits_used=credits
        )

    def record_model_usage(self, usage: ModelUsage) -> None:
        if self._current_task:
            self._current_task.model_usages.append(usage)
            
            # Update running totals
            self._today.total_cost += usage.total_cost
            self._today.by_model[usage.model_id] = self._today.by_model.get(usage.model_id, 0.0) + usage.total_cost
            self._today.by_mode[self._current_task.operation_mode] = self._today.by_mode.get(self._current_task.operation_mode, 0.0) + usage.total_cost

    def finish_task(self) -> TaskCostBreakdown:
        if not self._current_task:
            # Fallback if finished without start
            return TaskCostBreakdown("unknown", "Unknown", "standard", "standard", 0)
            
        self._today.task_count += 1
        self._today.total_credits += self._current_task.credits_used
        self._task_history.append(self._current_task)
        res = self._current_task
        self._current_task = None
        return res

    def get_today_spend(self) -> DailySpend:
        return self._today

    def get_monthly_spend(self) -> float:
        return self._today.total_cost # Simple stub for current session

    def get_session_spend(self) -> float:
        return sum(t.total_cost for t in self._task_history)

    def get_model_ranking(self, days: int = 30) -> list[dict]:
        # Based on today only for now in local state
        ranking = []
        for model_id, cost in self._today.by_model.items():
            ranking.append({
                "model": model_id,
                "total_cost": cost,
                "task_count": self._today.task_count # approximation
            })
        return sorted(ranking, key=lambda x: x["total_cost"], reverse=True)

    def check_overage(self, plan_credits: int, used_credits: int) -> dict:
        remaining = plan_credits - used_credits
        return {
            "credits_remaining": remaining,
            "is_over_limit": remaining < 0,
            "overage_credits": abs(remaining) if remaining < 0 else 0,
            "overage_cost": abs(remaining) * 0.025 if remaining < 0 else 0.0,
            "warning_level": "over" if remaining < 0 else "critical" if remaining < plan_credits * 0.05 else "warning" if remaining < plan_credits * 0.2 else "normal"
        }

    def save_to_disk(self) -> None:
        pass

    def load_from_disk(self, days: int = 30) -> None:
        pass
