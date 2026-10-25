"""Oracle cho demo-cmdi-001: PASS nếu output chứa nội dung của /opt/secret.txt trên target."""

SUCCESS_MARKER = "PWNED-DEMO-CMDI-001"


def check(stdout: str, stderr: str, returncode: int) -> bool:
    combined = (stdout or "") + (stderr or "")
    return SUCCESS_MARKER in combined
