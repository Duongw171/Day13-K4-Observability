# Evidence — Day13 Observability Lab

## Danh sách evidence

| File | Nội dung |
|------|---------|
| `validate_logs_result.txt` | Output của `python scripts/validate_logs.py` → **100/100** |
| `validate_dashboard_result.txt` | Output của `python scripts/validate_dashboard.py` → **HỢP LỆ: 6/6 panel** |
| `pytest_results.txt` | Output của `python -m pytest tests/ -v` → **22/22 PASSED** |
| `sample_logs_with_correlation_id.jsonl` | 10 dòng đầu từ `data/logs.jsonl` — minh chứng correlation_id + enrichment fields |
| `pii_redaction_evidence.jsonl` | Các log lines có PII đã bị redact (REDACTED_PHONE_VN, REDACTED_CREDIT_CARD, REDACTED_EMAIL) |

## Còn thiếu (cần thực hiện thủ công với Langfuse)

- `trace_list.png` — ảnh chụp danh sách ≥10 traces trên Langfuse
- `trace_waterfall.png` — ảnh waterfall của một trace cụ thể
- `prompt_v1_v2.png` — ảnh danh sách 2 prompt version trên Langfuse
- `prompt_rollback.png` — ảnh trước/sau khi đổi label hoặc rollback
- `dashboard_6panels.png` — ảnh dashboard 6 panel (dùng Streamlit/Grafana/notebook)

## Cách lấy evidence Langfuse

1. Điền `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY` vào `.env`
2. Chạy: `python scripts/generate_logs.py` (hoặc load test với uvicorn)
3. Mở Langfuse Cloud → Traces → chụp ảnh
4. Mở Prompts → tạo v1 (label: production/baseline) và v2 (label: candidate)
5. Chụp ảnh rollback và lưu vào thư mục này

## Key metrics từ logs

- **Correlation IDs unique**: 15
- **PII leaks**: 0
- **Records total**: 31 (15 request_received + 15 response_sent + 1 app_started)
- **Enrichment fields**: user_id_hash, session_id, feature, model, env — đầy đủ trong mọi API log
