"""Oracle CVE-2026-33017: PASS khi RCE trả về nội dung flag."""

SUCCESS_MARKER = "FLAG{LAB10-LANGFLOW-CVE-2026-33017}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
