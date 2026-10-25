# demo-ledger-003 — Ledger

Ứng dụng ví/sổ cái với 5 lỗi về logic nghiệp vụ và injection. Cấp độ: **Newbie → Nâng cao**.

```sh
cd poc-lab/targets/demo-ledger-003
docker compose up --build -d     # http://127.0.0.1:8092
docker compose down
```

Bắt đầu bằng `GET /` để xem danh sách endpoint.

| # | Lỗi | Vị trí | Mức | Gợi ý hướng đi |
|---|---|---|---|---|
| 1 | Debug endpoint lộ cấu hình | `/debug/config` | Newbie | Thử các đường dẫn quản trị/debug phổ biến |
| 2 | Mass assignment | `/profile/update` | Newbie–Trung cấp | Hàm update nhận mọi trường client gửi lên |
| 3 | 2nd-order SQLi | `/register` → `/reports` → `/reports/<id>` | Nâng cao | Dữ liệu được lưu an toàn ở bước 1 nhưng dùng lại không an toàn ở bước 3 |
| 4 | Race condition (TOCTOU) | `/coupon/redeem` | Trung cấp–Nâng cao | Kiểm tra `redeemed` và cập nhật là 2 bước riêng; gửi song song để khai thác |
| 5 | YAML unsafe load | `/import` | Chuyên gia | `yaml.load` với `Loader=yaml.Loader` |

Flag:
- Lỗi 1: trong response `/debug/config`.
- Lỗi 2: khi nâng role lên `admin` cho một user.
- Lỗi 3: khi báo cáo lộ ra người dùng `admin`.
- Lỗi 4: khi số dư sau khi đổi coupon ≥ 200.
- Lỗi 5: đọc `/opt/yaml_flag.txt` trong container.

Lưu ý khi làm lỗi 4: cần gửi nhiều request đồng thời. Coupon chỉ có một mã `WELCOME50` nên có thể cần tạo thêm user và tái sử dụng trong cùng cửa sổ race (lab này không tự reset coupon).

Nếu bị kẹt, xem `SOLUTIONS.md`.

## Chấm điểm (thang 10)

Điểm phân theo độ khó, tổng 10 điểm. Được tính khi lấy được flag tương ứng.

| # | Lỗi | Mức | Điểm |
|---|---|---|---|
| 1 | Debug endpoint lộ cấu hình | Newbie | 1 |
| 2 | Mass assignment | Newbie–Trung cấp | 1.5 |
| 3 | 2nd-order SQLi | Nâng cao | 2.5 |
| 4 | Race condition (TOCTOU) | Trung cấp–Nâng cao | 2 |
| 5 | YAML unsafe load | Chuyên gia | 3 |
| | **Tổng** | | **10** |
