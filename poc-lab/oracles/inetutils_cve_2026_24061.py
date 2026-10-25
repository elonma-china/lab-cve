"""Oracle CVE-2026-24061: PASS khi có root shell và đọc được flag."""

SUCCESS_MARKER = "FLAG{LAB10-INETUTILS-CVE-2026-24061}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined and "uid=0(root)" in combined
