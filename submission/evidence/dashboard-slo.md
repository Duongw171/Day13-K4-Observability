# Evidence — Dashboard, SLO & Alerts

Vai trò: **Dashboard, SLO & Alert**

## 1. Kết quả Validator Dashboard

Lệnh thực thi:

```powershell
python scripts/validate_dashboard.py
```

Kết quả:

```text
HỢP LỆ: 6/6 panel có trong dashboard contract.
```

## 2. Dữ liệu 6 Panel & SLO Mapping (Contract: `config/dashboard.yaml`)

Dữ liệu nguồn chuẩn được đọc trực tiếp từ `data/logs.jsonl` trong khung thời gian 60 phút, chu kỳ tự động làm mới mỗi 30 giây:

| Panel | Event / Field | Phép tổng hợp | Đơn vị | Ngưỡng (Threshold / SLO) | Trạng thái Baseline |
|---|---|---|---|---|---|
| **1. Latency** | `response_sent.latency_ms` | P50, P95, P99 | `ms` | $P95 \le 3000\text{ ms}$ | ✅ PASS |
| **2. Traffic** | `request_received` | count, rate_per_minute | `req/min` | $\text{Rate} \ge 1\text{ req/m}$ | ✅ PASS |
| **3. Errors** | `request_received`, `request_failed`, `error_type` | error_rate_pct, count_by_value | `percent` | $\text{Rate} \le 2.0\%$ | ✅ PASS |
| **4. Cost** | `response_sent.cost_usd` | sum_by_minute, total | `USD` | $\text{Total} \le \$2.5$ | ✅ PASS |
| **5. Tokens** | `response_sent.tokens_in`, `tokens_out` | sum_by_field | `tokens` | $\text{Total} \le 50,000$ | ✅ PASS |
| **6. Quality** | `response_sent.quality_score` | mean | `score 0-1` | $\text{Mean} \ge 0.75$ | ✅ PASS |

## 3. Bằng chứng Dashboard Runtime phản ứng khi xảy ra sự cố

Khi kích hoạt sự cố `python scripts/inject_incident.py --scenario rag_slow` và chạy `load_test.py`:
- Panel **Latency P95** tăng vọt từ mức bình thường lên **4952 - 5289 ms** (vượt ngưỡng 3000ms).
- Hệ thống lập tức đánh dấu trạng thái **`❌ [BREACH]`**, chứng minh Dashboard phản ánh chính xác dữ liệu thời gian thực.

Trích xuất snapshot JSON tại [`submission/evidence/dashboard_metrics_snapshot.json`](dashboard_metrics_snapshot.json):

```json
{
  "time_range_minutes": 60,
  "refresh_seconds": 30,
  "panels": {
    "latency": {
      "p50": 3591.5,
      "p95": 4952.25,
      "p99": 6404.59,
      "status": "BREACH",
      "threshold": {"operator": "lte", "value": 3000, "unit": "ms"}
    }
  }
}
```

## 4. Alert Rules & Runbook

- Đã cấu hình 3 Alert Rules dựa trên triệu chứng (symptom-based) trong [`config/alert_rules.yaml`](../../config/alert_rules.yaml):
  1. `high_latency_p95`: Cảnh báo khi Latency P95 > 3000ms trong 5m.
  2. `high_error_rate`: Cảnh báo khi tỉ lệ lỗi > 2% trong 2m.
  3. `quality_score_drop`: Cảnh báo khi điểm chất lượng trung bình < 0.75 trong 10m.
- Đã hoàn thiện toàn bộ kịch bản ứng phó (Runbook) chi tiết trong [`docs/alerts.md`](../../docs/alerts.md).
