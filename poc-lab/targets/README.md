# Bộ lab luyện pentest (5 target)

Năm lab web/API chạy local bằng Docker, dùng để luyện tập pentest có kiểm soát. Mỗi lab có flag và được chấm theo thang 10 điểm.

> Chỉ dùng trên máy lab. Các port chỉ bind `127.0.0.1`. Không tấn công ra ngoài `127.0.0.1` và không phá huỷ dữ liệu.

## 1. Chạy

Yêu cầu: Docker và Docker Compose v2.

```sh
cd poc-lab/targets
docker compose up --build -d     # build và chạy cả 5 lab
docker compose ps                # kiểm tra trạng thái
docker compose down              # dừng và gỡ toàn bộ
```

Chạy riêng một lab (ví dụ lab 2):

```sh
cd poc-lab/targets/demo-gatekeeper-002
docker compose up --build -d
docker compose down
```

Lab 1 và 3 tự tạo lại dữ liệu mỗi lần khởi động. Muốn reset một lab về trạng thái ban đầu thì `docker compose down` rồi `up` lại.

## 2. Danh sách lab

| # | Lab | URL | Cấp độ | Lỗi chính | Thư mục |
|---|---|---|---|---|---|
| 1 | VulnNotes | http://127.0.0.1:8090 | Newbie → Trung cấp | SQLi, IDOR, CMDi, path traversal, stored XSS | `demo-multivuln-001/` |
| 2 | Gatekeeper | http://127.0.0.1:8091 | Trung cấp → Chuyên gia | JWT yếu, JWT `alg: none`, SSTI, SSRF, pickle | `demo-gatekeeper-002/` |
| 3 | Ledger | http://127.0.0.1:8092 | Newbie → Nâng cao | Debug leak, mass assignment, 2nd-order SQLi, race condition, YAML unsafe load | `demo-ledger-003/` |
| 4 | n8n CVE-2026-21858 | http://127.0.0.1:5678 | Nâng cao | Đọc file tuỳ ý qua Form Webhook (n8n 1.65.0) | `cve-2026-n8n-file-read-004/` |
| 5 | Langflow CVE-2026-33017 | http://127.0.0.1:7860 | Nâng cao → Chuyên gia | RCE không cần đăng nhập qua endpoint public (Langflow 1.8.1) | `cve-2026-langflow-rce-005/` |

Mỗi thư mục có `README.md` (mô tả và gợi ý) và `SOLUTIONS.md` (chỉ có ở lab 2 và 3, dùng khi bị kẹt).

## 3. Cách tính điểm

Mỗi lab tổng 10 điểm. Một điểm chỉ được tính khi bạn lấy được flag hoặc hoàn thành tiêu chí tương ứng.

| # | Lab | Phân bổ điểm |
|---|---|---|
| 1 | VulnNotes | 5 lỗi × 2 điểm |
| 2 | Gatekeeper | 1.5 + 2 + 2.5 + 2 + 2 |
| 3 | Ledger | 1 + 1.5 + 2.5 + 2 + 3 |
| 4 | n8n CVE | Phiên bản 2 + xác định CVE 2 + đọc file thử nghiệm 2 + lấy flag 4 |
| 5 | Langflow CVE | Phiên bản 1.5 + liệt kê endpoint 2 + phân biệt auth/public 2 + khai thác và lấy flag 4.5 |

Lab 2 và 3 chia điểm theo độ khó: lỗi càng khó càng nhiều điểm. Lab 4 và 5 có một lỗ hổng nên chấm theo các bước phải làm theo thứ tự. Chi tiết từng lỗi nằm trong `README.md` của lab đó.

Xếp cấp người học theo tổng điểm đạt được:

| Điểm | Cấp | Gợi ý tiếp theo |
|---|---|---|
| Dưới 4 | Newbie | Luyện lại lab 1 và 3 |
| 4 – 7 | Trung cấp | Thử lab 2 và lab 4 |
| Trên 7 | Nâng cao | Thử lab 5 và các lỗi chuyên gia |

## 4. Trạng thái kiểm tra

- Cả 5 lab đã được build và khởi động bằng `docker compose up --build -d`, đều phản hồi HTTP.
- **Lab 1**: đã khai thác đủ 5 lỗi và xác nhận flag.
- **Lab 2 và 3**: chỉ kiểm tra endpoint khởi động, **chưa khai thác đầy đủ từng lỗi**.
- **Lab 4**: lần thử gần nhất gửi request tới `/form/vulnerable-form` chỉ nhận về trang lỗi, **chưa xác nhận lại lỗi đọc file**.
- **Lab 5**: đã khai thác thành công trong lần chạy trước (xem `results/pentestcode_runs/`), **chưa chạy lại trong bộ lab này**.

## 5. Nguồn tham khảo

- Lab 4 và 5 dùng image vulhub có sẵn: `_vulhub-ref/n8n__CVE-2026-21858/` và `_vulhub-ref/langflow__CVE-2026-33017/`.
- Cơ chế lỗi của lab 4 và 5 được đối chiếu theo `results/pentestcode_runs/engagements_by_case/` (`findings.md`, `state.json`).
- Lab 1–3 tự viết, tham chiếu cấu trúc từ `demo-cmdi-001/`.
- Flag của lab 4 và 5 được thêm qua `Dockerfile` vào `/opt/lab/`.
