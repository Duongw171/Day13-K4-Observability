# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL: https://github.com/Duongw171/Day13-K4-Observability
- Commit SHA cuối: Nhóm cập nhật sau khi tích hợp các role
- Thành viên và vai trò: **Bùi Công Hậu — Logging & PII**

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (35 log records, 16 correlation IDs)
- Tổng số traces: Nhóm phụ trách Tracing cập nhật
- Số PII leak còn lại: **0**
- Link/đường dẫn dashboard: `http://127.0.0.1:8000/dashboard` (đọc trực tiếp `data/logs.jsonl`)

## 3. Logging và tracing

- Evidence correlation ID: [`evidence/logging-pii.md`](evidence/logging-pii.md) — request, response header và hai log event dùng cùng `logging-pii-evidence`.
- Evidence PII redaction: [`evidence/logging-pii.md`](evidence/logging-pii.md) — email, số điện thoại Việt Nam, CCCD và thẻ mẫu đều được thay bằng placeholder; validator không phát hiện leak.
- Evidence trace waterfall: Nhóm phụ trách Tracing cập nhật
- Giải thích một span đáng chú ý: Nhóm phụ trách Tracing cập nhật

Phần Logging & PII sử dụng `structlog.contextvars` để gắn correlation ID và metadata xuyên suốt request. Middleware nhận request ID an toàn từ client hoặc sinh ID dạng `req-<8 ký tự hex>`, đồng thời trả ID và thời gian xử lý trong response header. Trước khi ghi JSONL, processor redaction duyệt đệ quy toàn bộ event sau bước render exception để PII không lọt qua payload lồng nhau hoặc stack trace.

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **`HỢP LỆ: 6/6 panel`** (đáp ứng trọn vẹn contract `config/dashboard.yaml`).
- Evidence dashboard: [`evidence/dashboard-slo.md`](evidence/dashboard-slo.md) và snapshot [`evidence/dashboard_metrics_snapshot.json`](evidence/dashboard_metrics_snapshot.json) — giao diện 6 panel tại `http://127.0.0.1:8000/dashboard` hiển thị đầy đủ Latency (P50/P95/P99), Traffic, Error breakdown, Cost, Token usage, Quality score kèm đường ngưỡng SLO.
- SLO đã chọn và lý do:
  - `latency_p95_ms <= 3000ms` (Target 99.5%): Đảm bảo phản hồi nhanh cho trợ lý AI, tránh timeout giao diện.
  - `error_rate_pct <= 2.0%` (Target 99.0%): Duy trì độ tin cậy dịch vụ, hạn chế gián đoạn.
  - `daily_cost_usd <= 2.5 USD` (Target 100.0%): Kiểm soát ngân sách tiêu thụ token của LLM.
  - `quality_score_avg >= 0.75` (Target 95.0%): Đảm bảo chất lượng câu trả lời và hiệu quả retrieve từ RAG.
- Alert rules và runbook:
  - 3 alert rules symptom-based cấu hình tại [`config/alert_rules.yaml`](../config/alert_rules.yaml) (`high_latency_p95`, `high_error_rate`, `quality_score_drop`).
  - Toàn bộ kịch bản ứng phó (Runbook) chi tiết đã hoàn thiện trong [`docs/alerts.md`](../docs/alerts.md) với 3 bước kiểm tra và biện pháp khắc phục tạm thời.

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Bùi Công Hậu | Correlation middleware; log enrichment; recursive PII redaction; unit/integration tests; evidence Logging & PII | [`5a61e37`](https://github.com/Duongw171/Day13-K4-Observability/commit/5a61e37) | Cách cô lập context giữa các request, thứ tự processor trong structured logging, hashing định danh và kiểm chứng PII độc lập bằng validator |
| Dashboard, SLO & Alert | Cấu hình mục tiêu SLO (`config/slo.yaml`), Alert rules (`config/alert_rules.yaml`), Runbook (`docs/alerts.md`), Dashboard 6 panel (`app/dashboard_view.py`), evidence Dashboard | [`ce2e1da`](https://github.com/Duongw171/Day13-K4-Observability/commit/ce2e1da) | Cách thiết kế cảnh báo symptom-based, tính toán percentiles P50/P95/P99 trên log streaming và xây dựng SLO bảo vệ trải nghiệm người dùng |
