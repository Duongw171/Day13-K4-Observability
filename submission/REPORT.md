# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL: https://github.com/Duongw171/Day13-K4-Observability
- Commit SHA cuối: Nhóm cập nhật sau khi tích hợp các role
- Thành viên và vai trò:
  - Bùi Công Hậu — Logging & PII
  - Nguyễn Anh Đức — Tracing & Prompt Version
  - Nguyễn Văn Tấn — Dashboard, SLO & Alert
  - Nguyễn Văn Dương — Incident, Report & Demo

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (35 log records, 16 correlation IDs)
- Tổng số traces: 170 traces (340 observations) trên project Langfuse dùng chung của nhóm; riêng phần chạy kiểm chứng prompt versioning gồm 4 lần load test x 10 request
- Số PII leak còn lại: **0**
- Link/đường dẫn dashboard: `http://127.0.0.1:8000/dashboard` (đọc trực tiếp `data/logs.jsonl`)

## 3. Kiến trúc Observability đã triển khai

- Evidence correlation ID: [`evidence/logging-pii.md`](evidence/logging-pii.md) — request, response header và hai log event dùng cùng `logging-pii-evidence`.
- Evidence PII redaction: [`evidence/logging-pii.md`](evidence/logging-pii.md) — email, số điện thoại Việt Nam, CCCD và thẻ mẫu đều được thay bằng placeholder; validator không phát hiện leak.
- Evidence trace waterfall: [`evidence/cp2-trace-waterfall-v3-production.png`](evidence/cp2-trace-waterfall-v3-production.png) và [`evidence/cp2-trace-list.png`](evidence/cp2-trace-list.png)
- Giải thích một span đáng chú ý: Trace `76341b4dd8ddfbbd16a95b157e1abff7` cho thấy span `run` chỉ mất 0.15 giây, đúng bằng thời gian xử lý của mock LLM. Trước đó, ở giai đoạn baseline, cùng span này mất từ 1.4 đến 3.3 giây. Nguyên nhân là prompt `day13-chat` chưa tồn tại trên Langfuse nên mỗi request phải chờ hết `fetch_timeout_seconds` rồi mới rơi về template local, thể hiện qua metadata `prompt_source: local-fallback` và `prompt_fetch_error: LangfuseFallback`. Đây là ví dụ cho thấy metrics chỉ báo được triệu chứng latency cao, còn trace mới chỉ ra chính xác thời gian bị tiêu ở đâu và vì sao.

Phần Logging & PII sử dụng `structlog.contextvars` để gắn correlation ID và metadata xuyên suốt request. Middleware nhận request ID an toàn từ client hoặc sinh ID dạng `req-<8 ký tự hex>`, đồng thời trả ID và thời gian xử lý trong response header. Trước khi ghi JSONL, processor redaction duyệt đệ quy toàn bộ event sau bước render exception để PII không lọt qua payload lồng nhau hoặc stack trace.

### Ví dụ log record hoàn chỉnh

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

## 5. Prompt versioning

- Kết quả `validate_dashboard.py`: **`HỢP LỆ: 6/6 panel`** (đáp ứng trọn vẹn contract `config/dashboard.yaml`).
- Evidence dashboard:
  - [`evidence/dashboard_baseline.png`](evidence/dashboard_baseline.png): Ảnh chụp toàn bộ 6 panel ở trạng thái bình thường (Baseline).
  - [`evidence/dashboard_rag_slow.png`](evidence/dashboard_rag_slow.png): Ảnh chụp Dashboard khi kích hoạt sự cố `rag_slow`, panel Latency P95 tăng vọt $>3500\text{ ms}$ và chuyển trạng thái `[BREACH]`.
  - [`evidence/dashboard-slo.md`](evidence/dashboard-slo.md): Báo cáo tổng hợp chi tiết phân tích và bảng mapping chỉ số.
  - [`evidence/dashboard_metrics_snapshot.json`](evidence/dashboard_metrics_snapshot.json): Snapshot dữ liệu JSON xuất từ API metrics.
  - Giao diện Dashboard trực tiếp: `http://127.0.0.1:8000/dashboard` (đọc trực tiếp từ `data/logs.jsonl`, tự động làm mới mỗi 30s, time range 60m).
- SLO đã chọn và lý do:
  - `latency_p95_ms <= 3000ms` (Target 99.5%): Đảm bảo phản hồi nhanh cho trợ lý AI, tránh timeout giao diện.
  - `error_rate_pct <= 2.0%` (Target 99.0%): Duy trì độ tin cậy dịch vụ, hạn chế gián đoạn.
  - `daily_cost_usd <= 2.5 USD` (Target 100.0%): Kiểm soát ngân sách tiêu thụ token của LLM.
  - `quality_score_avg >= 0.75` (Target 95.0%): Đảm bảo chất lượng câu trả lời và hiệu quả retrieve từ RAG.
- Alert rules và runbook:
  - 3 alert rules symptom-based cấu hình tại [`config/alert_rules.yaml`](../config/alert_rules.yaml) (`high_latency_p95`, `high_error_rate`, `quality_score_drop`).
  - Toàn bộ kịch bản ứng phó (Runbook) chi tiết đã hoàn thiện trong [`docs/alerts.md`](../docs/alerts.md) với 3 bước kiểm tra và biện pháp khắc phục tạm thời.

### Prompt v1 (production/baseline)
```
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

- Challenge ID: `day13-k4-observability-v1` (Cohort K4)
- Triệu chứng từ metrics:
  - Latency tăng đột biến vượt ngưỡng cho phép: P95 latency toàn hệ thống vượt quá `latency_threshold_ms: 2000ms`, các request của challenge đạt mức từ **2651ms đến 4161ms** (tổng thời gian xử lý khi chạy đồng thời 5 request lên tới ~12.1s - 14.8s).
  - Tỉ lệ lỗi (Error rate) không tăng (0%), nhưng thời gian phản hồi ở tính năng `feature: monitoring` bị trễ nghiêm trọng, gây nguy cơ breach SLO latency P95 (ngưỡng 3000ms).
- Trace ID liên quan:
  - Request 1 (`k4-challenge-s02`): Trace correlation ID `req-8b82ffef` (Latency: 4161ms).
  - Request 2 (`k4-challenge-s05`): Trace correlation ID `req-6e2db2ce` (Latency: 2652ms).
  - Request 3 (`k4-challenge-s03`): Trace correlation ID `req-522cef4f` (Latency: 2651ms).
  - Request 4 (`k4-challenge-s01`): Trace correlation ID `req-030b9294` (Latency: 2651ms).
  - Request 5 (`k4-challenge-s04`): Trace correlation ID `req-1b090979` (Latency: 2651ms).
- Log line/correlation ID liên quan:
  - Log kích hoạt incident:
    `{"service": "control", "event": "incident_enabled", "payload": {"name": "rag_slow"}, "correlation_id": "req-48d2f4f0", "level": "warning", "ts": "2026-08-11T10:33:02.196381Z"}`
  - Log request bị chậm tiêu biểu (`req-8b82ffef`):
    `{"service": "api", "event": "response_sent", "correlation_id": "req-8b82ffef", "user_id_hash": "cb22af258a5e", "session_id": "k4-challenge-s02", "feature": "monitoring", "model": "claude-sonnet-4-5", "latency_ms": 4161, "tokens_in": 34, "tokens_out": 95, "cost_usd": 0.001527, "quality_score": 0.9, "level": "info", "ts": "2026-08-11T10:33:07.313166Z"}`
- Root cause:
  - Khi cờ incident `rag_slow` được bật trong hệ thống, hàm `retrieve()` tại [`app/mock_rag.py`](../app/mock_rag.py) thực thi lệnh `time.sleep(2.5)` mô phỏng sự cố nghẽn mạng / vector store database phản hồi chậm. Việc hàm retrieval bị trễ 2.5s dạng synchronous đã chặn (block) toàn bộ luồng xử lý của `LabAgent.run`, khiến thời gian xử lý của mỗi request bị kéo dài thêm ít nhất 2500ms, dẫn tới tail latency tăng vọt trên toàn bộ các request có sử dụng RAG.
- Fix action:
  - Tắt sự cố: Gửi lệnh `POST /incidents/rag_slow/disable` hoặc chạy `python scripts/inject_incident.py --scenario rag_slow --disable` để đưa hệ thống về trạng thái bình thường.
  - Tối ưu hóa kỹ thuật dài hạn: Chuyển hàm `retrieve` sang cơ chế bất đồng bộ (`async def retrieve`) để không block event loop; cấu hình timeout nghiêm ngặt cho Vector DB (ví dụ 1000ms); thêm bộ nhớ đệm (caching) cho các query tài liệu lặp lại.
- Preventive measure:
  - Thiết lập Alert Rule cảnh báo sớm `high_latency_p95` (P95 > 2000ms duy trì trong 3 phút) gửi thông báo tới đội ngũ on-call.
  - Áp dụng mẫu thiết kế Circuit Breaker: nếu module RAG/Vector DB vượt quá timeout 1.5s thì tự động ngắt và trả về fallback domain documents thay vì làm treo request của người dùng.
  - Tách timeout và theo dõi riêng biệt cho từng span (Retriever timeout $\le 1000\text{ ms}$, LLM generation timeout $\le 2000\text{ ms}$).

### Trace IDs

| Run | Label | Correlation ID (ví dụ) | prompt_source |
|-----|-------|----------------------|---------------|
| Production (v1) | `production` | `req-47694cbb` | `langfuse` |
| Production (v1) | `production` | `req-44d46c8a` | `langfuse` |
| Candidate (v2) | `candidate` | *(từ run_with_label.py)* | `langfuse` |

- Bằng chứng rollback: `submission/evidence/prompt_rollback_v1.png` *(chụp từ Langfuse)*

### Cơ chế fallback

```
Langfuse không khả dụng
    → prompt_source = "local-fallback"
    → fetch_error = "TimeoutError" | "LangfuseFallback"
    → App vẫn chạy bình thường với local template
```

## 6. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **HỢP LỆ: 6/6 panel** ✅
- Evidence dashboard: `submission/evidence/dashboard_6panels.png` *(chụp từ tool dashboard)*

### 6 Panel Contract

| Panel | Title | Metrics | SLO/Threshold |
|-------|-------|---------|----------------|
| `latency` | Latency percentiles | `latency_ms` P50/P95/P99 | **P95 ≤ 3000ms** |
| `traffic` | Request traffic | count, rate_per_minute | rate ≥ 1 req/min |
| `errors` | Error rate & breakdown | error_rate_pct, count_by_value | **error_rate ≤ 2%** |
| `cost` | Cost over time | `cost_usd` sum/min | **total ≤ $2.50/hr** |
| `tokens` | Input & output tokens | `tokens_in`, `tokens_out` sum | total ≤ 50,000 |
| `quality` | Quality proxy | `quality_score` mean | **mean ≥ 0.75** |

### Alert Rules (`config/alert_rules.yaml`)

| Alert | Condition | Severity | Action |
|-------|-----------|---------|--------|
| High Latency | P95 > 3000ms | Warning | Kiểm tra `rag_slow` incident |
| Error Rate | error_rate > 2% | Critical | Trace → Log theo correlation_id |
| Cost Spike | total_cost > $2.50/hr | Warning | Kiểm tra `cost_spike` incident |
| Low Quality | quality_avg < 0.75 | Warning | Kiểm tra prompt version |

### Runbook — Luồng điều tra sự cố

```
1. METRICS  → Phát hiện: latency_p95 tăng / error_rate tăng / cost_spike
2. TRACES   → Langfuse: filter theo time, tìm trace chậm, xem waterfall
              → Span nào bất thường? retrieve() hay generate()?
              → Check metadata: prompt_version, correlation_id, feature
3. LOGS     → data/logs.jsonl: filter by correlation_id từ trace
              → Xác nhận root cause từ log line cụ thể
4. FIX      → Disable incident: POST /incidents/{name}/disable
              → Hoặc rollback prompt version về baseline
```

## 7. Luồng điều tra sự cố: Metrics → Traces → Logs

### Ví dụ: Incident `rag_slow`

```
STEP 1 — METRICS (/metrics):
  latency_p95 = 4500ms  [> SLO 3000ms → ALERT]
  traffic     = 15 req
  error_rate  = 0%

STEP 2 — TRACES (Langfuse):
  → Mở trace có duration cao nhất
  → Waterfall: span retrieve() chiếm ~3000ms (bình thường ~50ms)
  → correlation_id: req-XXXXXXXX
  → metadata: feature=qa, prompt_version=1, prompt_source=langfuse

STEP 3 — LOGS (data/logs.jsonl):
  → Filter: correlation_id = "req-XXXXXXXX"
  → Tìm log: event=response_sent, latency_ms=4500
  → Xác nhận: latency cao do rag_slow incident

STEP 4 — FIX:
  → POST /incidents/rag_slow/disable
  → Verify: latency_p95 trở về < 3000ms
```

## 8. Điều tra challenge

- Challenge ID: *(điền sau khi Lab Coach release `config/challenge.json`)*
- Triệu chứng từ metrics: *(điền)*
- Trace ID liên quan: *(điền)*
- Log line/correlation ID liên quan: *(điền)*
- Root cause: *(điền)*
- Fix action: *(điền)*
- Preventive measure: *(điền)*

## 9. Đóng góp cá nhân

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Bùi Công Hậu | Correlation middleware; log enrichment; recursive PII redaction; unit/integration tests; evidence Logging & PII | [`5a61e37`](https://github.com/Duongw171/Day13-K4-Observability/commit/5a61e37) | Cách cô lập context giữa các request, thứ tự processor trong structured logging, hashing định danh và kiểm chứng PII độc lập bằng validator |
| Nguyễn Anh Đức | Prompt versioning trên Langfuse: tạo prompt `day13-chat`, phát hiện và sửa lỗi sai tên biến ở v1/v2, dựng v3 baseline và v4 candidate, thực hiện đổi label và rollback, thu thập evidence trace và prompt | [`4b29d1e`](https://github.com/Duongw171/Day13-K4-Observability/commit/4b29d1e) | Cách Langfuse quản lý prompt bất biến theo version và điều hướng bằng label; lỗi sai tên biến trong prompt không sinh exception nên chỉ phát hiện được bằng cách đối chiếu prompt sau compile; ảnh hưởng của prompt fetch timeout lên latency của toàn hệ thống |
| Nguyễn Văn Tấn | Xây dựng Dashboard 6 panel tương tác trực tiếp (`app/dashboard_view.py`), cấu hình SLI/SLO (`config/slo.yaml`), định nghĩa 3 Alert rules symptom-based (`config/alert_rules.yaml`), viết Runbook chi tiết (`docs/alerts.md`), script xuất snapshot (`scripts/export_dashboard.py`) và thu thập evidence baseline / incident | [`3115e05`](https://github.com/Duongw171/Day13-K4-Observability/commit/3115e05) | Cách thiết kế cảnh báo dựa trên triệu chứng (symptom-based) thay vì nguyên nhân nội bộ, tính toán percentiles (P50, P95, P99) trên log streaming, cách ánh xạ dữ liệu thời gian thực từ logs sang biểu đồ và bảo vệ trải nghiệm người dùng bằng SLO |
| Nguyễn Văn Dương | Phụ trách chạy inject incident & load test challenge chính thức (`config/challenge.json`), điều tra sự cố theo luồng Metrics → Traces → Logs, xác định root cause nghẽn tại module `mock_rag`, tổng hợp báo cáo và chuẩn bị kịch bản demo | [`6b9f99c`](https://github.com/Duongw171/Day13-K4-Observability/commit/6b9f99c) | Quy trình điều tra incident chuẩn: dùng metrics phát hiện khoảng thời gian bất thường, dùng trace waterfall khoanh vùng span chậm (RAG retrieve) và dùng logs với correlation ID làm bằng chứng root cause không thể chối cãi |
