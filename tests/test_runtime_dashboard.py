from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.dashboard import render_dashboard


def test_runtime_dashboard_renders_six_populated_panels(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    timestamp = datetime.now(timezone.utc).isoformat()
    records = [
        {"ts": timestamp, "event": "request_received"},
        {
            "ts": timestamp,
            "event": "response_sent",
            "latency_ms": 200,
            "ttft_ms": 50,
            "cost_usd": 0.001,
            "tokens_in": 25,
            "tokens_out": 100,
            "quality_score": 0.8,
            "tool_success": True,
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(record) for record in records), encoding="utf-8"
    )

    output = render_dashboard(log_path=log_path)

    for panel_id in ("latency", "traffic", "errors", "cost", "tokens", "quality"):
        assert f'id="{panel_id}"' in output
    assert "200 ms" in output
    assert "100.0%" in output
    assert "SLO line" in output
