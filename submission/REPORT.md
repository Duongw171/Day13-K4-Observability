# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò: **Bùi Công Hậu — Logging & PII**

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** (35 log records, 16 correlation IDs)
- Tổng số traces: Nhóm phụ trách Tracing cập nhật
- Số PII leak còn lại: **0**
- Link/đường dẫn dashboard: Nhóm phụ trách Dashboard cập nhật

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

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

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
| Bùi Công Hậu | Correlation middleware; log enrichment; recursive PII redaction; unit/integration tests; evidence Logging & PII | Chưa commit — cập nhật SHA sau khi commit | Cách cô lập context giữa các request, thứ tự processor trong structured logging, hashing định danh và kiểm chứng PII độc lập bằng validator |
