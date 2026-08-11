"""
Run a quick test with a specific Langfuse prompt label.
Usage:
  python scripts/run_with_label.py --label candidate
  python scripts/run_with_label.py --label production
  python scripts/run_with_label.py --label baseline
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# ── Load .env (override mode) ─────────────────────────────────────────────────
env_file = REPO_ROOT / ".env"
if env_file.exists():
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and val:
            os.environ[key] = val
# ─────────────────────────────────────────────────────────────────────────────

os.environ.setdefault("LOG_PATH", "data/logs.jsonl")
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("APP_NAME", "day13-observability-lab")

parser = argparse.ArgumentParser(description="Run test queries with a specific prompt label")
parser.add_argument("--label", required=True, help="Langfuse prompt label (e.g. production, candidate, baseline)")
parser.add_argument("--count", type=int, default=5, help="Number of queries to send (default: 5)")
parser.add_argument("--clear-logs", action="store_true", help="Clear existing logs before running")
args = parser.parse_args()

# Override label BEFORE importing app
os.environ["LANGFUSE_PROMPT_LABEL"] = args.label
print(f"\n{'='*60}")
print(f"Running with LANGFUSE_PROMPT_LABEL={args.label}")
pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
if pk and sk:
    print(f"Langfuse: ✓ keys loaded (pk={pk[:8]}...)")
else:
    print("Langfuse: ⚠ keys missing — traces won't push to cloud")
print(f"{'='*60}\n")

from fastapi.testclient import TestClient
from app import logging_config
from app.main import app

log_path = REPO_ROOT / "data" / "logs.jsonl"
log_path.parent.mkdir(exist_ok=True)
logging_config.LOG_PATH = log_path

if args.clear_logs and log_path.exists():
    log_path.unlink()
    print(f"Cleared {log_path}")

# Subset of queries to test with the new label
QUERIES = [
    {"user_id": "label-01", "session_id": f"label-{args.label}-01", "feature": "qa",
     "message": "What is observability and why does it matter?"},
    {"user_id": "label-02", "session_id": f"label-{args.label}-02", "feature": "monitoring",
     "message": "How do I detect a latency spike using traces?"},
    {"user_id": "label-03", "session_id": f"label-{args.label}-03", "feature": "summary",
     "message": "Summarize the key differences between logging and tracing"},
    {"user_id": "label-04", "session_id": f"label-{args.label}-04", "feature": "qa",
     "message": "What PII should never appear in application logs?"},
    {"user_id": "label-05", "session_id": f"label-{args.label}-05", "feature": "qa",
     "message": "Explain prompt versioning and how to rollback safely"},
][:args.count]

correlation_ids = []
with TestClient(app) as client:
    for i, payload in enumerate(QUERIES, 1):
        try:
            r = client.post("/chat", json=payload)
            if r.status_code == 200:
                data = r.json()
                cid = data.get("correlation_id", "MISSING")
                correlation_ids.append(cid)
                print(f"[{i}] OK  | label={args.label} | cid={cid} | lat={data.get('latency_ms')}ms")
            else:
                print(f"[{i}] ERR | status={r.status_code}")
        except Exception as e:
            print(f"[{i}] EXC | {e}")

print(f"\nCorrelation IDs for label='{args.label}':")
for cid in correlation_ids:
    print(f"  {cid}")
print("\n→ Tìm các trace này trên Langfuse để xem prompt_label và prompt_version")
