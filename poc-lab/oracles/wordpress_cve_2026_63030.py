"""Oracle WP2Shell (CVE-2026-63030 + CVE-2026-60137): PASS khi output chứa flag
của lab (được mount tại /opt/lab/flag trên target); PoC cần đọc được file này
sau khi hoàn tất chuỗi khai thác (route confusion + SQLi -> admin)."""

SUCCESS_MARKER = "FLAG{LAB10-WORDPRESS-CVE-2026-63030}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
