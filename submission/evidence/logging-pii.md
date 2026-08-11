# Evidence — Logging & PII

Người thực hiện: **Bùi Công Hậu**

Vai trò: **Logging & PII**

## Kết quả kiểm thử

Lệnh:

```powershell
python -m pytest -q --basetemp=.pytest-tmp-role
```

Kết quả:

```text
28 passed, 2 warnings in 2.86s
```

Hai warning là cảnh báo deprecation của FastAPI `on_event`, không thuộc phạm vi Logging & PII và không làm test thất bại.

## Kết quả validator

Lệnh:

```powershell
python scripts/validate_logs.py
```

Kết quả cuối:

```text
Total log records analyzed: 35
Records with missing required fields: 0
Records with missing enrichment (context): 0
Unique correlation IDs found: 16
Potential PII leaks detected: 0

+ [PASSED] Basic JSON schema
+ [PASSED] Correlation ID propagation
+ [PASSED] Log enrichment
+ [PASSED] PII scrubbing

Estimated Score: 100/100
```

## Correlation ID và metadata

Request kiểm chứng trả:

```text
status=200
x-request-id=logging-pii-evidence
x-response-time-ms=153
```

Hai event liên quan đều có cùng correlation ID và đủ metadata:

```json
{"service":"api","event":"request_received","correlation_id":"logging-pii-evidence","user_id_hash":"cbb96d345bf3","session_id":"pii-evidence-session","feature":"qa","model":"claude-sonnet-4-5","env":"dev"}
{"service":"api","event":"response_sent","correlation_id":"logging-pii-evidence","user_id_hash":"cbb96d345bf3","session_id":"pii-evidence-session","feature":"qa","model":"claude-sonnet-4-5","env":"dev","latency_ms":150}
```

## PII redaction

Request sử dụng dữ liệu kiểm thử tổng hợp cho bốn loại PII bắt buộc. Log chỉ còn bản đã che:

```json
{"event":"request_received","payload":{"message_preview":"Email [REDACTED_EMAIL] phone [REDACTED_PHONE_VN] CCCD [REDACTED_CCCD] card [REDA..."},"correlation_id":"logging-pii-evidence"}
```

Redaction chạy sau bước format exception và trước khi ghi file, đồng thời xử lý đệ quy dictionary, list, tuple và set. Raw user ID không được ghi log; hệ thống chỉ ghi SHA-256 rút gọn 12 ký tự.
