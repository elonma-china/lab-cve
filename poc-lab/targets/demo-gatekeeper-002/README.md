# demo-gatekeeper-002 — Gatekeeper

Cổng xác thực Flask với 5 lỗi. Cấp độ: **Trung cấp → Chuyên gia**.

```sh
cd poc-lab/targets/demo-gatekeeper-002
docker compose up --build -d     # http://127.0.0.1:8091
docker compose down
```

Tài khoản đăng nhập thường: `guest` / `guest` (`POST /login`).

| # | Lỗi | Vị trí | Mức | Gợi ý hướng đi |
|---|---|---|---|---|
| 1 | JWT ký secret yếu | `/login`, `/admin` | Newbie–Trung cấp | Thử bẻ khoá chữ ký HS256 bằng danh sách mật khẩu phổ biến |
| 2 | JWT chấp nhận `alg: none` | `/admin` | Trung cấp | Đọc kỹ logic `verify_token` |
| 3 | SSTI (Jinja2) | `/greet?name=` | Nâng cao | Bộ lọc chặn `{{` và `__`, không chặn `{%` |
| 4 | SSRF | `/fetch?url=` | Trung cấp–Nâng cao | Bộ lọc chỉ chặn chuỗi `localhost` và `127.0.0.1`; `/internal/flag` chỉ trả lời khi nguồn là loopback |
| 5 | Pickle deserialization | `/prefs` (cookie) | Chuyên gia | Cookie `prefs` là base64 của pickle, được `loads` mà không kiểm tra |

Flag nằm ở:
- Lỗi 1–2: trả về trong `/admin` khi token hợp lệ có role admin.
- Lỗi 3: `/opt/ssti_flag.txt` trong container.
- Lỗi 4: trả về từ `/internal/flag` (chỉ đọc được qua SSRF).
- Lỗi 5: `/opt/pickle_flag.txt` trong container.

Nếu bị kẹt, xem `SOLUTIONS.md` (chỉ gợi ý, không có payload đầy đủ).

## Chấm điểm (thang 10)

Điểm phân theo độ khó, tổng 10 điểm. Được tính khi lấy được flag tương ứng.

| # | Lỗi | Mức | Điểm |
|---|---|---|---|
| 1 | JWT secret yếu | Newbie–Trung cấp | 1.5 |
| 2 | JWT `alg: none` | Trung cấp | 2 |
| 3 | SSTI (Jinja2) | Nâng cao | 2.5 |
| 4 | SSRF | Trung cấp–Nâng cao | 2 |
| 5 | Pickle deserialization | Chuyên gia | 2 |
| | **Tổng** | | **10** |
