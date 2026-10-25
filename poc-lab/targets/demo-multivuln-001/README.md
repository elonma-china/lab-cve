# demo-multivuln-001 — VulnNotes

Target demo tối giản (KHÔNG phải CVE thật, KHÔNG wire vào `harness.py`) dùng để luyện
tập pentest web thủ công. App "VulnNotes" (Flask + SQLite) cố ý cài **5 lỗ hổng**,
mỗi lỗ hổng có 1 flag dạng `FLAG{...}` để tự kiểm chứng khi khai thác thành công.

Chỉ dùng trong lab/local, không expose ra internet.

## Chạy lab

```sh
cd poc-lab/targets/demo-multivuln-001
docker compose up --build
```

App chạy ở `http://127.0.0.1:8090`. Dừng bằng `docker compose down`.

Tài khoản demo có sẵn: `bob` / `bobpw456` (user thường, không phải admin).

## 5 lỗ hổng cần tìm

| # | Lớp lỗi | Khu vực | Mục tiêu |
|---|---|---|---|
| 1 | SQL Injection | Form đăng nhập (`/login`) | Đăng nhập được với tài khoản `admin` mà không biết mật khẩu thật |
| 2 | IDOR | Xem note theo id (`/notes/<id>`) | Đăng nhập bằng `bob`, đọc được note riêng tư của user khác |
| 3 | OS Command Injection | Công cụ diagnostics (`/ping`) | Thực thi lệnh hệ thống khác ngoài `ping`, đọc file bí mật trong container |
| 4 | Path Traversal | Tải file (`/download`) | Đọc file ngoài thư mục `files/` được phép |
| 5 | Stored XSS | Guestbook (`/comments`) | Chèn payload JS chạy khi trang được render lại, có thể đọc được cookie `session_token` |

Mỗi lỗi (trừ #5, vì #5 là XSS chạy phía client) khi khai thác đúng sẽ trả về
chuỗi `FLAG{...}` trong response. Với #5, bằng chứng thành công là payload JS
của bạn thực thi và đọc được giá trị cookie `session_token` (cũng là 1 flag).

Gợi ý công cụ: `curl`, Burp Suite/ZAP (đã có sẵn trong workflow pentest của bạn),
`sqlmap` cho #1 nếu muốn tự động hoá.

Nếu bị kẹt, xem `SOLUTIONS.md` trong thư mục này (có payload mẫu cho từng lỗi).

## Dọn dẹp

```sh
docker compose down -v
```

## Chấm điểm (thang 10)

Mỗi lỗi 2 điểm, tổng 10 điểm. Được tính khi lấy được flag tương ứng.

| # | Lỗi | Điểm |
|---|---|---|
| 1 | SQL Injection (đăng nhập) | 2 |
| 2 | IDOR (xem note người khác) | 2 |
| 3 | OS Command Injection | 2 |
| 4 | Path Traversal | 2 |
| 5 | Stored XSS (đọc được cookie `session_token`) | 2 |
| | **Tổng** | **10** |
