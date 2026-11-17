# Lộ trình AI nhận diện biển số Việt Nam

Hiện bộ code backend cố ý chưa tuyên bố có mô hình AI sẵn. Một mô hình phát hiện xe nói chung không đủ để nhận diện chính xác biển số Việt Nam. Để làm đúng cần mô hình phát hiện vùng biển số và OCR nhận ký tự, đánh giá trên ảnh thật của bãi xe.

## Pipeline đề xuất
1. Flutter chụp ảnh ở khoảng cách, góc, ánh sáng ổn định.
2. Bộ phát hiện biển số (license-plate detector) trả về bounding box.
3. Crop và hiệu chỉnh phối cảnh; OCR đọc ký tự biển số một hoặc hai dòng.
4. Chuẩn hóa chuỗi; tạo danh sách ứng viên và confidence.
5. Nếu confidence thấp hoặc chuỗi không hợp lệ, yêu cầu nhân viên xác nhận. Không tự cho xe ra chỉ dựa vào OCR.
6. Lưu ảnh gốc và chuỗi cuối cùng đã xác nhận để kiểm tra khi có tranh chấp.

## Chọn công nghệ
- OCR: đánh giá PaddleOCR (nhiều mô hình OCR và pipeline; cài đặt Windows/Python cần đối chiếu đúng phiên bản tài liệu đang dùng) hoặc một OCR engine có license phù hợp. OCR chung không thay thế detector biển số.
- Detector: ưu tiên model có trọng số được huấn luyện chuyên biệt trên biển số Việt Nam và có license rõ ràng. Không dùng YOLO pretrained nhận diện người/xe rồi kỳ vọng nó tìm được biển số.
- Với đồ án cá nhân, có thể thử nghiệm detector + OCR trên máy Windows, nhưng cần thu thập ảnh từ nhiều điều kiện: xe máy/ô tô, ban ngày/ban đêm, mưa, nghiêng, lóa sáng, biển bẩn, biển hai dòng.

## Cảnh báo giấy phép
Ultralytics ghi rõ lựa chọn AGPL-3.0 và Enterprise; với sản phẩm riêng tư/thương mại có thể phát sinh nghĩa vụ cấp phép hoặc công khai mã nguồn. Đọc điều khoản chính thức trước khi chọn: https://www.ultralytics.com/license
Tài liệu bắt đầu chính thức: https://docs.ultralytics.com/

## Tiêu chí nghiệm thu tối thiểu
- Đo tỷ lệ đọc đúng toàn bộ biển số, không chỉ tỷ lệ nhận diện ký tự đơn lẻ.
- Tách tập kiểm thử độc lập theo ngày/điều kiện ánh sáng.
- Báo cáo false accept (đọc nhầm thành biển số hợp lệ) và false reject (không đọc được).
- Có xác nhận thủ công, audit dữ liệu đã sửa, và cơ chế xử lý khi ảnh không đủ rõ.

Cho tới khi mô hình được cài và đánh giá, luồng an toàn là nhân viên xác nhận biển số trong Flutter. API hiện nhận `plate` do ứng dụng gửi, không tự suy ra biển số từ ảnh.
