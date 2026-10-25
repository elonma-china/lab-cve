"""Oracle Comment2Shell (CVE-2026-93485): PASS khi output chứa flag của lab
(đọc được qua webshell tạo ra từ chuỗi stored-XSS -> admin -> RCE)."""

SUCCESS_MARKER = "FLAG{LAB10-COMMENT2SHELL-CVE-2026-93485}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
