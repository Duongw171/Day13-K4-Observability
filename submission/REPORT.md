# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL: https://github.com/Duongw171/Day13-K4-Observability
- Commit SHA cuối: Nhóm cập nhật sau khi tích hợp các role
- Thành viên và vai trò:
  - Bùi Công Hậu — Logging & PII
  - Nguyễn Anh Đức — Tracing & Prompt Version
  - (tên) — Dashboard, SLO & Alert
  - (tên) — Incident, Report & Demo

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (35 log records, 16 correlation IDs)
- Tổng số traces: 170 traces (340 observations) trên project Langfuse dùng chung của nhóm; riêng phần chạy kiểm chứng prompt versioning gồm 4 lần load test x 10 request
- Số PII leak còn lại: **0**
- Link/đường dẫn dashboard: `http://127.0.0.1:8000/dashboard` (đọc trực tiếp `data/logs.jsonl`)

## 3. Logging và tracing

- Evidence correlation ID: [`evidence/logging-pii.md`](evidence/logging-pii.md) — request, response header và hai log event dùng cùng `logging-pii-evidence`.
- Evidence PII redaction: [`evidence/logging-pii.md`](evidence/logging-pii.md) — email, số điện thoại Việt Nam, CCCD và thẻ mẫu đều được thay bằng placeholder; validator không phát hiện leak.
- Evidence trace waterfall: [`evidence/cp2-trace-waterfall-v3-production.png`](evidence/cp2-trace-waterfall-v3-production.png) và [`evidence/cp2-trace-list.png`](evidence/cp2-trace-list.png)
- Giải thích một span đáng chú ý: Trace `76341b4dd8ddfbbd16a95b157e1abff7` cho thấy span `run` chỉ mất 0.15 giây, đúng bằng thời gian xử lý của mock LLM. Trước đó, ở giai đoạn baseline, cùng span này mất từ 1.4 đến 3.3 giây. Nguyên nhân là prompt `day13-chat` chưa tồn tại trên Langfuse nên mỗi request phải chờ hết `fetch_timeout_seconds` rồi mới rơi về template local, thể hiện qua metadata `prompt_source: local-fallback` và `prompt_fetch_error: LangfuseFallback`. Đây là ví dụ cho thấy metrics chỉ báo được triệu chứng latency cao, còn trace mới chỉ ra chính xác thời gian bị tiêu ở đâu và vì sao.

Phần Logging & PII sử dụng `structlog.contextvars` để gắn correlation ID và metadata xuyên suốt request. Middleware nhận request ID an toàn từ client hoặc sinh ID dạng `req-<8 ký tự hex>`, đồng thời trả ID và thời gian xử lý trong response header. Trước khi ghi JSONL, processor redaction duyệt đệ quy toàn bộ event sau bước render exception để PII không lọt qua payload lồng nhau hoặc stack trace.

## 4. Prompt versioning

- Prompt name: `day13-chat` (text prompt, quản lý trên Langfuse Cloud)
- Version/label baseline: version 3, label `baseline` và `production`
- Version/label candidate: version 4, label `candidate` và `latest`
- Trace ID của mỗi version:
  - v3 với label `production`: `76341b4dd8ddfbbd16a95b157e1abff7`
  - v4 với label `candidate`: `f65bb1459d2608f704c9858f934e6b00`
- Bằng chứng đổi label hoặc rollback:
  - [`evidence/cp2-prompt-versions.png`](evidence/cp2-prompt-versions.png) danh sách 4 version kèm label
  - [`evidence/cp2-rollback-before.png`](evidence/cp2-rollback-before.png) label `production` trỏ vào v4
  - [`evidence/cp2-rollback-after.png`](evidence/cp2-rollback-after.png) label `production` đã rollback về v3
  - [`evidence/cp2-rollback-production-v4.png`](evidence/cp2-rollback-production-v4.png) trace `4af3e30da9e95269c12466f8e0c12197` ghi nhận `prompt_label: production` kèm `prompt_version: 4`
  - [`evidence/cp2-trace-after-rollback-v3.png`](evidence/cp2-trace-after-rollback-v3.png) trace `84597c38624749d318c68885a8970ba8` ghi nhận `prompt_label: production` kèm `prompt_version: 3`

Hai trace cuối dùng cùng label `production` nhưng nhận hai version khác nhau, chứng minh việc đổi label trên Langfuse điều khiển được prompt mà ứng dụng sử dụng, không cần sửa code hay biến môi trường.

Ghi chú về version 1 và version 2: hai version đầu dùng biến `{{question}}` trong khi ứng dụng gọi `compile(feature=..., docs=..., message=...)`. Langfuse không tìm thấy biến tương ứng nên giữ nguyên chuỗi `{{question}}` trong prompt gửi tới LLM và bỏ qua câu hỏi thật của người dùng. Lỗi này không sinh exception, cũng không đổi giá trị `prompt_source`, nên chỉ phát hiện được khi đối chiếu nội dung prompt sau khi compile. Version 3 và 4 sửa lại thành `{{message}}`; kết quả kiểm chứng lưu tại [`evidence/cp2-prompt-v3-verify.txt`](evidence/cp2-prompt-v3-verify.txt) và [`evidence/cp2-prompt-v4-candidate-verify.txt`](evidence/cp2-prompt-v4-candidate-verify.txt).

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

| Thành viên     | Phần việc                                                                                                                                                                                                 | Commit/PR                                                                       | Điều đã học                                                                                                                                                                                                                                                     |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bùi Công Hậu   | Correlation middleware; log enrichment; recursive PII redaction; unit/integration tests; evidence Logging & PII                                                                                           | [`5a61e37`](https://github.com/Duongw171/Day13-K4-Observability/commit/5a61e37) | Cách cô lập context giữa các request, thứ tự processor trong structured logging, hashing định danh và kiểm chứng PII độc lập bằng validator                                                                                                                     |
| Nguyễn Anh Đức | Prompt versioning trên Langfuse: tạo prompt `day13-chat`, phát hiện và sửa lỗi sai tên biến ở v1/v2, dựng v3 baseline và v4 candidate, thực hiện đổi label và rollback, thu thập evidence trace và prompt | [`4b29d1e`](https://github.com/Duongw171/Day13-K4-Observability/commit/4b29d1e) | Cách Langfuse quản lý prompt bất biến theo version và điều hướng bằng label; lỗi sai tên biến trong prompt không sinh exception nên chỉ phát hiện được bằng cách đối chiếu prompt sau compile; ảnh hưởng của prompt fetch timeout lên latency của toàn hệ thống |
