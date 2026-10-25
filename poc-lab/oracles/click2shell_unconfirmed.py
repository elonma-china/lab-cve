"""Oracle Click2Shell (CVE chưa xác nhận chắc chắn): PASS khi output chứa flag
của lab (đọc được qua webshell tạo ra từ chuỗi forced-theme-install -> RCE)."""

SUCCESS_MARKER = "FLAG{LAB10-CLICK2SHELL-UNCONFIRMED}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
