from __future__ import annotations

import json
import asyncio
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True


def test_chat_adds_correlation_headers_and_scrubs_pii(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                headers={"x-request-id": "req-test1234"},
                json={
                    "user_id": "student@vinuni.edu.vn",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Call 0901234567; card 4111 1111 1111 1111",
                },
            )

    response = asyncio.run(send_request())
    raw_logs = log_path.read_text(encoding="utf-8")
    events = [json.loads(line) for line in raw_logs.splitlines()]
    request_event = next(event for event in events if event["event"] == "request_received")

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-test1234"
    assert float(response.headers["x-response-time-ms"]) >= 0
    assert request_event["correlation_id"] == "req-test1234"
    assert request_event["user_id_hash"] != "student@vinuni.edu.vn"
    assert request_event["session_id"] == "session-01"
    assert request_event["feature"] == "qa"
    assert request_event["model"]
    assert request_event["env"]
    assert "0901234567" not in raw_logs
    assert "4111 1111 1111 1111" not in raw_logs
