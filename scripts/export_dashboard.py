import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.dashboard_view import get_dashboard_metrics

def main() -> None:
    configure_utf8_stdio()
    data = get_dashboard_metrics()
    print("=" * 60)
    print(" DAY 13 AI OBSERVABILITY DASHBOARD SUMMARY")
    print(f" Time Window: {data['time_range_minutes']}m | Total Log Records: {data['total_records']}")
    print("=" * 60)
    
    for panel_id, p in data["panels"].items():
        status_symbol = "✅ [PASS]" if p["status"] == "PASS" else "❌ [BREACH]"
        thresh_info = f"(Threshold: {p['threshold']['operator']} {p['threshold']['value']} {p['threshold'].get('unit','')})"
        print(f"\n[{p['title'].upper()}] - {status_symbol} {thresh_info}")
        for k, v in p.items():
            if k not in ("id", "title", "threshold", "status"):
                print(f"  • {k}: {v}")
                
    # Save a JSON snapshot of metrics to evidence
    evidence_dir = Path("submission/evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = evidence_dir / "dashboard_metrics_snapshot.json"
    snapshot_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[Snapshot exported to {snapshot_path}]")

if __name__ == "__main__":
    main()
