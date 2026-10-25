"""Oracle CVE-2026-40281: PASS khi command output chứa flag của lab."""

SUCCESS_MARKER = "FLAG{LAB10-GOTENBERG-CVE-2026-40281}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
