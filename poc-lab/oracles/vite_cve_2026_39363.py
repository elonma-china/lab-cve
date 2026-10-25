"""Oracle CVE-2026-39363: PASS khi đọc được flag qua WebSocket fetchModule."""

SUCCESS_MARKER = "FLAG{LAB10-VITE-CVE-2026-39363}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
