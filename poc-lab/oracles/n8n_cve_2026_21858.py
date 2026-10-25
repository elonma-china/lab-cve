"""Oracle CVE-2026-21858: PASS khi form webhook trả về nội dung flag."""

SUCCESS_MARKER = "FLAG{LAB10-N8N-CVE-2026-21858}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
