import json

import pytest
import structlog


def test_logs_are_json_and_carry_bound_request_id(capsys: pytest.CaptureFixture[str]) -> None:
    from codedoc.structured_logging import configure_logging

    configure_logging()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="req-test-1234")

    structlog.get_logger().info("ingestion_started", repository_id="abc123def456")

    captured_line = capsys.readouterr().out.strip().splitlines()[-1]
    log_record = json.loads(captured_line)
    assert log_record["event"] == "ingestion_started"
    assert log_record["request_id"] == "req-test-1234"
    assert log_record["repository_id"] == "abc123def456"
    assert log_record["level"] == "info"
    assert "timestamp" in log_record
