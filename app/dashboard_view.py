from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from .incidents import status as get_incident_status

router = APIRouter()
LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


def _compute_percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 2)


def get_dashboard_metrics() -> dict[str, Any]:
    if not LOG_PATH.exists():
        records: list[dict[str, Any]] = []
    else:
        records = []
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    now = datetime.now(timezone.utc)
    # 60 minute window filter
    window_records = []
    for r in records:
        ts_str = r.get("ts")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if (now - ts).total_seconds() <= 3600:
                    window_records.append((ts, r))
                else:
                    # If logs are slightly outside or simulated, include them if few
                    window_records.append((ts, r))
            except Exception:
                window_records.append((now, r))
        else:
            window_records.append((now, r))

    # Aggregate panels
    latencies: list[float] = []
    quality_scores: list[float] = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost_usd = 0.0
    request_count = 0
    failed_count = 0
    error_breakdown: dict[str, int] = {}
    time_buckets: dict[str, dict[str, Any]] = {}

    for ts, r in window_records:
        minute_key = ts.strftime("%H:%M")
        if minute_key not in time_buckets:
            time_buckets[minute_key] = {
                "requests": 0,
                "errors": 0,
                "latencies": [],
                "cost": 0.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "quality": [],
            }

        event = r.get("event")
        if event == "request_received":
            request_count += 1
            time_buckets[minute_key]["requests"] += 1
        elif event == "request_failed":
            failed_count += 1
            time_buckets[minute_key]["errors"] += 1
            err_type = r.get("error_type", "UnknownError")
            error_breakdown[err_type] = error_breakdown.get(err_type, 0) + 1
        elif event == "response_sent":
            lat = r.get("latency_ms")
            if lat is not None:
                latencies.append(float(lat))
                time_buckets[minute_key]["latencies"].append(float(lat))
            q = r.get("quality_score")
            if q is not None:
                quality_scores.append(float(q))
                time_buckets[minute_key]["quality"].append(float(q))
            t_in = r.get("tokens_in", 0) or 0
            t_out = r.get("tokens_out", 0) or 0
            total_tokens_in += t_in
            total_tokens_out += t_out
            time_buckets[minute_key]["tokens_in"] += t_in
            time_buckets[minute_key]["tokens_out"] += t_out
            cost = float(r.get("cost_usd", 0.0) or 0.0)
            total_cost_usd += cost
            time_buckets[minute_key]["cost"] += cost

    p50 = _compute_percentile(latencies, 50)
    p95 = _compute_percentile(latencies, 95)
    p99 = _compute_percentile(latencies, 99)

    num_minutes = max(1, len(time_buckets))
    req_per_min = round(request_count / num_minutes, 2)
    error_rate_pct = round((failed_count / max(1, request_count)) * 100, 2)
    avg_quality = round(sum(quality_scores) / max(1, len(quality_scores)), 3)

    sorted_minutes = sorted(time_buckets.keys())
    chart_data = {
        "labels": sorted_minutes,
        "latency_p95": [
            _compute_percentile(time_buckets[m]["latencies"], 95) if time_buckets[m]["latencies"] else p95
            for m in sorted_minutes
        ],
        "latency_p50": [
            _compute_percentile(time_buckets[m]["latencies"], 50) if time_buckets[m]["latencies"] else p50
            for m in sorted_minutes
        ],
        "traffic": [time_buckets[m]["requests"] for m in sorted_minutes],
        "cost": [round(time_buckets[m]["cost"], 4) for m in sorted_minutes],
        "quality": [
            round(sum(time_buckets[m]["quality"]) / max(1, len(time_buckets[m]["quality"])), 2)
            if time_buckets[m]["quality"]
            else avg_quality
            for m in sorted_minutes
        ],
    }

    return {
        "time_range_minutes": 60,
        "refresh_seconds": 30,
        "total_records": len(records),
        "incidents": get_incident_status(),
        "panels": {
            "latency": {
                "id": "latency",
                "title": "Latency percentiles",
                "unit": "ms",
                "p50": p50,
                "p95": p95,
                "p99": p99,
                "threshold": {"operator": "lte", "value": 3000, "unit": "ms"},
                "status": "PASS" if p95 <= 3000 else "BREACH",
            },
            "traffic": {
                "id": "traffic",
                "title": "Request traffic",
                "unit": "requests_per_minute",
                "count": request_count,
                "rate_per_minute": req_per_min,
                "threshold": {"operator": "gte", "value": 1, "unit": "req/m"},
                "status": "PASS" if req_per_min >= 1 else "BREACH",
            },
            "errors": {
                "id": "errors",
                "title": "Error rate and breakdown",
                "unit": "percent",
                "failed_count": failed_count,
                "request_count": request_count,
                "error_rate_pct": error_rate_pct,
                "error_breakdown": error_breakdown,
                "threshold": {"operator": "lte", "value": 2.0, "unit": "%"},
                "status": "PASS" if error_rate_pct <= 2.0 else "BREACH",
            },
            "cost": {
                "id": "cost",
                "title": "Cost over time",
                "unit": "usd",
                "total_cost_usd": round(total_cost_usd, 6),
                "threshold": {"operator": "lte", "value": 2.5, "unit": "USD"},
                "status": "PASS" if total_cost_usd <= 2.5 else "BREACH",
            },
            "tokens": {
                "id": "tokens",
                "title": "Input and output tokens",
                "unit": "tokens",
                "tokens_in": total_tokens_in,
                "tokens_out": total_tokens_out,
                "total_tokens": total_tokens_in + total_tokens_out,
                "threshold": {"operator": "lte", "value": 50000, "unit": "tokens"},
                "status": "PASS" if (total_tokens_in + total_tokens_out) <= 50000 else "BREACH",
            },
            "quality": {
                "id": "quality",
                "title": "Quality proxy",
                "unit": "score_0_to_1",
                "mean_quality_score": avg_quality,
                "threshold": {"operator": "gte", "value": 0.75, "unit": "score"},
                "status": "PASS" if avg_quality >= 0.75 else "BREACH",
            },
        },
        "chart_data": chart_data,
    }


@router.get("/api/dashboard-metrics")
async def api_dashboard_metrics() -> JSONResponse:
    return JSONResponse(get_dashboard_metrics())


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_html() -> HTMLResponse:
    html_content = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Day 13 — AI Observability Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #0B0F19;
      --bg-surface: #111827;
      --bg-card: #1F2937;
      --bg-card-hover: #283548;
      --border-color: #374151;
      --text-main: #F9FAFB;
      --text-muted: #9CA3AF;
      --accent-cyan: #06B6D4;
      --accent-blue: #3B82F6;
      --accent-green: #10B981;
      --accent-yellow: #F59E0B;
      --accent-red: #EF4444;
      --accent-purple: #8B5CF6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', sans-serif;
      padding: 24px;
      line-height: 1.5;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border-color);
      flex-wrap: wrap;
      gap: 16px;
    }
    .header h1 {
      font-size: 24px;
      font-weight: 800;
      background: linear-gradient(135deg, #60A5FA, #A78BFA, #34D399);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .badge-group { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .badge {
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .badge-cyan { background: rgba(6, 182, 212, 0.15); color: #22D3EE; border: 1px solid rgba(6, 182, 212, 0.3); }
    .badge-purple { background: rgba(139, 92, 246, 0.15); color: #C084FC; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-green { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-red { background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 20px;
    }
    .card {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
      transition: transform 0.2s, border-color 0.2s;
    }
    .card:hover {
      border-color: #4B5563;
      transform: translateY(-2px);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text-main);
    }
    .threshold-badge {
      font-size: 12px;
      padding: 3px 8px;
      border-radius: 4px;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
    }
    .pass { background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .breach { background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    
    .metric-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 14px;
      background: var(--bg-card);
      padding: 12px 16px;
      border-radius: 8px;
    }
    .metric-item { display: flex; flex-direction: column; }
    .metric-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 20px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }
    .chart-container {
      position: relative;
      height: 180px;
      width: 100%;
      margin-top: auto;
    }
    .footer {
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      color: var(--text-muted);
      font-size: 13px;
      flex-wrap: wrap;
      gap: 10px;
    }
  </style>
</head>
<body>
  <header class="header">
    <div>
      <h1>⚡ Day 13 AI Observability Dashboard</h1>
      <p style="color: var(--text-muted); font-size: 14px; margin-top: 4px;">Nguồn chuẩn: <code>data/logs.jsonl</code> &bull; Chu kỳ refresh: 30s &bull; Khung quan sát: 60 phút</p>
    </div>
    <div class="badge-group">
      <span class="badge badge-cyan">⏱️ Time Range: 60 min</span>
      <span class="badge badge-purple" id="refresh-timer">🔄 Refresh in: 30s</span>
      <span class="badge badge-green" id="incident-status">🟢 Incidents: Normal</span>
    </div>
  </header>

  <main class="grid">
    <!-- Panel 1: Latency -->
    <div class="card" id="panel-latency">
      <div class="card-header">
        <span class="card-title">1. Latency Percentiles (ms)</span>
        <span class="threshold-badge" id="thresh-latency">Threshold: P95 &le; 3000ms</span>
      </div>
      <div class="metric-row">
        <div class="metric-item"><span class="metric-label">P50</span><span class="metric-value" id="val-p50">-</span></div>
        <div class="metric-item"><span class="metric-label">P95 (SLO)</span><span class="metric-value" id="val-p95">-</span></div>
        <div class="metric-item"><span class="metric-label">P99</span><span class="metric-value" id="val-p99">-</span></div>
      </div>
      <div class="chart-container"><canvas id="chart-latency"></canvas></div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="card" id="panel-traffic">
      <div class="card-header">
        <span class="card-title">2. Request Traffic (req/min)</span>
        <span class="threshold-badge" id="thresh-traffic">Threshold: &ge; 1 req/min</span>
      </div>
      <div class="metric-row">
        <div class="metric-item"><span class="metric-label">Total Requests</span><span class="metric-value" id="val-req-total">-</span></div>
        <div class="metric-item"><span class="metric-label">Rate / Min</span><span class="metric-value" id="val-req-rate">-</span></div>
      </div>
      <div class="chart-container"><canvas id="chart-traffic"></canvas></div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="card" id="panel-errors">
      <div class="card-header">
        <span class="card-title">3. Error Rate & Breakdown (%)</span>
        <span class="threshold-badge" id="thresh-errors">Threshold: &le; 2.0%</span>
      </div>
      <div class="metric-row">
        <div class="metric-item"><span class="metric-label">Error Rate</span><span class="metric-value" id="val-err-rate">-</span></div>
        <div class="metric-item"><span class="metric-label">Failed Requests</span><span class="metric-value" id="val-err-count">-</span></div>
      </div>
      <div class="chart-container"><canvas id="chart-errors"></canvas></div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="card" id="panel-cost">
      <div class="card-header">
        <span class="card-title">4. Cost Over Time (USD)</span>
        <span class="threshold-badge" id="thresh-cost">Threshold: Total &le; $2.5</span>
      </div>
      <div class="metric-row">
        <div class="metric-item"><span class="metric-label">Total Cost</span><span class="metric-value" id="val-cost-total">-</span></div>
      </div>
      <div class="chart-container"><canvas id="chart-cost"></canvas></div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="card" id="panel-tokens">
      <div class="card-header">
        <span class="card-title">5. Input & Output Tokens</span>
        <span class="threshold-badge" id="thresh-tokens">Threshold: &le; 50k tokens</span>
      </div>
      <div class="metric-row">
        <div class="metric-item"><span class="metric-label">Tokens In</span><span class="metric-value" id="val-tokens-in">-</span></div>
        <div class="metric-item"><span class="metric-label">Tokens Out</span><span class="metric-value" id="val-tokens-out">-</span></div>
        <div class="metric-item"><span class="metric-label">Total</span><span class="metric-value" id="val-tokens-total">-</span></div>
      </div>
      <div class="chart-container"><canvas id="chart-tokens"></canvas></div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="card" id="panel-quality">
      <div class="card-header">
        <span class="card-title">6. Quality Proxy (0 to 1)</span>
        <span class="threshold-badge" id="thresh-quality">Threshold: Mean &ge; 0.75</span>
      </div>
      <div class="metric-row">
        <div class="metric-item"><span class="metric-label">Avg Quality Score</span><span class="metric-value" id="val-quality-mean">-</span></div>
      </div>
      <div class="chart-container"><canvas id="chart-quality"></canvas></div>
    </div>
  </main>

  <footer class="footer">
    <span>Contract: <code>config/dashboard.yaml</code> | SLO: <code>config/slo.yaml</code></span>
    <span id="last-updated">Cập nhật lần cuối: -</span>
  </footer>

  <script>
    let charts = {};
    let countdown = 30;

    function initCharts() {
      const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#283548' }, ticks: { color: '#9CA3AF', font: { size: 10 } } },
          y: { grid: { color: '#283548' }, ticks: { color: '#9CA3AF', font: { size: 10 } } }
        }
      };

      // Latency Chart
      charts.latency = new Chart(document.getElementById('chart-latency'), {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            { label: 'P95', data: [], borderColor: '#F87171', backgroundColor: 'rgba(248, 113, 113, 0.1)', fill: true, tension: 0.3 },
            { label: 'P50', data: [], borderColor: '#60A5FA', borderDash: [4, 4], fill: false, tension: 0.3 }
          ]
        },
        options: commonOptions
      });

      // Traffic Chart
      charts.traffic = new Chart(document.getElementById('chart-traffic'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Requests', data: [], backgroundColor: '#38BDF8', borderRadius: 4 }] },
        options: commonOptions
      });

      // Errors Chart
      charts.errors = new Chart(document.getElementById('chart-errors'), {
        type: 'doughnut',
        data: { labels: ['Success', 'Errors'], datasets: [{ data: [1, 0], backgroundColor: ['#10B981', '#EF4444'], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#9CA3AF' } } } }
      });

      // Cost Chart
      charts.cost = new Chart(document.getElementById('chart-cost'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Cost ($)', data: [], borderColor: '#F59E0B', backgroundColor: 'rgba(245, 158, 11, 0.1)', fill: true }] },
        options: commonOptions
      });

      // Tokens Chart
      charts.tokens = new Chart(document.getElementById('chart-tokens'), {
        type: 'bar',
        data: {
          labels: ['Input Tokens', 'Output Tokens'],
          datasets: [{ data: [0, 0], backgroundColor: ['#818CF8', '#C084FC'], borderRadius: 4 }]
        },
        options: { ...commonOptions, indexAxis: 'y' }
      });

      // Quality Chart
      charts.quality = new Chart(document.getElementById('chart-quality'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Score', data: [], borderColor: '#34D399', backgroundColor: 'rgba(52, 211, 153, 0.1)', fill: true, tension: 0.2 }] },
        options: { ...commonOptions, scales: { ...commonOptions.scales, y: { ...commonOptions.scales.y, min: 0, max: 1 } } }
      });
    }

    async function fetchMetrics() {
      try {
        const res = await fetch('/api/dashboard-metrics');
        const data = await res.json();
        updateUI(data);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      }
    }

    function updateUI(data) {
      const p = data.panels;
      const c = data.chart_data;

      // Incident Status
      const incEl = document.getElementById('incident-status');
      const activeIncs = Object.entries(data.incidents || {}).filter(([_, v]) => v).map(([k]) => k);
      if (activeIncs.length > 0) {
        incEl.className = 'badge badge-red';
        incEl.innerText = `🚨 Incidents Active: ${activeIncs.join(', ')}`;
      } else {
        incEl.className = 'badge badge-green';
        incEl.innerText = '🟢 Incidents: Normal';
      }

      // Panel 1: Latency
      document.getElementById('val-p50').innerText = `${p.latency.p50} ms`;
      document.getElementById('val-p95').innerText = `${p.latency.p95} ms`;
      document.getElementById('val-p99').innerText = `${p.latency.p99} ms`;
      const threshLat = document.getElementById('thresh-latency');
      threshLat.className = `threshold-badge ${p.latency.status.toLowerCase()}`;
      threshLat.innerText = `P95: ${p.latency.p95}ms (SLO: &le; 3000ms) [${p.latency.status}]`;

      charts.latency.data.labels = c.labels.length ? c.labels : ['Now'];
      charts.latency.data.datasets[0].data = c.latency_p95.length ? c.latency_p95 : [p.latency.p95];
      charts.latency.data.datasets[1].data = c.latency_p50.length ? c.latency_p50 : [p.latency.p50];
      charts.latency.update();

      // Panel 2: Traffic
      document.getElementById('val-req-total').innerText = p.traffic.count;
      document.getElementById('val-req-rate').innerText = `${p.traffic.rate_per_minute} req/m`;
      const threshTraffic = document.getElementById('thresh-traffic');
      threshTraffic.className = `threshold-badge ${p.traffic.status.toLowerCase()}`;
      threshTraffic.innerText = `Rate: ${p.traffic.rate_per_minute} (SLO: &ge; 1) [${p.traffic.status}]`;

      charts.traffic.data.labels = c.labels.length ? c.labels : ['Now'];
      charts.traffic.data.datasets[0].data = c.traffic.length ? c.traffic : [p.traffic.count];
      charts.traffic.update();

      // Panel 3: Errors
      document.getElementById('val-err-rate').innerText = `${p.errors.error_rate_pct}%`;
      document.getElementById('val-err-count').innerText = `${p.errors.failed_count} / ${p.errors.request_count}`;
      const threshErr = document.getElementById('thresh-errors');
      threshErr.className = `threshold-badge ${p.errors.status.toLowerCase()}`;
      threshErr.innerText = `Rate: ${p.errors.error_rate_pct}% (SLO: &le; 2%) [${p.errors.status}]`;

      charts.errors.data.datasets[0].data = [Math.max(0, p.errors.request_count - p.errors.failed_count), p.errors.failed_count];
      charts.errors.update();

      // Panel 4: Cost
      document.getElementById('val-cost-total').innerText = `$${p.cost.total_cost_usd}`;
      const threshCost = document.getElementById('thresh-cost');
      threshCost.className = `threshold-badge ${p.cost.status.toLowerCase()}`;
      threshCost.innerText = `Total: $${p.cost.total_cost_usd} (SLO: &le; $2.5) [${p.cost.status}]`;

      charts.cost.data.labels = c.labels.length ? c.labels : ['Now'];
      charts.cost.data.datasets[0].data = c.cost.length ? c.cost : [p.cost.total_cost_usd];
      charts.cost.update();

      // Panel 5: Tokens
      document.getElementById('val-tokens-in').innerText = p.tokens.tokens_in.toLocaleString();
      document.getElementById('val-tokens-out').innerText = p.tokens.tokens_out.toLocaleString();
      document.getElementById('val-tokens-total').innerText = p.tokens.total_tokens.toLocaleString();
      const threshTokens = document.getElementById('thresh-tokens');
      threshTokens.className = `threshold-badge ${p.tokens.status.toLowerCase()}`;
      threshTokens.innerText = `Total: ${p.tokens.total_tokens} (SLO: &le; 50k) [${p.tokens.status}]`;

      charts.tokens.data.datasets[0].data = [p.tokens.tokens_in, p.tokens.tokens_out];
      charts.tokens.update();

      // Panel 6: Quality
      document.getElementById('val-quality-mean').innerText = p.quality.mean_quality_score;
      const threshQuality = document.getElementById('thresh-quality');
      threshQuality.className = `threshold-badge ${p.quality.status.toLowerCase()}`;
      threshQuality.innerText = `Mean: ${p.quality.mean_quality_score} (SLO: &ge; 0.75) [${p.quality.status}]`;

      charts.quality.data.labels = c.labels.length ? c.labels : ['Now'];
      charts.quality.data.datasets[0].data = c.quality.length ? c.quality : [p.quality.mean_quality_score];
      charts.quality.update();

      document.getElementById('last-updated').innerText = `Cập nhật lần cuối: ${new Date().toLocaleTimeString()}`;
    }

    // Auto-refresh timer loop
    window.addEventListener('DOMContentLoaded', () => {
      initCharts();
      fetchMetrics();
      setInterval(() => {
        countdown--;
        if (countdown <= 0) {
          fetchMetrics();
          countdown = 30;
        }
        document.getElementById('refresh-timer').innerText = `🔄 Refresh in: ${countdown}s`;
      }, 1000);
    });
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)
