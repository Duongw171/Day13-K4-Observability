from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import logging_config
from app.incidents import disable, enable
from app.main import app
from app.pii import hash_user_id


def _read_events(log_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_chat_propagates_supplied_request_id_and_enriches_logs(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setenv("APP_ENV", "test")
    payload = {
        "user_id": "student-01",
        "session_id": "session-01",
        "feature": "qa",
        "message": "Explain observability",
    }

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            headers={"x-request-id": "client-request-123"},
            json=payload,
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "client-request-123"
    assert response.json()["correlation_id"] == "client-request-123"
    assert response.headers["x-response-time-ms"].isdigit()

    api_events = [event for event in _read_events(log_path) if event.get("service") == "api"]
    assert {event["event"] for event in api_events} == {
        "request_received",
        "response_sent",
    }
    for event in api_events:
        assert event["correlation_id"] == "client-request-123"
        assert event["user_id_hash"] == hash_user_id(payload["user_id"])
        assert event["session_id"] == "session-01"
        assert event["feature"] == "qa"
        assert event["model"] == "claude-sonnet-4-5"
        assert event["env"] == "test"

    assert payload["user_id"] not in log_path.read_text(encoding="utf-8")


def test_invalid_or_sensitive_request_id_is_replaced(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            headers={"x-request-id": "0901234567"},
            json={
                "user_id": "student-02",
                "session_id": "session-02",
                "feature": "qa",
                "message": "Explain logs",
            },
        )

    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert "0901234567" not in log_path.read_text(encoding="utf-8")


def test_request_context_does_not_leak_between_requests(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    with TestClient(app) as client:
        for suffix in ("one", "two"):
            response = client.post(
                "/chat",
                headers={"x-request-id": f"request-{suffix}"},
                json={
                    "user_id": f"user-{suffix}",
                    "session_id": f"session-{suffix}",
                    "feature": suffix,
                    "message": "Explain metrics",
                },
            )
            assert response.status_code == 200

    api_events = [event for event in _read_events(log_path) if event.get("service") == "api"]
    events_by_request: dict[str, list[dict]] = {}
    for event in api_events:
        events_by_request.setdefault(event["correlation_id"], []).append(event)

    assert set(events_by_request) == {"request-one", "request-two"}
    for request_id, events in events_by_request.items():
        suffix = request_id.removeprefix("request-")
        assert len(events) == 2
        assert all(event["session_id"] == f"session-{suffix}" for event in events)
        assert all(event["feature"] == suffix for event in events)


def test_failed_request_keeps_correlation_and_enrichment(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    enable("tool_fail")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/chat",
                headers={"x-request-id": "failed-request"},
                json={
                    "user_id": "failed-user",
                    "session_id": "failed-session",
                    "feature": "qa",
                    "message": "Explain logs",
                },
            )
    finally:
        disable("tool_fail")

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "failed-request"
    failed_event = next(
        event for event in _read_events(log_path) if event["event"] == "request_failed"
    )
    assert failed_event["correlation_id"] == "failed-request"
    assert failed_event["user_id_hash"] == hash_user_id("failed-user")
    assert failed_event["session_id"] == "failed-session"
    assert failed_event["feature"] == "qa"
    assert failed_event["error_type"] == "RuntimeError"


def test_logging_processor_scrubs_nested_and_rendered_exception_pii(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    logger = logging_config.get_logger()

    try:
        raise RuntimeError("Contact student@vinuni.edu.vn or 0901234567")
    except RuntimeError:
        logger.exception(
            "pii_test_event",
            service="test",
            session_id="012345678901",
            payload={
                "contacts": [
                    "student@vinuni.edu.vn",
                    {"phone": "+84 90 123 4567"},
                ],
                "card": "4111 1111 1111 1111",
            },
        )

    raw_log = log_path.read_text(encoding="utf-8")
    for raw_pii in (
        "student@vinuni.edu.vn",
        "0901234567",
        "+84 90 123 4567",
        "012345678901",
        "4111 1111 1111 1111",
    ):
        assert raw_pii not in raw_log

    assert "REDACTED_EMAIL" in raw_log
    assert "REDACTED_PHONE_VN" in raw_log
    assert "REDACTED_CCCD" in raw_log
    assert "REDACTED_CREDIT_CARD" in raw_log
