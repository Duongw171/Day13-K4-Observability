# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: K4-Observability
- Repository URL: https://github.com/Duongw171/Day13-K4-Observability
- Commit SHA cuối: `9ce7ba7` (hoặc commit mới nhất sau khi push)
- Thành viên và vai trò:
  - Bùi Công Hậu — Logging & PII
  - Nguyễn Anh Đức — Tracing & Prompt Version
  - Nguyễn Văn Tấn — Dashboard, SLO & Alert
  - Nguyễn Văn Dương — Incident, Report & Demo

## 2. Kết quả kỹ thuật

| Validator / Chỉ số | Kết quả | Trạng thái |
|---|---|---|
| `python scripts/validate_logs.py` | **100/100** | PASSED ✅ |
| `python scripts/validate_dashboard.py` | **HỢP LỆ: 6/6 panel** | PASSED ✅ |
| `python -m pytest -q` | **28/28 passed** | PASSED ✅ |
| Số PII leak còn lại | **0** | PASSED ✅ |
| Unique correlation IDs | **51+** | PASSED ✅ |
| Traces trên Langfuse | **170+ traces** | PASSED ✅ |
| Giao diện Dashboard trực tiếp | `http://127.0.0.1:8000/dashboard` | Hoạt động ✅ |

---

## 3. Kiến trúc Observability đã triển khai

### Luồng xử lý tổng thể

```text
HTTP Request
    │
    ▼
CorrelationIdMiddleware (app/middleware.py)
  ├─ clear_contextvars()            ← ngăn context leak giữa các request
  ├─ _resolve_correlation_id()      ← nhận header x-request-id hoặc sinh ID req-<8-char-hex>
  ├─ bind_contextvars(correlation_id)
  └─ response headers: x-request-id, x-response-time-ms
    │
    ▼
/chat endpoint (app/main.py)
  └─ bind_contextvars(user_id_hash, session_id, feature, model, env)
    │
    ▼
LabAgent.run() (app/agent.py)
  ├─ resolve_prompt() → Langfuse Cloud (day13-chat, label=production/candidate)
  │    └─ fallback: local template nếu Langfuse gặp sự cố
  ├─ FakeLLM.generate()
  ├─ langfuse.update_current_trace(user_id, session_id, tags, metadata)
  ├─ langfuse.update_current_generation(model, usage_details, cost_details, prompt)
  └─ metrics.record_request(latency_ms, cost_usd, tokens_in, tokens_out, quality_score)
    │
    ▼
structlog pipeline (app/logging_config.py)
  ├─ merge_contextvars     ← inject correlation_id & context metadata
  ├─ add_log_level
  ├─ TimeStamper(iso, utc)
  ├─ scrub_event()         ← PII REDACTION đệ quy toàn bộ keys/values
  ├─ JsonlFileProcessor()  ← ghi data/logs.jsonl
  └─ JSONRenderer()        ← xuất log ra stdout
```

### PII Redaction (`app/pii.py` & `app/logging_config.py`)

- **Bao phủ PII**: Email, Số điện thoại Việt Nam (các đầu 03x, 05x, 07x, 08x, 09x & +84), CCCD (12 số), Thẻ tín dụng mẫu (16 số), Hộ chiếu Việt Nam.
- **Xử lý đệ quy**: Hàm `_scrub_value` duyệt đệ quy qua chuỗi, dictionary lồng nhau, danh sách, và cả chuỗi traceback exception đã render để không rò rỉ PII ở bất cứ độ sâu nào trong payload.

### Evidence
- Correlation ID & PII: [`evidence/logging-pii.md`](evidence/logging-pii.md)
- Log mẫu minh chứng: [`evidence/sample_logs_with_correlation_id.jsonl`](evidence/sample_logs_with_correlation_id.jsonl)
- Evidence PII: [`evidence/pii_redaction_evidence.jsonl`](evidence/pii_redaction_evidence.jsonl)
- Waterfall trace: [`evidence/cp2-trace-waterfall-v3-production.png`](evidence/cp2-trace-waterfall-v3-production.png)

---

## 4. Prompt versioning

- **Prompt name**: `day13-chat` (Text prompt trên Langfuse Cloud)
- **Version/label baseline**: Version 3 — labels `production`, `baseline`
- **Version/label candidate**: Version 4 — labels `candidate`, `latest`

### Trace IDs tiêu biểu theo Version

| Phase / Label | Version | Trace ID / Correlation ID | prompt_source |
|---|---|---|---|
| Production Baseline | v3 | `76341b4dd8ddfbbd16a95b157e1abff7` / `req-47694cbb` | `langfuse` |
| Candidate Test | v4 | `f65bb1459d2608f704c9858f934e6b00` | `langfuse` |
| Post-Rollback Production | v3 | `84597c38624749d318c68885a8970ba8` | `langfuse` |

### Bằng chứng Rollback & Quản lý Version
- Danh sách 4 versions: [`evidence/cp2-prompt-versions.png`](evidence/cp2-prompt-versions.png)
- Trước rollback (label `production` trỏ v4): [`evidence/cp2-rollback-before.png`](evidence/cp2-rollback-before.png)
- Sau rollback (label `production` trỏ v3): [`evidence/cp2-rollback-after.png`](evidence/cp2-rollback-after.png)
- Trace v4: [`evidence/cp2-rollback-production-v4.png`](evidence/cp2-rollback-production-v4.png)
- Trace sau rollback v3: [`evidence/cp2-trace-after-rollback-v3.png`](evidence/cp2-trace-after-rollback-v3.png)

### Cơ chế Fallback an toàn
Khi Langfuse gặp sự cố mạng hoặc timeout, ứng dụng tự động rơi về local prompt template (`prompt_source: local-fallback`, `fetch_error: LangfuseFallback`), đảm bảo dịch vụ AI không bao giờ ngắt kết nối đối với người dùng cuối.

---

## 5. Dashboard, SLO và Alerts

- **Kết quả `validate_dashboard.py`**: **`HỢP LỆ: 6/6 panel`** theo contract [`config/dashboard.yaml`](../config/dashboard.yaml).
- **Giao diện trực tiếp**: `http://127.0.0.1:8000/dashboard` (đọc realtime từ `data/logs.jsonl`, auto-refresh 30s).

### Bảng mapping 6 Panel Dashboard & SLOs

| Panel ID | Panel Title | Metrics / Aggregations | Threshold / SLO |
|---|---|---|---|
| `latency` | Latency percentiles | `latency_ms` P50, P95, P99 | **P95 ≤ 3000ms** (SLO 99.5%) |
| `traffic` | Request traffic | count, rate_per_minute | **rate ≥ 1 req/min** |
| `errors` | Error rate and breakdown | error_rate_pct, count_by_value | **error_rate ≤ 2.0%** (SLO 99.0%) |
| `cost` | Cost over time | cost_usd sum_by_minute, total | **total ≤ $2.50 USD/hr** |
| `tokens` | Input and output tokens | tokens_in, tokens_out sum | **total ≤ 50,000 tokens** |
| `quality` | Quality proxy | quality_score mean | **mean ≥ 0.75** (SLO 95.0%) |

### Alert Rules & Runbook
- 3 kịch bản cảnh báo chính trong [`config/alert_rules.yaml`](../config/alert_rules.yaml): `high_latency_p95`, `high_error_rate`, `quality_score_drop`.
- Quy trình ứng phó chi tiết tại [`docs/alerts.md`](../docs/alerts.md).
- Bằng chứng hình ảnh: Baseline ([`evidence/dashboard_baseline.png`](evidence/dashboard_baseline.png)), Incident `rag_slow` ([`evidence/dashboard_rag_slow.png`](evidence/dashboard_rag_slow.png)).

---

## 6. Luồng điều tra sự cố: Metrics → Traces → Logs

```text
[BƯỚC 1: METRICS]
  → Dashboard / metrics endpoint phát hiện chỉ số bất thường.
  → Ví dụ: P95 Latency tăng vọt > 3500ms (vượt ngưỡng SLO 3000ms) → Cảnh báo BREACH.

[BƯỚC 2: TRACES]
  → Mở Langfuse UI, lọc danh sách Trace trong khoảng thời gian xảy ra sự cố.
  → Chọn Trace có duration cao nhất, kiểm tra Waterfall Diagram.
  → Phát hiện Span `retrieve` (RAG) kéo dài ~2500ms (bình thường < 50ms), trong khi Span LLM generation vẫn bình thường.
  → Trích xuất `correlation_id` (ví dụ: `req-8b82ffef`).

[BƯỚC 3: LOGS]
  → Tra cứu `data/logs.jsonl` theo `correlation_id = "req-8b82ffef"`.
  → Tìm log event `response_sent` hoặc log sự cố: xác nhận `feature: monitoring` bị trễ do `rag_slow` incident.

[BƯỚC 4: FIX & PREVENT]
  → Khắc phục tạm thời: Tắt incident via `POST /incidents/rag_slow/disable`.
  → Phòng ngừa lâu dài: Cấu hình timeout gắt (1000ms) cho Retriever, chuyển hàm `retrieve` sang `async`, bổ sung cache.
```

---

## 7. Điều tra Challenge chính thức (`config/challenge.json`)

- **Challenge ID**: `day13-k4-observability-v1` (Cohort K4)
- **Incident chính thức**: `rag_slow`
- **Triệu chứng từ metrics**:
  - P95 latency toàn hệ thống vượt quá `latency_threshold_ms: 2000ms`, các request của challenge đạt từ **2651ms đến 4161ms**.
  - Tỷ lệ lỗi (Error rate) bằng 0%, nhưng phản hồi tính năng `monitoring` bị trễ nghiêm trọng.
- **Trace ID / Correlation ID liên quan**:
  - Request 1 (`k4-challenge-s02`): `req-8b82ffef` (Latency: 4161ms)
  - Request 2 (`k4-challenge-s05`): `req-6e2db2ce` (Latency: 2652ms)
  - Request 3 (`k4-challenge-s03`): `req-522cef4f` (Latency: 2651ms)
  - Request 4 (`k4-challenge-s01`): `req-030b9294` (Latency: 2651ms)
  - Request 5 (`k4-challenge-s04`): `req-1b090979` (Latency: 2651ms)
- **Log line minh chứng**:
  - Log kích hoạt incident:
    `{"service": "control", "event": "incident_enabled", "payload": {"name": "rag_slow"}, "correlation_id": "req-48d2f4f0", "level": "warning", "ts": "2026-08-11T10:33:02.196381Z"}`
  - Log request bị chậm (`req-8b82ffef`):
    `{"service": "api", "event": "response_sent", "correlation_id": "req-8b82ffef", "user_id_hash": "cb22af258a5e", "session_id": "k4-challenge-s02", "feature": "monitoring", "model": "claude-sonnet-4-5", "latency_ms": 4161, "tokens_in": 34, "tokens_out": 95, "cost_usd": 0.001527, "quality_score": 0.9, "level": "info", "ts": "2026-08-11T10:33:07.313166Z"}`
- **Root cause**:
  - Cờ incident `rag_slow` kích hoạt lệnh `time.sleep(2.5)` đồng bộ trong hàm `retrieve()` tại `app/mock_rag.py`. Việc nghẽn đồng bộ làm block luồng thực thi của agent, kéo dài latency của toàn bộ request dùng RAG.
- **Fix action**:
  - Khắc phục tức thì: Gọi `POST /incidents/rag_slow/disable` hoặc `python scripts/inject_incident.py --scenario rag_slow --disable`.
  - Tối ưu lâu dài: Chuyển `retrieve()` sang bất đồng bộ (`async def`), áp dụng cache kết quả truy vấn, đặt timeout cứng cho Vector DB (1000ms).
- **Preventive measure**:
  - Cấu hình Alert Rule `high_latency_p95` ngắt cảnh báo khi P95 > 2000ms duy trì trong 3 phút.
  - Áp dụng Circuit Breaker: nếu RAG fetch quá 1.5s thì nhả fallback document lập tức thay vì treo request.

---

## 8. Đóng góp cá nhân

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| **Bùi Công Hậu** | Correlation middleware; log enrichment; recursive PII redaction; unit/integration tests; evidence Logging & PII | [`5a61e37`](https://github.com/Duongw171/Day13-K4-Observability/commit/5a61e37) | Cách cô lập context giữa các request bằng `clear_contextvars`, thứ tự processor trong structured logging, hashing định danh và kiểm chứng PII đệ quy độc lập bằng validator. |
| **Nguyễn Anh Đức** | Prompt versioning trên Langfuse: tạo prompt `day13-chat`, phát hiện và sửa lỗi tên biến ở v1/v2, dựng v3 baseline và v4 candidate, thực hiện đổi label và rollback, thu thập evidence trace và prompt. | [`4b29d1e`](https://github.com/Duongw171/Day13-K4-Observability/commit/4b29d1e) | Cách Langfuse quản lý prompt bất biến theo version và điều hướng bằng label; lỗi biến prompt không gây exception nên cần kiểm tra sau compile; ảnh hưởng của prompt fetch timeout lên latency hệ thống. |
| **Nguyễn Văn Tấn** | Xây dựng Dashboard 6 panel tương tác trực tiếp (`app/dashboard_view.py`), cấu hình SLI/SLO (`config/slo.yaml`), định nghĩa 3 Alert rules (`config/alert_rules.yaml`), viết Runbook (`docs/alerts.md`), xuất snapshot (`scripts/export_dashboard.py`) và thu thập evidence. | [`3115e05`](https://github.com/Duongw171/Day13-K4-Observability/commit/3115e05) | Thiết kế cảnh báo dựa trên triệu chứng (symptom-based), tính toán percentiles (P50, P95, P99) trên log streaming, ánh xạ dữ liệu realtime từ logs sang biểu đồ và bảo vệ UX bằng SLOs. |
| **Nguyễn Văn Dương** | Chạy inject incident & load test challenge chính thức (`config/challenge.json`), điều tra sự cố theo luồng Metrics → Traces → Logs, xác định root cause nghẽn tại `mock_rag`, tổng hợp báo cáo và kịch bản demo. | [`6b9f99c`](https://github.com/Duongw171/Day13-K4-Observability/commit/6b9f99c) | Quy trình điều tra incident chuẩn: dùng metrics phát hiện khoảng thời gian bất thường, dùng trace waterfall khoanh vùng span chậm (RAG retrieve) và dùng logs với correlation ID làm bằng chứng root cause. |
