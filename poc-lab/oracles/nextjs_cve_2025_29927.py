"""Oracle CVE-2025-29927: PASS khi dashboard admin truy cập được mà không cần auth."""

MARKERS = ("Admin Dashboard", "protected page")


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return returncode == 0 and any(marker in combined for marker in MARKERS)
