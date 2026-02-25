from __future__ import annotations

from textual.widgets import Static

from src.billing.cost_breakdown import TaskCostBreakdown


class CostSummaryWidget(Static):
    """
    Renders a compact cost breakdown after each task.
    Shown in the chat panel, right after the agent's response.
    """

    DEFAULT_CSS = """
    CostSummaryWidget {
        background: $surface;
        border: round $secondary;
        padding: 1 2;
        margin: 1 0;
        width: 100%;
        height: auto;
    }
    """

    def __init__(self, breakdown: TaskCostBreakdown, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.breakdown = breakdown
        self._expanded = False

    def on_click(self) -> None:
        self._expanded = not self._expanded
        self.refresh()

    def render(self) -> str:
        if self._expanded:
            return self.breakdown.format_breakdown()

        # Compact view
        in_k = self.breakdown.total_input_tokens / 1000
        out_k = self.breakdown.total_output_tokens / 1000

        line1 = f"─── Cost: ${self.breakdown.total_cost:.3f} │ {self.breakdown.credits_used} credits │ {in_k:.1f}K/{out_k:.1f}K tokens │ {self.breakdown.total_duration:.1f}s ───"  # noqa: E501

        models_summary = []
        for m in self.breakdown.model_usages:
            if m.was_refusal:
                continue
            models_summary.append(
                f"{m.model_display_name} ${m.total_cost:.3f} ({m.duration_seconds:.1f}s)"
            )

        line2 = " • ".join(models_summary)
        return f"{line1}\n    {line2}"
