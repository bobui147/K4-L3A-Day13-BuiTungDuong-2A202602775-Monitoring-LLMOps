# Alert và runbook

Các cảnh báo dưới đây dựa trên triệu chứng mà người dùng quan sát được. Kênh
nhận cảnh báo là Slack `#llmops-alerts`.

## High request latency

- **Severity / duration:** warning, duy trì 10 phút.
- **Điều kiện:** P95 `latency_ms > 3000` trong cửa sổ 10 phút.
- **SLI/SLO:** SLO `fast_successful_requests`; request chậm tiêu thụ error budget.
- **Ảnh hưởng:** người dùng phải chờ lâu hoặc bỏ request.
- **Owner:** `platform-oncall`.
- **Kiểm tra đầu tiên:** (1) xác nhận P95/TTFT và thời điểm tăng trên dashboard;
  (2) lọc log chậm và lấy `correlation_id`; (3) mở trace tương ứng, so sánh
  thời lượng observation `retrieval` và `fake-llm-generation`.
- **Mitigation:** giảm concurrency, tắt incident practice nếu đang bật, giới hạn
  output token; nếu retrieval chậm thì chuyển sang nguồn dự phòng/cache.
- **Khôi phục:** đóng cảnh báo khi P95 dưới 3000 ms liên tục 10 phút và ghi lại
  correlation/trace ID dùng để xác minh.

## Elevated request error rate

- **Severity / duration:** critical, duy trì 5 phút.
- **Điều kiện:** tỷ lệ `request_failed / request_received > 2%` trong 5 phút.
- **SLI/SLO:** request lỗi là bad event và tiêu thụ error budget.
- **Ảnh hưởng:** người dùng không nhận được câu trả lời.
- **Owner:** `platform-oncall`.
- **Kiểm tra đầu tiên:** (1) xem error breakdown theo `error_type`; (2) lấy một
  `correlation_id` từ `request_failed`; (3) kiểm tra trace và observation cuối
  cùng trước lỗi, đồng thời xác nhận retrieval success.
- **Mitigation:** rollback thay đổi gần nhất, tắt incident practice, hoặc chuyển
  dependency lỗi sang fallback; không retry không giới hạn.
- **Khôi phục:** error rate dưới 2% liên tục 10 phút và request kiểm thử thành công.

## Degraded answer quality

- **Severity / duration:** warning, duy trì 15 phút.
- **Điều kiện:** trung bình `quality_score < 0.75` trong 15 phút.
- **SLI/SLO:** quality guardrail tối thiểu 0.75; kiểm tra thêm retrieval success
  phải đạt ít nhất 90%.
- **Ảnh hưởng:** câu trả lời vẫn trả về nhưng thiếu liên quan hoặc không hữu ích.
- **Owner:** `llm-application-oncall`.
- **Kiểm tra đầu tiên:** (1) đối chiếu quality và retrieval success; (2) lấy
  correlation ID của các response điểm thấp; (3) kiểm tra prompt name/label/version,
  retrieval observation và generation usage trong trace.
- **Mitigation:** rollback label `production` về prompt baseline đã xác minh;
  nếu retrieval giảm thì dùng cache hoặc nguồn dữ liệu dự phòng.
- **Khôi phục:** quality trung bình đạt ít nhất 0.75 và retrieval success đạt 90%
  liên tục 15 phút.
