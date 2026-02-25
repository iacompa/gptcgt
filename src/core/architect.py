"""
Architect Mode Pipeline.

In Architect mode, AI agents do not write code directly.
1. The user provides a task.
2. 2-3 models compete to write the best IMPLEMENTATION PLAN (not code).
3. The Arbiter evaluates the plans based on clarity, security awareness, and completeness.
4. The winning plan is presented to the user.
5. Once approved, the plan is fed into a single powerful Coder agent (e.g., Claude 3.5 Sonnet)
   to execute the full plan.

This matches the proven Planner + Coder workflow, but adds the parallel competition
layer to the planning phase.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import AsyncIterator

from src.core.arbiter import Arbiter, ArbiterScore, ArbiterVerdict
from src.core.logger import get_logger
from src.core.model_registry import ModelDefinition
from src.core.parallel_dispatcher import ParallelDispatch, ParallelDispatcher

logger = get_logger("core.architect")


@dataclass
class ArchitectPlan:
    """A proposed implementation plan from an agent."""

    agent_id: str
    model_name: str
    plan_text: str
    score: int = 0
    feedback: str = ""


class ArchitectPipeline:
    """Manages the full lifecycle of Architect Mode."""

    def __init__(self, parallel_dispatcher: ParallelDispatcher, arbiter: Arbiter) -> None:
        self._dispatcher = parallel_dispatcher
        self._arbiter = arbiter

    async def run_planning_phase(
        self,
        task_str: str,
        context_messages: list[dict],
        models: list[ModelDefinition],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """
        Phase 1: Competing planners.

        Yields events identical to parallel_dispatcher, but intercepts the
        final `all_complete` to run a specialized plan-only arbiter evaluation.
        """
        # Inject an architect-specific system prompt addition if we wanted to be strict,
        # but the mode manager already handles appending the architect instructions
        # to the system prompt (e.g. "You are an architect. Do not write code. Write a plan.")

        dispatch_events = self._dispatcher.dispatch(
            task_str=task_str,
            context_messages=context_messages,
            models=models,
            tools=tools,
            mode="architect",
        )

        dispatch: ParallelDispatch | None = None

        async for event in dispatch_events:
            if event["type"] == "all_complete":
                dispatch = event.get("dispatch")
                continue  # Intercept this, we need to evaluate first

            yield event

        if dispatch:
            # Run Plan Evaluation
            # We don't use the standard 6-stage arbiter here because there is no code to test!
            # Instead, we do a meta-evaluation (LLM-as-judge) just for the plans, or a heuristic score.  # noqa: E501
            # For gptcgt V1, we will do a fast heuristic evaluation of the plans.

            yield {"type": "architect_evaluating", "message": "Evaluating implementation plans..."}

            verdict = await self._evaluate_plans(dispatch)

            # Fire a modified verdict ready event
            yield {"type": "all_complete", "dispatch": dispatch}
            yield {"type": "arbiter_verdict", "verdict": verdict}

    async def _evaluate_plans(self, dispatch: ParallelDispatch) -> ArbiterVerdict:
        """
        Evaluate natural language implementation plans.
        Uses heuristics since we can't compile/test English.
        """
        start_ms = time.time()
        scores: list[ArbiterScore] = []

        for slot in dispatch.slots:
            if slot.status != "completed" or not slot.response_text:
                scores.append(
                    ArbiterScore(
                        agent_id=slot.agent_id,
                        model_name=slot.model.name,
                        model_id=slot.model.id,
                        eliminated=True,
                        elimination_reason="Failed to produce a plan",
                    )
                )
                continue

            text = slot.response_text.lower()
            score = ArbiterScore(
                agent_id=slot.agent_id,
                model_name=slot.model.name,
                model_id=slot.model.id,
                total_score=50.0,  # Base score
            )

            # Heuristics for a good plan:
            if "step 1" in text or "1." in text:
                score.total_score += 10
            if "security" in text or "safet" in text:
                score.total_score += 15
            if "test" in text or "verify" in text:
                score.total_score += 15
            if "edge case" in text or "error handling" in text:
                score.total_score += 10

            # Penalty for writing code blocks when asked not to
            if "```python" in text or "```ts" in text:
                score.total_score -= 20
                if score.total_score < 0:
                    score.total_score = 0

            scores.append(score)

        scores.sort(key=lambda x: (not x.eliminated, x.total_score), reverse=True)

        winner = (
            scores[0]
            if scores and not scores[0].eliminated
            else ArbiterScore(
                agent_id="none",
                model_name="none",
                model_id="none",
                eliminated=True,
                elimination_reason="No valid plans",
            )
        )

        runner_up = scores[1] if len(scores) > 1 and not scores[1].eliminated else None

        evidence = [f"{winner.model_name} provided the most structured and comprehensive plan."]

        total_ms = int((time.time() - start_ms) * 1000)

        return ArbiterVerdict(
            dispatch_id=dispatch.dispatch_id,
            scores=scores,
            winner=winner,
            runner_up=runner_up,
            comparison_summary=f"🏆 {winner.model_name} generated the best implementation plan.",
            evidence=evidence,
            confidence="medium",
            total_evaluation_ms=total_ms,
        )
