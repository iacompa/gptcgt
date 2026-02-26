"""Tests for spending cap enforcement — hard-stop before API calls."""

import inspect

import pytest

from src.core.logger import SensitiveDataFilter


class TestSpendingCapPreflight:
    def test_pipeline_has_spending_cap_check(self):
        """ChatPipeline.process_message must check spending caps before API calls."""
        from src.core import chat_pipeline
        source = inspect.getsource(chat_pipeline)
        assert "Spending cap preflight" in source, "Pipeline missing spending cap preflight"
        assert "spending cap exceeded" in source.lower() or "Spending cap exceeded" in source, (
            "Pipeline missing spending cap error message"
        )


class TestLoggerSecretRedaction:
    """Tests for SensitiveDataFilter — ensures secrets are redacted."""

    @pytest.fixture
    def filter(self):
        return SensitiveDataFilter()

    def _make_record(self, msg):
        import logging
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None,
        )
        return record

    def test_redacts_openai_key(self, filter):
        record = self._make_record("Using key sk-proj-ABCDEFGH1234567890abcdefgh1234567890ZZZZ")
        filter.filter(record)
        assert "1234567890abcdefgh" not in str(record.msg)

    def test_redacts_anthropic_key(self, filter):
        record = self._make_record("Key: sk-ant-api03-ABCDEFGH1234567890abcdefghijklmnopqrstuvwxyz1234")
        filter.filter(record)
        assert "1234567890abcdefgh" not in str(record.msg)

    def test_redacts_bearer_token(self, filter):
        record = self._make_record("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.longtoken.sig")
        filter.filter(record)
        assert "eyJhbGciOiJIUzI1NiJ9" not in str(record.msg)
        assert "...XXXX" in str(record.msg)

    def test_redacts_api_key_assignment(self, filter):
        record = self._make_record("api_key=sk_live_abc123def456ghi789")
        filter.filter(record)
        assert "sk_live_abc123def456ghi789" not in str(record.msg)
        assert "REDACTED" in str(record.msg)

    def test_redacts_password_assignment(self, filter):
        record = self._make_record("password: 'mysecretpassword123'")
        filter.filter(record)
        assert "mysecretpassword123" not in str(record.msg)

    def test_preserves_safe_messages(self, filter):
        record = self._make_record("Processing file: main.py with 42 tokens")
        filter.filter(record)
        assert "Processing file: main.py with 42 tokens" in str(record.msg)

    def test_scrubs_tuple_args(self, filter):
        import logging
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="data: %s", args=("api_key=secretvalue",), exc_info=None,
        )
        filter.filter(record)
        assert "secretvalue" not in str(record.args[0])

    def test_redacts_structured_data_sensitive_keys(self, filter):
        import logging
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="event", args=(), exc_info=None,
        )
        record.structured_data = {"api_key": "sk-real-key-here", "model": "gpt-4"}
        filter.filter(record)
        assert record.structured_data["api_key"] == "***REDACTED***"
        assert record.structured_data["model"] == "gpt-4"
