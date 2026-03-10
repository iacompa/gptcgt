"""Tests for Phase 3: Autonomy Blast-Radius Controls."""



def test_guardrail_low_risk():
    """Small change set within limits → LOW risk, allowed."""
    from src.core.guardrails import GuardrailEvaluator

    evaluator = GuardrailEvaluator()
    preview = evaluator.evaluate(["src/core/foo.py", "src/core/bar.py"], lines_added=50, lines_removed=10)

    assert preview.allowed is True
    assert preview.risk_level.value == "low"
    assert len(preview.violations) == 0


def test_guardrail_blocks_excessive_files():
    """Too many files → BLOCKED."""
    from src.core.guardrails import BlastRadiusPolicy, GuardrailEvaluator

    policy = BlastRadiusPolicy(max_files=3)
    evaluator = GuardrailEvaluator(policy)
    files = [f"src/file_{i}.py" for i in range(10)]

    preview = evaluator.evaluate(files, lines_added=20)
    assert preview.allowed is False
    assert preview.risk_level.value == "blocked"
    assert any("Files changed" in v for v in preview.violations)


def test_guardrail_blocks_excessive_lines():
    """Too many lines → BLOCKED."""
    from src.core.guardrails import BlastRadiusPolicy, GuardrailEvaluator

    policy = BlastRadiusPolicy(max_lines_changed=100)
    evaluator = GuardrailEvaluator(policy)

    preview = evaluator.evaluate(["src/big_file.py"], lines_added=80, lines_removed=50)
    assert preview.allowed is False
    assert any("Lines changed" in v for v in preview.violations)


def test_guardrail_detects_sensitive_paths():
    """Protected paths → HIGH risk, requires approval."""
    from src.core.guardrails import GuardrailEvaluator

    evaluator = GuardrailEvaluator()
    preview = evaluator.evaluate(
        ["src/billing/stripe_service.py", "src/core/foo.py"],
        lines_added=10,
    )

    assert preview.requires_approval is True
    assert preview.risk_level.value == "high"
    assert "billing" in preview.change_summary.sensitive_categories


def test_guardrail_sensitive_within_limits():
    """One sensitive file within limit → requires approval but not blocked."""
    from src.core.guardrails import BlastRadiusPolicy, GuardrailEvaluator

    policy = BlastRadiusPolicy(max_sensitive_files=5, require_approval_for_protected=True)
    evaluator = GuardrailEvaluator(policy)

    preview = evaluator.evaluate(["src/auth/middleware.py"], lines_added=5)
    assert preview.requires_approval is True
    assert preview.risk_level.value == "high"
    # Not blocked, just needs approval
    assert len(preview.violations) == 0


def test_guardrail_risk_preview_text():
    """Risk preview renders readable text."""
    from src.core.guardrails import GuardrailEvaluator

    evaluator = GuardrailEvaluator()
    preview = evaluator.evaluate(["src/billing/x.py"], lines_added=5)
    text = preview.to_text()

    assert "Risk Preview" in text
    assert "billing" in text.lower()
