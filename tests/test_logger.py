import logging  # noqa: I001
import shutil
import sys
import pytest

from src.core.logger import (
    GptcgtFormatter,
    LogBuffer,
    SensitiveDataFilter,
    setup_logging,
)


@pytest.fixture
def clean_log_dir(tmp_path):
    log_dir = tmp_path / ".gptcgt" / "logs"
    if log_dir.exists():
        shutil.rmtree(log_dir)
    return tmp_path


def test_logger_creates_log_directory(clean_log_dir):
    setup_logging(clean_log_dir)
    assert (clean_log_dir / ".gptcgt" / "logs").exists()
    assert (clean_log_dir / ".gptcgt" / "logs" / "gptcgt.log").exists()
    assert (clean_log_dir / ".gptcgt" / "logs" / "debug.log").exists()


def test_sensitive_data_filter_redacts_api_keys():
    filter_ = SensitiveDataFilter()
    record = logging.LogRecord(
        "test", logging.INFO, "test.py", 1, "Got key sk-ant-api03-abcdefgh12345678abcd", (), None
    )
    filter_.filter(record)
    assert record.msg == "Got key sk-ant-api03-abcdefgh...abcd"


def test_sensitive_data_filter_redacts_tokens():
    filter_ = SensitiveDataFilter()
    record = logging.LogRecord(
        "test", logging.INFO, "test.py", 1, "Bearer 1234567890abcdef", (), None
    )
    filter_.filter(record)
    assert record.msg == "Bearer ...XXXX"


def test_sensitive_data_filter_redacts_passwords():
    filter_ = SensitiveDataFilter()
    record = logging.LogRecord("test", logging.INFO, "test.py", 1, "test", (), None)
    record.structured_data = {"password": "my_super_secret_password"}
    filter_.filter(record)
    assert record.structured_data["password"] == "***REDACTED***"


def test_structured_data_appended():
    formatter = GptcgtFormatter()
    record = logging.LogRecord("test.component", logging.INFO, "test.py", 1, "My message", (), None)
    record.structured_data = {"credits": 5, "model": "claude"}
    formatted = formatter.format(record)
    assert "My message" in formatted
    assert "credits=5" in formatted
    assert "model=claude" in formatted
    assert "test.component" in formatted
    assert "INFO" in formatted

def test_formatter_redacts_exceptions():
    formatter = GptcgtFormatter()
    try:
        raise ValueError("Failed with token sk-ant-api03-abcdefgh12345678abcd")
    except ValueError as e:  # noqa: F841
        record = logging.LogRecord("test", logging.ERROR, "test.py", 1, "Error occurred", (), sys.exc_info())
        formatted = formatter.format(record)
        assert "sk-ant-api03-abcdefgh...abcd" in formatted
        assert "sk-ant-api03-abcdefgh12345678abcd" not in formatted


def test_log_buffer_stores_500_entries(clean_log_dir):
    # Ensure fresh instance
    LogBuffer._instance = None
    buffer = LogBuffer()
    formatter = GptcgtFormatter()
    buffer.setFormatter(formatter)

    for i in range(600):
        record = logging.LogRecord("test", logging.INFO, "test.py", 1, f"Message {i}", (), None)
        buffer.emit(record)

    recent = buffer.get_recent(500)
    assert len(recent) == 500
    assert "Message 599" in recent[-1]
    assert "Message 100" in recent[0]


def test_log_buffer_subscribe_callback(clean_log_dir):
    LogBuffer._instance = None
    buffer = LogBuffer()
    formatter = GptcgtFormatter()
    buffer.setFormatter(formatter)

    received = []

    def callback(msg):
        received.append(msg)

    buffer.subscribe(callback)

    record = logging.LogRecord("test", logging.INFO, "test.py", 1, "Test Callback", (), None)
    buffer.emit(record)

    assert len(received) == 1
    assert "Test Callback" in received[0]
