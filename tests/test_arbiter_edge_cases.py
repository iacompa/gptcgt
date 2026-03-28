from src.core.arbiter import Arbiter, ArbiterScore


def _score(
    *, model_id: str, model_name: str, total_score: float, eliminated: bool = False
) -> ArbiterScore:
    return ArbiterScore(
        agent_id=f"agent-{model_id}",
        model_name=model_name,
        model_id=model_id,
        total_score=total_score,
        eliminated=eliminated,
    )


def test_produce_verdict_prefers_non_eliminated_over_higher_scoring_eliminated():
    arbiter = Arbiter.__new__(Arbiter)
    winner_candidate = _score(model_id="openai/gpt-4o", model_name="GPT-4o", total_score=99.0, eliminated=True)
    stable_candidate = _score(model_id="anthropic/claude-4-sonnet", model_name="Claude 4", total_score=42.0)

    verdict = arbiter._produce_verdict("dispatch-test", [winner_candidate, stable_candidate], total_ms=10)

    assert verdict.winner.model_id == "anthropic/claude-4-sonnet"
    assert not verdict.winner.eliminated
    assert verdict.runner_up is None


def test_produce_verdict_returns_winner_when_only_eliminated():
    arbiter = Arbiter.__new__(Arbiter)
    first = _score(model_id="openai/gpt-4o", model_name="GPT-4o", total_score=50.0, eliminated=True)
    second = _score(model_id="anthropic/claude-4-sonnet", model_name="Claude", total_score=10.0, eliminated=True)

    verdict = arbiter._produce_verdict("dispatch-test", [first, second], total_ms=12)

    assert verdict.winner.model_id == "openai/gpt-4o"
    assert verdict.winner.eliminated
    assert verdict.comparison_summary == "All agent solutions failed structural validation."
