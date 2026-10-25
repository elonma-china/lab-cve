"""Oracle CVE-2025-30208: PASS khi đọc được flag đặt ngoài project root."""

SUCCESS_MARKER = "FLAG{LAB10-VITE-CVE-2025-30208}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
