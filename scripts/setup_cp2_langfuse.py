from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PROMPT_NAME = "day13-chat"
PROMPT_V1 = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
PROMPT_V2 = (
    "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}\n"
    "Answer concisely in at most three sentences."
)
SESSION_ID = "cp2-langfuse-evidence"


def _prompt_exists(client) -> bool:
    return bool(client.api.prompts.list(name=PROMPT_NAME, limit=50).data)


def _ensure_prompt_versions(client) -> tuple[int, int]:
    if not _prompt_exists(client):
        version_1 = client.create_prompt(
            name=PROMPT_NAME,
            type="text",
            prompt=PROMPT_V1,
            labels=["baseline", "production"],
            commit_message="CP2 baseline prompt",
        )
        version_2 = client.create_prompt(
            name=PROMPT_NAME,
            type="text",
            prompt=PROMPT_V2,
            labels=["candidate"],
            commit_message="CP2 candidate: concise answer instruction",
        )
        return int(version_1.version), int(version_2.version)

    version_1 = client.get_prompt(PROMPT_NAME, version=1, cache_ttl_seconds=0)
    version_2 = client.get_prompt(PROMPT_NAME, version=2, cache_ttl_seconds=0)
    if version_1.prompt != PROMPT_V1 or version_2.prompt != PROMPT_V2:
        raise RuntimeError(
            "day13-chat already exists but versions 1/2 do not match this lab; "
            "refusing to overwrite personal prompt history"
        )
    return 1, 2


def _run_trace(label: str, correlation_id: str) -> None:
    os.environ["LANGFUSE_PROMPT_NAME"] = PROMPT_NAME
    os.environ["LANGFUSE_PROMPT_LABEL"] = label
    from app.agent import LabAgent

    LabAgent().run(
        user_id="cp2-student",
        feature="qa",
        session_id=SESSION_ID,
        message="Explain how metrics, logs, and traces work together.",
        correlation_id=correlation_id,
    )


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    from langfuse import get_client

    client = get_client()
    version_1, version_2 = _ensure_prompt_versions(client)

    # Compare the same input against the baseline and candidate labels.
    _run_trace("baseline", "req-cp2base")
    _run_trace("candidate", "req-cp2cand")

    # Promote v2, exercise production, then roll production back to v1.
    client.update_prompt(
        name=PROMPT_NAME,
        version=version_2,
        new_labels=["candidate", "production"],
    )
    _run_trace("production", "req-cp2prod")
    client.update_prompt(
        name=PROMPT_NAME,
        version=version_1,
        new_labels=["baseline", "production"],
    )
    _run_trace("production", "req-cp2roll")

    # Add six more production traces so the CP2 project has at least ten.
    for index in range(6):
        _run_trace("production", f"req-cp2{index:04x}")

    client.flush()
    time.sleep(2)

    baseline = client.get_prompt(PROMPT_NAME, label="baseline", cache_ttl_seconds=0)
    candidate = client.get_prompt(PROMPT_NAME, label="candidate", cache_ttl_seconds=0)
    production = client.get_prompt(PROMPT_NAME, label="production", cache_ttl_seconds=0)
    observations = client.api.observations.get_many(
        session_id=SESSION_ID,
        from_start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        to_start_time=datetime.now(timezone.utc),
        fields="basic,metadata,model,usage,prompt,metrics,trace_context",
        limit=100,
    ).data
    trace_ids = sorted({observation.trace_id for observation in observations})
    summary = {
        "prompt": PROMPT_NAME,
        "baseline_version": baseline.version,
        "candidate_version": candidate.version,
        "production_version_after_rollback": production.version,
        "trace_count": len(trace_ids),
        "observation_count": len(observations),
        "trace_ids": trace_ids,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
