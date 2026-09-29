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
   - Hỗ trợ chạy đa luồng (Multi-threading) với cơ chế xoay vòng danh sách Shopee Cookie.
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

## 🚀 Hướng dẫn trên MÁY MỚI (Cực kỳ đơn giản)

### 1. Tải code về máy mới
- **Cách 1 (Nhanh nhất)**: Mở CMD gõ:
  ```cmd
  git clone https://github.com/thincole/checkduet.git
  ```
- **Cách 2**: Vào https://github.com/thincole/checkduet bấm **Code** -> **Download ZIP** và giải nén.

### 2. Cài đặt tự động 1-Click
- Vào thư mục vừa tải, nhấp đúp vào:
  👉 **`install.bat`**
- File này sẽ **tự động làm toàn bộ mọi thứ**:
  1. Tự tải và cài đặt Python (tự động bật PATH).
  2. Tự tải và cài đặt Git.
  3. Tự cài đặt toàn bộ thư viện cần thiết (`PyQt6`, `requests`, `qrcode`, `gspread`...).
  4. Tự tạo lối tắt (Shortcut) **Shopee Duet Checker** ngoài màn hình Desktop.
  5. Mở phần mềm lên sử dụng ngay.

---

## 🔄 Cập nhật phiên bản mới trên các máy khác
- Nhấp đúp vào **`update.bat`** để tự động kéo code mới nhất từ GitHub về.
