"""Oracle PHP2Shell (CVE-2026-109618 / CVE-2026-109619): PASS khi output chứa flag."""

SUCCESS_MARKER = "FLAG{LAB10-PHP2SHELL-CVE-2026-109618}"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
