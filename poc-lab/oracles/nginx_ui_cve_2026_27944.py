"""Oracle CVE-2026-27944: PASS khi bypass auth bằng node secret và tạo được admin mới."""

SUCCESS_MARKER = "ADMIN-API-OK"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined and "poclabadmin" in combined
