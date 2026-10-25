# Gợi ý — demo-ledger-003

1. **Debug**: `GET /debug/config` trả về cả `api_token` và flag. Đây là lỗi lộ thông tin qua endpoint không cần xác thực.
2. **Mass assignment**: `POST /profile/update` với JSON có trường `username` (định danh) và `role` (trường không nên cho client đặt). Lưu ý `data.pop("username")` chỉ bỏ username, các trường còn lại đi thẳng vào câu UPDATE.
3. **2nd-order SQLi**: đăng ký user có username chứa ký tự đặc biệt của SQL, sau đó tạo report với username đó rồi gọi `GET /reports/<id>`. Thử điều kiện luôn đúng để liệt kê toàn bộ user; chú ý trường `role` trong kết quả.
4. **Race**: hàm kiểm tra `redeemed` và hàm cập nhật tách rời, có `sleep(0.2)` ở giữa. Gửi nhiều request `/coupon/redeem` song song với cùng một code để nhiều lần cộng tiền trước khi `redeemed` được đặt. Cần số dư cuối ≥ 200.
5. **YAML**: `POST /import` nhận YAML thô và dùng `yaml.Loader` đầy đủ. Tag Python trong YAML có thể gọi hàm hệ thống. Mục tiêu là đọc `/opt/yaml_flag.txt`; hàm trả về `flag` chỉ khi kết quả chứa chuỗi `FLAG`, nên hãy để output của payload có chuỗi đó.
