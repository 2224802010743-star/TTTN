# Quản lý xe ra/vào bãi giữ xe — Flask + MySQL + Admin + Flutter

Bản khởi đầu chạy Windows/LAN, không tính phí gửi xe. Có:
- Flask REST API cho ứng dụng Flutter.
- MySQL qua SQLAlchemy.
- Website Admin đăng nhập, thống kê trong ngày, xe đang gửi, lịch sử, tìm theo biển số.
- Ảnh xe vào/ra lưu trên ổ đĩa máy chủ; database lưu đường dẫn tương đối.
- Xóa theo biển số sẽ xóa toàn bộ lượt vào/ra và ảnh tương ứng.
- OCR biển số là mô-đun tùy chọn; mặc định API nhận `plate` do app gửi. Không tự nhận diện chính xác nếu chưa cấu hình model.

## 1. Cài MySQL trên Windows
1. Tải **MySQL Installer Community** từ trang MySQL chính thức: https://dev.mysql.com/downloads/installer/
2. Chọn MySQL Server 8.4 LTS (hoặc 8.0), cài đặt kiểu Server Only/Developer Default.
3. Đặt mật khẩu mạnh cho tài khoản `root`, ghi lại mật khẩu; giữ cổng `3306`.
4. Mở MySQL Command Line Client hoặc PowerShell và chạy nội dung `database/schema.sql`:
   `cmd /c "mysql -u root -p < database\schema.sql"`
   Nếu lệnh `mysql` không được nhận diện, mở MySQL Command Line Client hoặc thêm thư mục `C:\\Program Files\\MySQL\\MySQL Server 8.4\\bin` vào PATH.
5. `schema.sql` tạo database và user ứng dụng `parking_app`. Thay mật khẩu mẫu `CHANGE_ME_DB_PASSWORD` trong SQL trước khi chạy, sau đó đặt cùng giá trị trong `.env`.

## 2. Cài Python và chạy backend
Khuyến nghị Python 3.11 hoặc 3.12 x64. Mở PowerShell trong thư mục `backend`:
```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```
Sửa `.env`: `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `DATABASE_URL`, `API_DEVICE_TOKEN`. Có thể tạo chuỗi ngẫu nhiên bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"` (chạy riêng cho `SECRET_KEY` và `API_DEVICE_TOKEN`). Backend từ chối khởi động khi còn dùng secret mẫu/quá ngắn hoặc URL không phải MySQL.
`DATABASE_URL` mẫu:
`mysql+pymysql://parking_app:CHANGE_ME_DB_PASSWORD@localhost:3306/parking_db?charset=utf8mb4`

Khởi chạy chế độ phát triển:
```powershell
python app.py
```
Admin: `http://127.0.0.1:5000/admin/login`
API health: `http://127.0.0.1:5000/api/health`

**Không dùng Flask development server khi triển khai thật ra Internet.** Bản này dành cho LAN/lab; production cần Waitress/reverse proxy, HTTPS, firewall, backup, giới hạn truy cập và quản lý secret an toàn. Để chạy Waitress trên LAN, trong thư mục `backend` chạy `.\.venv\Scripts\waitress-serve.exe --listen=0.0.0.0:5000 wsgi:app` hoặc `waitress-serve --listen=0.0.0.0:5000 wsgi:app` sau khi kích hoạt venv.

## 3. Cho điện thoại Android truy cập
- Điện thoại và PC phải cùng Wi-Fi/LAN.
- Lấy IPv4 PC: `ipconfig`, ví dụ `192.168.1.10`.
- Chạy `python app.py` (bind `0.0.0.0`) và cho phép Python/port 5000 qua Windows Defender Firewall chỉ trên mạng Private.
- Trong Flutter đặt `baseUrl = http://192.168.1.10:5000`.
- Android Emulator dùng `http://10.0.2.2:5000` để truy cập host Windows.
- API dùng header `X-Device-Token: <API_DEVICE_TOKEN>`; giữ token bí mật. Chỉ dùng HTTP trong mạng thử nghiệm đáng tin cậy; production phải dùng HTTPS. Có thể khởi chạy bằng `scripts\run_backend.ps1`; để chạy WSGI Waitress thay Flask development server, dùng lệnh ở phần dưới.

## 4. API
Xem chi tiết request/response trong `API_REFERENCE_VI.md`; có thể import `postman_collection.json` vào Postman để thử.
Mọi API nghiệp vụ yêu cầu `X-Device-Token`.
- `GET /api/health`
- `POST /api/vehicles/entry` multipart: `plate`, `image` (file ảnh)
- `POST /api/vehicles/exit` multipart: `plate`, `image` (ảnh ra, tùy chọn)
- `GET /api/vehicles/current?plate=51A12345`
- `GET /api/vehicles/history?plate=51A12345&page=1`
- `GET /api/vehicles/current/<id>` chi tiết lượt đang gửi

Entry trả lỗi 409 nếu biển số đã có lượt chưa ra. Exit trả 404 nếu không tìm thấy lượt đang gửi. Plate được chuẩn hóa chữ hoa và bỏ khoảng trắng/ký tự phân tách.

## 5. Nhận diện biển số Việt Nam (AI/OCR)
Bản đầu tiên **không giả vờ có AI sẵn**: Flutter chụp ảnh và gửi ảnh + biển số người vận hành xác nhận. Có thể bổ sung OCR bằng PaddleOCR/EasyOCR hoặc dịch vụ chuyên biển số, nhưng cần kiểm thử trên ảnh thật tại Việt Nam (góc nghiêng, ban đêm, mưa, xe máy/ô tô, biển 1/2 dòng). Khuyến nghị pipeline: phát hiện vùng biển số (YOLO fine-tune trên dữ liệu phù hợp) → crop/rectify → OCR → chuẩn hóa chuỗi → màn hình xác nhận thủ công. Không tự động cho xe ra nếu confidence thấp; luôn lưu ảnh gốc và log sửa biển số. Kiểm tra giấy phép model/dữ liệu trước khi dùng thương mại.

## 6. Chính sách xóa
Nút xóa trong Admin xóa mọi lượt của biển số và ảnh lưu trong `backend/uploads`. Đây là thao tác không thể hoàn tác. Hãy backup trước khi dùng dữ liệu thật. Tên ảnh được tạo ngẫu nhiên, không dùng tên file người dùng gửi.

## 7. Kiểm tra nhanh
1. Đăng nhập Admin.
2. Dùng Flutter mẫu hoặc Postman gửi `POST /api/vehicles/entry` với multipart `plate=51A12345`, `image=<ảnh>`.
3. Gửi `POST /api/vehicles/exit` cùng biển số; lượt xe sẽ thành `EXITED`.
4. Admin xem “Xe đang gửi”, “Lịch sử”, tìm biển số và thử xóa.

Mật khẩu mặc định không được hard-code trong backend; `.env.example` chỉ là mẫu. Đổi tất cả giá trị mẫu trước khi chạy. `parking_app` chỉ được cấp quyền đọc/ghi dữ liệu, không có quyền quản trị MySQL. `active_plate` là cột sinh tự động có unique index để database ngăn hai lượt đang gửi cho cùng biển số. Nếu bạn đã tạo database bằng phiên bản SQL cũ, hãy sao lưu dữ liệu rồi áp dụng migration phù hợp; không chạy lệnh xóa database trên dữ liệu thật.

## 8. Chạy ví dụ Flutter
Tạo dự án Flutter mới (hoặc dùng dự án hiện có), gộp `http` và `image_picker` trong `flutter_example/pubspec_addition.yaml` vào `pubspec.yaml`, chép `flutter_example/lib/main.dart` và `parking_api.dart` vào thư mục `lib`, rồi chạy `flutter pub get`.
Trong `main.dart`, cập nhật `kApiBaseUrl` và `kDeviceToken`. Với Android Emulator dùng `http://10.0.2.2:5000`; với điện thoại thật dùng IPv4 máy Windows. Để thử HTTP nội bộ, trong `android/app/src/main/AndroidManifest.xml`, khai báo `android.permission.INTERNET` và thuộc tính `android:usesCleartextTraffic="true"` trên thẻ `<application>` (chỉ cho môi trường thử nghiệm LAN; production phải dùng HTTPS). Cài và chạy:
```powershell
flutter pub get
flutter run
```
Màn hình ví dụ cho nhân viên chụp ảnh, nhập biển số thủ công/xác nhận và gửi API. Đây chưa phải nhận diện AI tự động. Không phát hành ứng dụng với token dùng chung nhúng trong mã nguồn. Nếu Android chặn HTTP, chỉ trong môi trường thử nghiệm mới bật `usesCleartextTraffic`; không dùng cấu hình này trong bản production.

## 9. Kiểm thử backend
Từ thư mục `backend`, sau khi cài requirements, chạy `python -m unittest -v test_app.py`. Bộ kiểm thử dùng SQLite trong bộ nhớ để kiểm tra health, xác thực API, luồng vào/ra, CSRF và xóa dữ liệu theo biển số; không thay thế kiểm thử tích hợp với MySQL trên máy Windows.
