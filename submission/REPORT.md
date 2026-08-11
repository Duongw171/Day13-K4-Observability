# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: K4-Observability
- Repository URL: *(điền URL sau khi push)*
- Commit SHA cuối: *(điền sau khi commit)*
- Thành viên và vai trò: *(điền thành viên)*

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 100/100
- Tổng số traces: ≥ 15 (từ load test với 15 queries)
- Số PII leak còn lại: 0
- Link/đường dẫn dashboard: `data/logs.jsonl` + `config/dashboard.yaml` (xem evidence/)

## 3. Kiến trúc Observability đã triển khai

```
HTTP Request
    │
    ▼
CorrelationIdMiddleware
  • clear_contextvars()          ← ngăn context leak giữa requests
  • generate req-XXXXXXXX ID     ← từ uuid4().hex[:8]
  • bind_contextvars(correlation_id)
  • set x-request-id header
    │
    ▼
/chat endpoint (main.py)
  • bind_contextvars(user_id_hash, session_id, feature, model, env)
  • log "request_received"
    │
    ▼
LabAgent.run() (agent.py)
  • resolve_prompt() → Langfuse Cloud / local-fallback
  • FakeLLM.generate()
  • langfuse.update_current_trace(metadata={prompt_name, label, version})
  • langfuse.update_current_generation(model, usage, cost, prompt_link)
  • metrics.record_request()
    │
    ▼
structlog pipeline (logging_config.py)
  • merge_contextvars         ← inject correlation_id + enrichment fields
  • add_log_level
  • TimeStamper(iso, utc)
  • scrub_event()             ← PII REDACTION (email, phone_vn, cccd, credit_card)
  • JsonlFileProcessor()      ← ghi data/logs.jsonl
  • JSONRenderer()            ← stdout
```

### PII Redaction Implementation

Hàm `scrub_text()` trong `app/pii.py` áp dụng regex patterns:

| Pattern | Mô tả |
|---------|-------|
| `email` | Email addresses |
| `phone_vn` | SĐT VN: 03x/05x/07x/08x/09x và +84, hỗ trợ separator space/dot/dash |
| `cccd` | Căn cước công dân (12 chữ số) |
| `credit_card` | Thẻ tín dụng (16 chữ số với separator) |
| `passport_vn` | Hộ chiếu VN (1 chữ + 7 số) |

`scrub_event` processor được đăng ký trong structlog pipeline, chạy **trước** `JsonlFileProcessor` để đảm bảo PII không bao giờ được ghi ra file log.

## 4. Logging và tracing

- Evidence correlation ID: xem `submission/evidence/correlation_id_log.txt`
- Evidence PII redaction: xem `submission/evidence/pii_redaction_evidence.txt`
- Evidence trace waterfall: xem `submission/evidence/trace_waterfall.png`
- Giải thích một span đáng chú ý: Span `LabAgent.run` là generation span chính, chứa `prompt_version`, `model`, `usage_details` (prompt_tokens, completion_tokens), `cost_details` và link tới managed prompt trên Langfuse.

## 5. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: v1 — label `baseline` và `production`
- Version/label candidate: v2 — label `candidate` (thêm hướng dẫn format câu trả lời ngắn gọn hơn)
- Trace ID của mỗi version:
  - v1 (production): *(điền sau khi chạy)*
  - v2 (candidate): *(điền sau khi chạy với LANGFUSE_PROMPT_LABEL=candidate)*
- Bằng chứng đổi label hoặc rollback: xem `submission/evidence/prompt_rollback.png`

### Cơ chế fallback

Khi Langfuse không khả dụng hoặc trả về `is_fallback=True`:
- `prompt_source` ghi `local-fallback`
- `fetch_error` ghi tên exception (`TimeoutError`, `LangfuseFallback`, v.v.)
- App vẫn chạy bình thường với local template

## 6. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: HỢP LỆ: 6/6 panel
- Evidence dashboard: xem `submission/evidence/dashboard_6panels.png`

### 6 Panel Contract (`config/dashboard.yaml`)

| Panel ID | Title | Metric | SLO/Threshold |
|----------|-------|--------|----------------|
| `latency` | Latency percentiles | `latency_ms` P50/P95/P99 | P95 ≤ 3000ms |
| `traffic` | Request traffic | count / rate_per_minute | rate ≥ 1 req/min |
| `errors` | Error rate & breakdown | error_rate_pct, count_by_value | error_rate ≤ 2% |
| `cost` | Cost over time | `cost_usd` sum | total ≤ $2.50/hr |
| `tokens` | Input & output tokens | `tokens_in`, `tokens_out` sum | total ≤ 50,000 tokens |
| `quality` | Quality proxy | `quality_score` mean | mean ≥ 0.75 |

### Alert Rules (`config/alert_rules.yaml`)
- Xem `config/alert_rules.yaml` cho chi tiết ngưỡng cảnh báo

### Runbook
1. **P95 > 3000ms**: Kiểm tra `rag_slow` incident, trace span `retrieve()`, xem logs với correlation_id
2. **Error rate > 2%**: Tìm `request_failed` events, group by `error_type`, trace để xem stack
3. **Cost > $2.50/hr**: Kiểm tra `cost_spike` incident, token_out bất thường trong `response_sent` logs
4. **Quality < 0.75**: Xem quality_score theo feature, kiểm tra prompt version đang dùng

## 7. Luồng điều tra sự cố: Metrics → Traces → Logs

```
1. METRICS (/metrics endpoint)
   • Phát hiện: latency_p95 tăng đột biến hoặc error_rate tăng
   • Ví dụ: latency_p95 = 4500ms (> SLO 3000ms)
   
2. TRACES (Langfuse)  
   • Filter traces theo time range
   • Tìm trace có duration cao, xem waterfall
   • Span nào chậm nhất? → retrieve() hay llm.generate()?
   • Kiểm tra metadata: prompt_version, feature, correlation_id
   
3. LOGS (data/logs.jsonl)
   • Filter by correlation_id từ trace
   • Xác nhận root cause từ log line
   • Ví dụ: rag_slow → latency_ms trong response_sent rất cao
   
4. ROOT CAUSE & FIX
   • Disable incident: POST /incidents/rag_slow/disable
   • Hoặc rollback prompt version nếu do prompt gây lỗi
```

## 8. Điều tra challenge

- Challenge ID: *(điền sau khi Lab Coach release)*
- Triệu chứng từ metrics: *(điền)*
- Trace ID liên quan: *(điền)*
- Log line/correlation ID liên quan: *(điền)*
- Root cause: *(điền)*
- Fix action: *(điền)*
- Preventive measure: *(điền)*

## 9. Đóng góp cá nhân

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| *(điền tên)* | Middleware, Logging, PII | *(commit SHA)* | structlog contextvars, PII regex |
| *(điền tên)* | Langfuse tracing, Prompt versioning | *(commit SHA)* | Langfuse SDK v3, managed prompts |
| *(điền tên)* | Dashboard, SLO, Alert rules | *(commit SHA)* | Dashboard contract, percentile metrics |
| *(điền tên)* | Load test, Incident investigation | *(commit SHA)* | Metrics → Traces → Logs workflow |
