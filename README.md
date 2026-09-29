# 🔍 Shopee Duet Checker

Phần mềm kiểm tra quyền Duet / Stitch của video Shopee, tìm kiếm video Viral và thống kê sản phẩm Affiliate tiếp thị liên kết đa quốc gia (Việt Nam, Philippines, Indonesia, Thái Lan, Malaysia, Singapore).

---

## 📌 Tính năng chính

1. **🔍 Scanner (Quét Video Shopee)**:
   - Quét danh sách video từ Profile Creator / Shop hoặc Hashtag.
   - Nhận diện trạng thái cho phép Duet / Stitch (`allow_duet`).
   - Lấy thống kê: Lượt xem, lượt thích, bình luận, ngày đăng.
   - Phân tích sản phẩm liên kết: Tên SP, link rút gọn / direct, giá bán, số lượng đã bán.

2. **🔥 Viral Finder**:
   - Tự động cào và phát hiện video viral theo từ khóa/hashtag và creator liên quan.
   - Hỗ trợ chạy đa luồng (Multi-threading) với cơ chế xoay vòng nhiều tài khoản Shopee Cookie.
   - Chấm điểm và lọc video theo tiêu chí: Lượt xem/ngày, tỷ lệ tương tác, thời gian đăng.

3. **🪟 Thống kê Cửa sổ Sản phẩm**:
   - Đếm số lượng video đang gắn affiliate cho từng sản phẩm cụ thể.
   - Lưu trữ dữ liệu tối ưu qua SQLite (`data/shopee_duet.db`).

4. **📱 Xem trên Điện thoại (Wi-Fi + QR Code)**:
   - Tích hợp máy chủ mini nội bộ phát danh sách video đã lọc sang Safari / Chrome trên điện thoại.
   - Nút bấm trực tiếp mở ngay video trong ứng dụng Shopee để tiến hành Duet / xem sản phẩm.

5. **📊 Đồng bộ Google Sheet**:
   - Tự động xuất kết quả quét lên Google Sheet qua Service Account.
   - Tự động lọc trùng Video ID giữa các lần quét.

---

## 🚀 Hướng dẫn cài đặt & Sử dụng

### 1. Yêu cầu hệ thống
- Hệ điều hành: Windows 10 / 11
- Python: Phiên bản 3.10 trở lên (Tick chọn **Add Python to PATH** khi cài đặt)
- Git: Cần cài đặt Git (tải tại [git-scm.com](https://git-scm.com/)) để sử dụng tính năng tự động cập nhật.

### 2. Khởi chạy phần mềm
- Nhấp đúp vào tệp **`run.bat`**.
- Script sẽ tự động kiểm tra và cài đặt các thư viện cần thiết (`PyQt6`, `requests`, `urllib3`, `qrcode`, `gspread`) và mở giao diện ứng dụng.

### 3. Cập nhật mã nguồn trên các máy trạm
- Nhấp đúp vào tệp **`update.bat`**.
- Script sẽ tự động kết nối với GitHub repository, kéo mã nguồn mới nhất về, cập nhật thư viện và báo số phiên bản hiện tại.

### 4. Đẩy mã nguồn mới lên GitHub (Dành cho máy chính)
- Nhấp đúp vào tệp **`upload-github.bat`**.
- Script sẽ tự động tăng số phiên bản (ví dụ từ `1.1` lên `1.2`, `1.3`...), tự động loại trừ các file cookie cá nhân / database nặng, và đẩy code lên repository:
  👉 `https://github.com/thincole/checkduet`

---

## 🔒 Bảo mật dữ liệu
- File `settings.json` (chứa Cookie tài khoản Shopee, API key, đường dẫn Google Sheet credential) và database SQLite `data/*.db` đã được cấu hình trong `.gitignore` nhằm đảm bảo **an toàn tuyệt đối**, không rò rỉ cookie ra bên ngoài khi đẩy code lên GitHub.
- Mẫu cấu hình chuẩn được cung cấp tại `settings.example.json`.
