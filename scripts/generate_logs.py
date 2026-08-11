"""
Generate logs locally using FastAPI TestClient (no uvicorn needed).
This script simulates 15 requests, ensuring data/logs.jsonl has proper
correlation IDs, enrichment fields, and PII-redacted content.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure we run from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Set env vars before importing app
os.environ.setdefault("LOG_PATH", "data/logs.jsonl")
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("APP_NAME", "day13-observability-lab")

# Load .env if present
env_file = REPO_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

from fastapi.testclient import TestClient
from app import logging_config
from app.main import app

# Use the real log path
log_path = REPO_ROOT / "data" / "logs.jsonl"
log_path.parent.mkdir(exist_ok=True)
logging_config.LOG_PATH = log_path

QUERIES = [
    {"user_id": "u01", "session_id": "s01", "feature": "qa", "message": "What is your refund policy? My email is student@vinuni.edu.vn"},
    {"user_id": "u02", "session_id": "s02", "feature": "qa", "message": "Explain why metrics traces and logs work together"},
    {"user_id": "u03", "session_id": "s03", "feature": "summary", "message": "Summarize the monitoring policy for production logging"},
    {"user_id": "u04", "session_id": "s04", "feature": "qa", "message": "Can I get help with policy and monitoring?"},
    {"user_id": "u05", "session_id": "s05", "feature": "qa", "message": "Here is my phone 0987654321, what should be logged?"},
    {"user_id": "u06", "session_id": "s06", "feature": "summary", "message": "Give me a short summary of the observability workflow"},
    {"user_id": "u07", "session_id": "s07", "feature": "qa", "message": "What should not appear in app logs?"},
    {"user_id": "u08", "session_id": "s08", "feature": "qa", "message": "How do I debug tail latency?"},
    {"user_id": "u09", "session_id": "s09", "feature": "qa", "message": "What is the policy for PII and credit card 4111 1111 1111 1111?"},
    {"user_id": "u10", "session_id": "s10", "feature": "qa", "message": "How should alerts be designed?"},
    {"user_id": "u11", "session_id": "s11", "feature": "monitoring", "message": "What is P95 latency and why does it matter?"},
    {"user_id": "u12", "session_id": "s12", "feature": "monitoring", "message": "Explain the difference between tracing and logging"},
    {"user_id": "u13", "session_id": "s13", "feature": "summary", "message": "What are the key SLOs for an AI API service?"},
    {"user_id": "u14", "session_id": "s14", "feature": "qa", "message": "How do I set up correlation IDs in a FastAPI app?"},
    {"user_id": "u15", "session_id": "s15", "feature": "qa", "message": "Contact me at +84 90 123 4567 to discuss observability"},
]


def main() -> None:
    # Clear existing logs to get a clean run
    if log_path.exists():
        log_path.unlink()
        print(f"Cleared existing {log_path}")

    successes = 0
    failures = 0

    with TestClient(app) as client:
        for i, payload in enumerate(QUERIES, 1):
            try:
                r = client.post("/chat", json=payload)
                if r.status_code == 200:
                    data = r.json()
                    cid = data.get("correlation_id", "MISSING")
                    print(f"[{i:02d}] OK  | cid={cid} | feature={payload['feature']} | lat={data.get('latency_ms')}ms")
                    successes += 1
                else:
                    print(f"[{i:02d}] ERR | status={r.status_code}")
                    failures += 1
            except Exception as e:
                print(f"[{i:02d}] EXC | {e}")
                failures += 1

    print(f"\nDone: {successes} success, {failures} failures")
    print(f"Log file: {log_path} ({log_path.stat().st_size if log_path.exists() else 0} bytes)")

    # Quick log inspection
    if log_path.exists():
        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        api_records = [r for r in records if r.get("service") == "api"]
        cids = {r.get("correlation_id") for r in records if r.get("correlation_id") and r.get("correlation_id") != "MISSING"}
        print(f"Total records: {len(records)} | API records: {len(api_records)} | Unique correlation IDs: {len(cids)}")
        
        # Check a sample record
        if api_records:
            sample = api_records[0]
            print("\nSample log record fields:", list(sample.keys()))


if __name__ == "__main__":
    main()
