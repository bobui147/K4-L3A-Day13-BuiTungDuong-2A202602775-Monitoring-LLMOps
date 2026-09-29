from __future__ import annotations

import html
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import yaml


LOG_PATH = Path("data/logs.jsonl")
CONFIG_PATH = Path("config/dashboard.yaml")


def _percentile(values: Iterable[float], percentile: int) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return float(
        ordered[lower] * (upper - position) + ordered[upper] * (position - lower)
    )


def _timestamp(record: dict[str, Any]) -> datetime | None:
    raw = record.get("ts")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_recent_records(
    path: Path = LOG_PATH, *, minutes: int = 60, now: datetime | None = None
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(minutes=minutes)
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = _timestamp(record)
        if timestamp is not None and timestamp >= cutoff:
            records.append(record)
    return records


def _status(value: float, operator: str, threshold: float) -> str:
    healthy = value <= threshold if operator == "lte" else value >= threshold
    return "healthy" if healthy else "breached"


def _metric(
    label: str,
    value: str,
    *,
    numeric_value: float | None = None,
    operator: str | None = None,
    threshold: float | None = None,
) -> str:
    status = ""
    if numeric_value is not None and operator and threshold is not None:
        status = _status(numeric_value, operator, threshold)
    return (
        f'<div class="metric {status}"><span>{html.escape(label)}</span>'
        f"<strong>{html.escape(value)}</strong></div>"
    )


def render_dashboard(
    log_path: Path = LOG_PATH, config_path: Path = CONFIG_PATH
) -> str:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))["dashboard"]
    records = load_recent_records(
        log_path, minutes=int(config["time_range_minutes"])
    )
    requests = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]

    latencies = [float(record["latency_ms"]) for record in responses if "latency_ms" in record]
    ttfts = [float(record["ttft_ms"]) for record in responses if "ttft_ms" in record]
    tool_results = [record.get("tool_success") for record in records if record.get("tool_success") is not None]
    retrieval_success = (
        100 * sum(result is True for result in tool_results) / len(tool_results)
        if tool_results
        else 0.0
    )
    error_rate = 100 * len(failures) / len(requests) if requests else 0.0
    error_types = Counter(str(record.get("error_type", "unknown")) for record in failures)
    total_cost = sum(float(record.get("cost_usd", 0)) for record in responses)
    tokens_in = sum(int(record.get("tokens_in", 0)) for record in responses)
    tokens_out = sum(int(record.get("tokens_out", 0)) for record in responses)
    quality_values = [float(record["quality_score"]) for record in responses if "quality_score" in record]
    quality = mean(quality_values) if quality_values else 0.0
    rpm = len(requests) / max(1, int(config["time_range_minutes"]))

    values: dict[str, list[str]] = {
        "latency": [
            _metric("P50", f"{_percentile(latencies, 50):.0f} ms"),
            _metric(
                "P95",
                f"{_percentile(latencies, 95):.0f} ms",
                numeric_value=_percentile(latencies, 95),
                operator="lte",
                threshold=3000,
            ),
            _metric("P99", f"{_percentile(latencies, 99):.0f} ms"),
            _metric("TTFT P95", f"{_percentile(ttfts, 95):.0f} ms"),
        ],
        "traffic": [
            _metric("Requests", str(len(requests))),
            _metric("Average rate", f"{rpm:.2f} req/min"),
        ],
        "errors": [
            _metric(
                "Error rate",
                f"{error_rate:.2f}%",
                numeric_value=error_rate,
                operator="lte",
                threshold=2,
            ),
            _metric("Errors by type", ", ".join(f"{k}: {v}" for k, v in error_types.items()) or "none"),
            _metric("Retrieval success", f"{retrieval_success:.1f}%"),
        ],
        "cost": [
            _metric(
                "Total",
                f"${total_cost:.6f}",
                numeric_value=total_cost,
                operator="lte",
                threshold=2.5,
            )
        ],
        "tokens": [
            _metric("Input", f"{tokens_in:,}"),
            _metric("Output", f"{tokens_out:,}"),
            _metric("Total", f"{tokens_in + tokens_out:,}"),
        ],
        "quality": [
            _metric(
                "Mean score",
                f"{quality:.2f}",
                numeric_value=quality,
                operator="gte",
                threshold=0.75,
            )
        ],
    }

    panels = []
    for panel in config["panels"]:
        threshold = panel["threshold"]
        cards = "".join(values[panel["id"]])
        panels.append(
            f'<section class="panel" id="{html.escape(panel["id"])}">'
            f'<div class="panel-head"><h2>{html.escape(panel["title"])}</h2>'
            f'<span class="unit">{html.escape(str(panel["unit"]))}</span></div>'
            f'<div class="metrics">{cards}</div>'
            f'<div class="threshold">SLO line: {html.escape(str(threshold["aggregation"]))} '
            f'{html.escape(str(threshold["operator"]))} {threshold["value"]}</div>'
            "</section>"
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="{int(config['refresh_seconds'])}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(config['title'])}</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #08111f; color: #e8eef8; }}
    header {{ padding: 26px 34px 18px; border-bottom: 1px solid #23324a; background: #0d1829; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    header p {{ margin: 0; color: #9eb0c9; }}
    main {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; padding: 22px 34px 34px; }}
    .panel {{ min-height: 220px; padding: 19px; border: 1px solid #263852; border-radius: 14px; background: linear-gradient(145deg, #111f33, #0c1727); box-shadow: 0 12px 30px #02071155; }}
    .panel-head {{ display: flex; align-items: start; justify-content: space-between; gap: 12px; }}
    h2 {{ margin: 0; font-size: 17px; }}
    .unit {{ color: #86a4ca; font-size: 12px; white-space: nowrap; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 22px; }}
    .metric {{ min-width: 115px; flex: 1; border-left: 3px solid #607a9e; padding: 7px 10px; background: #ffffff08; }}
    .metric span {{ display: block; color: #9eb0c9; font-size: 12px; margin-bottom: 5px; }}
    .metric strong {{ font-size: 21px; line-height: 1.15; }}
    .metric.healthy {{ border-color: #31c48d; }}
    .metric.breached {{ border-color: #f05252; }}
    .threshold {{ margin-top: 20px; padding-top: 12px; border-top: 1px dashed #31445f; color: #9eb0c9; font-size: 12px; }}
    @media (max-width: 950px) {{ main {{ grid-template-columns: 1fr 1fr; }} }}
    @media (max-width: 620px) {{ main {{ grid-template-columns: 1fr; padding: 16px; }} header {{ padding: 20px 16px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(config['title'])}</h1>
    <p>Live JSONL dashboard · Last {config['time_range_minutes']} minutes · Refresh {config['refresh_seconds']}s · {len(records)} records · {generated_at}</p>
  </header>
  <main>{''.join(panels)}</main>
</body>
</html>"""
