"""Tests for Phase 5: Policy-as-Code for Teams."""



def test_policy_default_config():
    """Default PolicyConfig has sensible defaults."""
    from src.core.policy import PolicyConfig

    config = PolicyConfig()
    assert "lint" in config.required_checks
    assert "tests" in config.required_checks
    assert config.blast_radius["max_files"] == 15
    assert config.spending_caps["daily_limit_usd"] == 10.0
    assert "standard" in config.mode_caps["allowed_tiers"]


def test_policy_parser_missing_file(tmp_path):
    """Missing policy file returns defaults with no errors."""
    from src.core.policy import PolicyParser

    config, errors = PolicyParser.load(tmp_path)
    assert len(errors) == 0
    assert "lint" in config.required_checks


def test_policy_parser_valid_yaml(tmp_path):
    """Valid policy YAML is parsed correctly."""
    from src.core.policy import PolicyParser

    policy_dir = tmp_path / ".gptcgt"
    policy_dir.mkdir()
    (policy_dir / "policy.yml").write_text("""
version: "2"
protected_paths:
  - billing/
  - secrets/
required_checks:
  - lint
  - tests
blast_radius:
  max_files: 10
  max_lines: 300
mode_caps:
  allowed_tiers:
    - lite
    - standard
  default_tier: lite
spending_caps:
  daily_limit_usd: 5.0
  per_task_limit_usd: 1.0
""")

    config, errors = PolicyParser.load(tmp_path)
    assert len(errors) == 0
    assert config.version == "2"
    assert config.blast_radius["max_files"] == 10
    assert "lite" in config.mode_caps["allowed_tiers"]
    assert config.spending_caps["daily_limit_usd"] == 5.0


def test_policy_parser_invalid_check(tmp_path):
    """Invalid required_checks produce validation errors."""
    from src.core.policy import PolicyParser

    policy_dir = tmp_path / ".gptcgt"
    policy_dir.mkdir()
    (policy_dir / "policy.yml").write_text("""
required_checks:
  - lint
  - made_up_check
""")

    config, errors = PolicyParser.load(tmp_path)
    assert len(errors) == 1
    assert "made_up_check" in errors[0].message


def test_policy_enforcer_run_start_blocks_mode():
    """Policy enforcer blocks disallowed modes."""
    from src.core.policy import PolicyConfig, PolicyEnforcer

    config = PolicyConfig()
    config.mode_caps["allowed_tiers"] = ["lite", "standard"]
    enforcer = PolicyEnforcer(config)

    # MAX not allowed
    allowed, errors = enforcer.check_run_start(current_spend=0, mode="max")
    assert allowed is False
    assert any("max" in e for e in errors)

    # STANDARD allowed
    allowed, errors = enforcer.check_run_start(current_spend=0, mode="standard")
    assert allowed is True


def test_policy_enforcer_run_start_blocks_spending():
    """Policy enforcer blocks when spending cap reached."""
    from src.core.policy import PolicyConfig, PolicyEnforcer

    config = PolicyConfig()
    config.spending_caps["daily_limit_usd"] = 5.0
    enforcer = PolicyEnforcer(config)

    allowed, errors = enforcer.check_run_start(current_spend=5.0, mode="standard")
    assert allowed is False
    assert any("spending" in e.lower() or "limit" in e.lower() for e in errors)


def test_policy_enforcer_pre_apply_blocks_protected():
    """Policy enforcer blocks changes to protected paths."""
    from src.core.policy import PolicyConfig, PolicyEnforcer

    config = PolicyConfig()
    enforcer = PolicyEnforcer(config)

    # Touching billing/ should trigger policy block
    allowed, errors = enforcer.check_pre_apply(
        files_changed=["src/billing/stripe.py", "src/core/foo.py"],
        lines_changed=50,
    )
    assert allowed is False
    assert any("Protected" in e or "protected" in e.lower() for e in errors)


def test_policy_enforcer_pre_apply_allows_safe_changes():
    """Safe changes within limits are allowed."""
    from src.core.policy import PolicyConfig, PolicyEnforcer

    config = PolicyConfig()
    config.approval_rules["require_approval_for_protected"] = False
    enforcer = PolicyEnforcer(config)

    allowed, errors = enforcer.check_pre_apply(
        files_changed=["src/core/utils.py"],
        lines_changed=20,
    )
    assert allowed is True
    assert len(errors) == 0


def test_policy_enforcer_pre_pr_blocks_missing_checks():
    """Pre-PR gate blocks if required checks are missing."""
    from src.core.policy import PolicyConfig, PolicyEnforcer

    config = PolicyConfig()
    enforcer = PolicyEnforcer(config)

    # Only lint passed, missing tests/security/migration
    allowed, errors = enforcer.check_pre_pr({"lint": True})
    assert allowed is False
    assert len(errors) == 3  # tests, security, migration missing


def test_policy_enforcer_pre_pr_passes_all_checks():
    """Pre-PR gate passes when all required checks pass."""
    from src.core.policy import PolicyConfig, PolicyEnforcer

    config = PolicyConfig()
    enforcer = PolicyEnforcer(config)

    allowed, errors = enforcer.check_pre_pr({
        "lint": True,
        "tests": True,
        "security": True,
        "migration": True,
    })
    assert allowed is True
    assert len(errors) == 0
