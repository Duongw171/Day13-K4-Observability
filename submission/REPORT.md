# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: K4-Observability
- Repository URL: *(điền URL sau khi push)*
- Commit SHA cuối: *(điền sau khi commit cuối)*
- Thành viên và vai trò: *(điền thành viên)*

## 2. Kết quả kỹ thuật

| Validator | Kết quả |
|-----------|---------|
| `validate_logs.py` | **100/100** ✅ |
| `validate_dashboard.py` | **HỢP LỆ: 6/6 panel** ✅ |
| `pytest -q` | **22/22 PASSED** ✅ |
| Tổng số traces Langfuse | **≥ 20** (15 production + 5 candidate) |
| PII leaks trong log | **0** ✅ |
| Unique correlation IDs | **20** |

## 3. Kiến trúc Observability đã triển khai

```
HTTP Request
    │
    ▼
CorrelationIdMiddleware  (app/middleware.py)
  ├─ clear_contextvars()            ← ngăn context leak giữa requests
  ├─ generate req-XXXXXXXX          ← uuid4().hex[:8]
  ├─ bind_contextvars(correlation_id)
  └─ set response headers: x-request-id, x-response-time-ms
    │
    ▼
/chat endpoint  (app/main.py)
  └─ bind_contextvars(
       user_id_hash, session_id,
       feature, model, env
     )
    │
    ▼
LabAgent.run()  (app/agent.py)
  ├─ resolve_prompt() → Langfuse Cloud (label=production/candidate)
  │    └─ fallback: local template nếu Langfuse không khả dụng
  ├─ FakeLLM.generate()
  ├─ langfuse.update_current_trace(
  │    user_id, session_id, tags,
  │    metadata={prompt_name, prompt_label, prompt_version, prompt_source}
  │  )
  ├─ langfuse.update_current_generation(
  │    model, usage_details, cost_details, prompt_link
  │  )
  └─ metrics.record_request(latency, cost, tokens, quality)
    │
    ▼
structlog pipeline  (app/logging_config.py)
  ├─ merge_contextvars     ← inject correlation_id + enrichment fields
  ├─ add_log_level
  ├─ TimeStamper(iso, utc)
  ├─ scrub_event()         ← PII REDACTION trước khi ghi file
  ├─ JsonlFileProcessor()  ← ghi data/logs.jsonl
  └─ JSONRenderer()        ← stdout
```

### PII Redaction — `app/pii.py`

| Pattern | Ví dụ bị bắt | Thay thế |
|---------|-------------|---------|
| `email` | `student@vinuni.edu.vn` | `[REDACTED_EMAIL]` |
| `phone_vn` | `0987654321`, `090 123 4567`, `+84 90 123 4567` | `[REDACTED_PHONE_VN]` |
| `cccd` | `012345678901` | `[REDACTED_CCCD]` |
| `credit_card` | `4111 1111 1111 1111` | `[REDACTED_CREDIT_CARD]` |
| `passport_vn` | `B1234567` | `[REDACTED_PASSPORT_VN]` |

`scrub_event` processor chạy **trước** `JsonlFileProcessor` trong pipeline — đảm bảo PII không bao giờ ghi ra file log.

## 4. Logging và tracing

- Evidence correlation ID: `submission/evidence/sample_logs_with_correlation_id.jsonl`
- Evidence PII redaction: `submission/evidence/pii_redaction_evidence.jsonl`
- Evidence trace waterfall: `submission/evidence/trace_waterfall.png` *(chụp từ Langfuse)*
- Giải thích một span đáng chú ý:
  - Span `LabAgent.run` là **generation span** chính
  - Chứa `model=claude-sonnet-4-5`, `prompt_tokens`, `completion_tokens`, `cost_details`
  - Linked tới managed prompt trên Langfuse qua `prompt` field
  - `metadata.prompt_version` xác định chính xác version prompt đã dùng

### Ví dụ log record hoàn chỉnh

```json
{
  "service": "api",
  "event": "response_sent",
  "correlation_id": "req-47694cbb",
  "user_id_hash": "2055254ee30a",
  "session_id": "s01",
  "feature": "qa",
  "model": "claude-sonnet-4-5",
  "env": "dev",
  "latency_ms": 160,
  "tokens_in": 36,
  "tokens_out": 137,
  "cost_usd": 0.002163,
  "quality_score": 0.9,
  "level": "info",
  "ts": "2026-08-11T08:12:00.101623Z"
}
```

## 5. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: **v1** — labels: `production`, `baseline`
- Version/label candidate: **v2** — labels: `candidate`

### Prompt v1 (production/baseline)
```
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

### Prompt v2 (candidate)
```
You are a concise assistant. Keep answers under 3 sentences.
Feature={{feature}}
Context: {{docs}}
User Question={{message}}
```

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
| *(điền tên)* | Middleware: correlation ID, context propagation | b3d0935 | structlog contextvars, request lifecycle |
| *(điền tên)* | Logging: JSON schema, PII scrubbing pipeline | b3d0935 | structlog processors, regex PII patterns |
| *(điền tên)* | Langfuse tracing, prompt versioning v1/v2 | 45c0cf3 | Langfuse SDK v3, managed prompts, fallback |
| *(điền tên)* | Dashboard contract, SLO definitions, alert rules | b3d0935 | Percentile metrics, SLO threshold design |
