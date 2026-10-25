"""Target demo tối giản: lỗi command-injection qua tham số 'host' trong endpoint /ping.

Dùng để kiểm thử end-to-end của harness (Option A), KHÔNG phải CVE thật.
Khi thêm CVE thật, thay thư mục này bằng image vulhub/ứng dụng đúng version.
"""
import subprocess
from flask import Flask, request

app = Flask(__name__)


@app.get("/ping")
def ping():
    host = request.args.get("host", "127.0.0.1")
    # Lỗ hổng cố ý: nối chuỗi thẳng vào shell command.
    out = subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True, text=True, timeout=5)
    return out.stdout + out.stderr, 200


@app.get("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
