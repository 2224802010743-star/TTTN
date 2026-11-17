# Bảo mật và kiểm thử

## Bắt buộc trước khi dùng dữ liệu thật
- Thay `SECRET_KEY`, `ADMIN_PASSWORD`, `API_DEVICE_TOKEN`, mật khẩu MySQL bằng chuỗi ngẫu nhiên dài.
- Không commit `.env`; không đưa token API vào Git hoặc ảnh chụp màn hình.
- API token hiện là một token dùng chung cho thiết bị; nếu mất token phải đổi ngay. Không nhúng token dùng chung vào ứng dụng phát hành thực tế vì có thể bị trích xuất. Hệ thống thật nên dùng tài khoản thiết bị riêng, token có thể thu hồi và audit log.
- Chỉ mở port 5000 trong mạng Private; không port-forward từ router ra Internet.
- Dùng HTTPS trong triển khai thật; bật `SESSION_COOKIE_SECURE=True` khi chạy HTTPS.
- Backup MySQL và thư mục `backend/uploads` cùng nhau; kiểm thử phục hồi backup.
- Hạn chế quyền thư mục uploads, kiểm tra dung lượng ổ đĩa và chính sách lưu trữ ảnh.
- Các POST của Admin đã có kiểm tra CSRF ở bản này; vẫn nên bổ sung giới hạn đăng nhập sai, nhật ký quản trị và kiểm thử bảo mật trước khi public.
- Dùng Waitress thay Flask development server khi chạy ổn định: `waitress-serve --listen=0.0.0.0:5000 app:app` (chạy trong thư mục backend).
- Cấu hình Windows Firewall chỉ cho subnet nội bộ truy cập TCP 5000.

## Test API bằng PowerShell (sau khi thay token và có ảnh test)
```powershell
$headers = @{ "X-Device-Token" = "YOUR_LONG_DEVICE_TOKEN" }
$form = @{ plate = "51A12345"; image = Get-Item "C:\temp\car.jpg" }
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/vehicles/entry" -Method Post -Headers $headers -Form $form
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/vehicles/current" -Headers $headers
$formExit = @{ plate = "51A12345"; image = Get-Item "C:\temp\car_exit.jpg" }
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/vehicles/exit" -Method Post -Headers $headers -Form $formExit
```
