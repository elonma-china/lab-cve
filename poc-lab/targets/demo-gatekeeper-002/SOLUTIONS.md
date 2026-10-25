# Gợi ý — demo-gatekeeper-002

Chỉ đọc khi đã thử và bị kẹt. Đây là gợi ý theo hướng, không phải lời giải đầy đủ.

1. **JWT yếu**: lấy token từ `/login` bằng `guest/guest`, rồi thử bẻ khoá chữ ký HS256 với một danh sách mật khẩu nhỏ (ví dụ các mẫu theo mùa/năm). Khi có secret, tự ký token với `role: admin`.
2. **alg none**: thử đổi header thành `none` và bỏ phần chữ ký. Lưu ý trường `sub` — một giá trị đặc biệt trong payload sẽ đổi flag trả về.
3. **SSTI**: bộ lọc chỉ chặn `{{` và `__`. Thử cú pháp statement `{% ... %}` để xác nhận có thực thi (ví dụ dùng `{% if %}` làm oracle đúng/sai), rồi tìm cách đọc `/opt/ssti_flag.txt`.
4. **SSRF**: thử các cách biểu diễn loopback khác (`127.1`, `0.0.0.0`, `[::]`, `127.0.0.2` tuỳ môi trường). Endpoint đích là `http://127.0.0.1:8080/internal/flag`.
5. **Pickle**: cookie `prefs` có thể đặt bằng `POST /prefs`. Cần tạo object pickle có hành vi tuỳ ý — đọc `/opt/pickle_flag.txt` qua payload đó.
