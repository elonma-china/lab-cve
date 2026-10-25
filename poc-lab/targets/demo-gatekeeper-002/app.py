"""demo-gatekeeper-002 — cổng xác thực "Gatekeeper" với 5 lỗi cố ý (đa dạng, có đánh đố).

Chỉ dùng trong lab local. Không phải CVE. Xem README.md để biết phân cấp độ khó.
"""
import base64
import hashlib
import hmac
import json
import os
import pickle
import socket
from urllib.parse import urlparse

import requests
from flask import Flask, abort, jsonify, make_response, render_template_string, request

app = Flask(__name__)

# [Lỗi 1 — Newbie] JWT ký bằng secret yếu nằm trong danh sách mật khẩu phổ biến.
JWT_SECRET = "summer2026"
FLAG_ADMIN = os.environ.get("FLAG_ADMIN", "FLAG{JWT_WEAK_SECRET_CRACKED}")
FLAG_ALG_NONE = "FLAG{JWT_ALG_NONE_ACCEPTED}"
FLAG_SSTI = "FLAG{SSTI_JINJA_BLACKLIST_BYPASS}"
FLAG_SSRF = "FLAG{SSRF_INTERNAL_ONLY_ENDPOINT}"
FLAG_PICKLE = "FLAG{PICKLE_PREFS_RCE}"


def b64url_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64url_enc(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def sign_hs256(header: dict, payload: dict, secret: str) -> str:
    h = b64url_enc(json.dumps(header, separators=(",", ":")).encode())
    p = b64url_enc(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{b64url_enc(sig)}"


def verify_token(token: str):
    """Trả về payload nếu token hợp lệ, None nếu không."""
    try:
        h_b64, p_b64, s_b64 = token.split(".")
        header = json.loads(b64url_dec(h_b64))
        payload = json.loads(b64url_dec(p_b64))
    except Exception:
        return None
    alg = header.get("alg")
    # [Lỗi 2 — Intermediate] Chấp nhận alg "none" (không kiểm chữ ký) khi header tự khai.
    if alg == "none":
        return payload
    if alg == "HS256":
        expected = hmac.new(JWT_SECRET.encode(), f"{h_b64}.{p_b64}".encode(), hashlib.sha256).digest()
        if hmac.compare_digest(b64url_enc(expected), s_b64):
            return payload
    return None


@app.get("/")
def index():
    return (
        "<h2>Gatekeeper</h2>"
        "<ul>"
        "<li><a href='/login'>POST /login (lấy token)</a></li>"
        "<li>GET /admin (cần token role=admin)</li>"
        "<li>GET /greet?name=... (chào hỏi)</li>"
        "<li>GET /fetch?url=... (kiểm tra link)</li>"
        "<li>GET /prefs / POST /prefs (tuỳ chọn người dùng)</li>"
        "</ul>"
    )


@app.post("/login")
def login():
    data = request.get_json(silent=True) or request.form
    user = data.get("username", "")
    pw = data.get("password", "")
    if user == "guest" and pw == "guest":
        payload = {"sub": "guest", "role": "user"}
        return jsonify(token=sign_hs256({"alg": "HS256", "typ": "JWT"}, payload, JWT_SECRET))
    return jsonify(error="sai thông tin"), 401


@app.get("/admin")
def admin():
    auth = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    payload = verify_token(auth)
    if payload is None:
        abort(401)
    if payload.get("role") != "admin":
        return jsonify(error="cần role=admin", you=payload), 403
    # Gợi ý: nếu thấy FLAG_ALG_NONE thì bạn đã dùng alg none ở lỗi 2.
    flag = FLAG_ALG_NONE if payload.get("sub") == "root-via-none" else FLAG_ADMIN
    return jsonify(message="chào admin", flag=flag)


@app.get("/greet")
def greet():
    name = request.args.get("name", "khách")
    # [Lỗi 3 — Advanced] SSTI: chặn "{{" và "__" nhưng vẫn để lọt cú pháp {% %} và {# #}.
    if "{{" in name or "__" in name:
        return "Tên chứa ký tự bị chặn", 400
    tpl = f"<p>Xin chào, {name}</p>"
    return render_template_string(tpl)


@app.get("/fetch")
def fetch():
    url = request.args.get("url", "")
    parsed = urlparse(url)
    # [Lỗi 4 — Intermediate/Advanced] SSRF: chỉ chặn chuỗi "localhost"/"127.0.0.1".
    host = parsed.hostname or ""
    if "localhost" in url or "127.0.0.1" in url:
        return "URL nội bộ bị chặn", 403
    if parsed.scheme not in ("http", "https"):
        return "chỉ http/https", 400
    try:
        r = requests.get(url, timeout=3, allow_redirects=False)
        return make_response(r.text[:500], r.status_code)
    except requests.RequestException as exc:
        return f"lỗi kết nối: {exc}", 502


@app.get("/internal/flag")
def internal_flag():
    # Chỉ trả flag khi request đến từ loopback (kiểm tra theo IP nguồn của socket).
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)
    return FLAG_SSRF


@app.route("/prefs", methods=["GET", "POST"])
def prefs():
    if request.method == "POST":
        raw = request.form.get("data", "")
        resp = make_response("đã lưu tuỳ chọn")
        resp.set_cookie("prefs", raw, httponly=True)
        return resp
    raw = request.cookies.get("prefs")
    if not raw:
        return "chưa có tuỳ chọn"
    # [Lỗi 5 — Expert] Cookie 'prefs' là base64 của pickle, được loads không kiểm tra.
    try:
        obj = pickle.loads(base64.b64decode(raw))
    except Exception as exc:
        return f"lỗi đọc tuỳ chọn: {exc}", 400
    return f"tuỳ chọn: {obj}"


if __name__ == "__main__":
    # Đảm bảo flag SSRF & pickle nằm trong môi trường (không hard-code trong code trả về)
    app.run(host="0.0.0.0", port=8080)
