# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: `high_latency_p95` (P95 Latency Vượt Ngưỡng)
- Severity: `Warning`
- SLI/SLO liên quan: `latency_p95_ms <= 3000` (Mục tiêu 99.5%)
- Điều kiện và thời gian duy trì: `latency_p95_ms > 3000` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng trải nghiệm phản hồi chậm, có nguy cơ timeout trên giao diện chat
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel **Latency** trên Dashboard và xem trạng thái incident (`/health`).
  2. Mở một vài Trace gần nhất trên Langfuse để phân tích span waterfall (xác định nghẽn ở Mock RAG hay LLM Generation).
  3. Lấy `correlation_id` từ trace chậm và tra cứu trong `data/logs.jsonl` để kiểm tra chi tiết các bước xử lý.
- Mitigation tạm thời: Tắt incident nếu đang kích hoạt (`python scripts/inject_incident.py --scenario rag_slow --disable`), bật fallback cache hoặc điều chỉnh timeout.
- Owner: `oncall-ai-team`

## Alert 2

- Tên: `high_error_rate` (Tỉ Lệ Lỗi Request Tăng Cao)
- Severity: `Critical`
- SLI/SLO liên quan: `error_rate_pct <= 2%` (Mục tiêu 99.0%)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` liên tục trong 2 phút
- Ảnh hưởng tới người dùng: Request chat thất bại (HTTP 500), gián đoạn dịch vụ trợ lý ảo
- Ba bước kiểm tra đầu tiên:
  1. Xem panel **Errors** trên Dashboard để xác định tỉ lệ lỗi và phân loại `error_type` (ví dụ: ToolError, ConnectionError).
  2. Mở `data/logs.jsonl`, lọc các log `request_failed` để đọc thông báo lỗi và stack trace.
  3. Mở Trace trên Langfuse có trạng thái lỗi để xem span và input gây ra crash.
- Mitigation tạm thời: Tắt tool hoặc incident lỗi (`/incidents/tool_fail/disable`), rollback code/prompt hoặc khởi động lại container API.
- Owner: `oncall-ai-team`

## Alert 3

- Tên: `quality_score_drop` (Điểm Chất Lượng Phản Hồi Giảm Sút)
- Severity: `Warning`
- SLI/SLO liên quan: `quality_score_avg >= 0.75` (Mục tiêu 95.0%)
- Điều kiện và thời gian duy trì: `quality_score_avg < 0.75` liên tục trong 10 phút
- Ảnh hưởng tới người dùng: Câu trả lời kém chất lượng, cụt ngủn, thiếu thông tin RAG hoặc bị redact sai ngữ cảnh
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel **Quality** trên Dashboard và so sánh với baseline.
  2. Kiểm tra `LANGFUSE_PROMPT_LABEL` trong `.env` và xem phiên bản prompt đang chạy có bị thay đổi không.
  3. Đối chiếu log `response_sent` (trường `quality_score` và `answer_preview`) với các câu hỏi tương ứng trong `data/logs.jsonl`.
- Mitigation tạm thời: Rollback prompt label về version `baseline` (`LANGFUSE_PROMPT_LABEL=baseline`), kiểm tra lại module retrieve tài liệu.
- Owner: `oncall-ai-team`
