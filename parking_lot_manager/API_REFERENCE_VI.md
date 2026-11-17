# REST API — tham chiếu nhanh

Base URL trong Android Emulator là `http://10.0.2.2:5000`; với điện thoại thật thay bằng IPv4 máy Windows. Trừ `/api/health`, các endpoint đều cần header:

```http
X-Device-Token: <giá trị API_DEVICE_TOKEN trong backend/.env>
```

## 1. Ghi nhận xe vào
`POST /api/vehicles/entry` — `multipart/form-data`

| Trường | Bắt buộc | Mô tả |
|---|---|---|
| `plate` | Có | Biển số đã xác nhận, ví dụ `51A-123.45` |
| `image` | Có | Ảnh JPG/JPEG/PNG/WEBP, tối đa theo `MAX_CONTENT_LENGTH_MB` |

Thành công: HTTP `201`; biển số trả về đã chuẩn hóa thành chữ hoa và bỏ ký tự phân cách. `409` nghĩa là biển số đã có lượt đang gửi.

## 2. Ghi nhận xe ra
`POST /api/vehicles/exit` — `multipart/form-data`

| Trường | Bắt buộc | Mô tả |
|---|---|---|
| `plate` | Có | Biển số đã xác nhận |
| `image` | Không | Ảnh xe ra; nếu có sẽ được lưu cùng lượt |

Thành công HTTP `200`. `404` nếu không có lượt `IN` cho biển số đó. Không tính tiền gửi xe.

## 3. Xe đang gửi
`GET /api/vehicles/current?plate=51A12345`

Trường `plate` là tùy chọn; không truyền thì trả tối đa 500 lượt mới nhất đang `IN`.

## 4. Lịch sử
`GET /api/vehicles/history?plate=51A12345&page=1`

Phân trang 30 bản ghi/trang, có các trường `items`, `page`, `pages`, `total`.

## 5. Chi tiết và ảnh
- `GET /api/vehicles/current/<id>` lấy chi tiết lượt đang gửi.
- `GET /api/images/<filename>` trả ảnh khi có `X-Device-Token`.
- Website Admin xem ảnh qua route yêu cầu phiên đăng nhập.

## Mã trạng thái phổ biến

| HTTP | Ý nghĩa |
|---|---|
| `200` | Thành công |
| `201` | Tạo lượt xe vào thành công |
| `400` | Biển số hoặc ảnh không hợp lệ |
| `401` | Thiếu/sai token thiết bị |
| `404` | Không có lượt xe đang gửi |
| `409` | Biển số đã có lượt đang gửi hoặc xung đột dữ liệu |
| `413` | Ảnh lớn hơn giới hạn |
| `500` | Lỗi máy chủ; xem terminal log |

Mỗi lỗi API trả JSON có `error` và `message` nếu đi qua các nhánh xử lý nghiệp vụ.
