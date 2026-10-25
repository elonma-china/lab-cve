"""demo-ledger-003 — ứng dụng sổ cái/ví "Ledger" với 5 lỗi cố ý (business logic + injection).

Chỉ dùng trong lab local. Không phải CVE. Xem README.md để biết phân cấp độ khó.
"""
import sqlite3
import threading
import time

import yaml
from flask import Flask, g, jsonify, request

app = Flask(__name__)
DB_PATH = "/tmp/ledger.db"
API_TOKEN = "ldg_live_7f3a9c21d0e84b56"  # sẽ lộ qua /debug/config (lỗi 1)
FLAG_CONFIG = "FLAG{DEBUG_ENDPOINT_LEAK}"
FLAG_MASS = "FLAG{MASS_ASSIGNMENT_ADMIN}"
FLAG_SECOND = "FLAG{SECOND_ORDER_SQLI_REPORT}"
FLAG_RACE = "FLAG{RACE_COUPON_DOUBLE_SPEND}"
FLAG_YAML = "FLAG{YAML_UNSAFE_LOAD_RCE}"

_lock_free_balance_lock = threading.Lock()  # khoá này KHÔNG được dùng ở chỗ kiểm tra coupon (lỗi 4)


def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(_exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()


def seed():
    import os

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, role TEXT DEFAULT 'user',
                            display TEXT, balance INTEGER DEFAULT 0);
        CREATE TABLE coupons (code TEXT PRIMARY KEY, value INTEGER, redeemed INTEGER DEFAULT 0);
        CREATE TABLE reports (id INTEGER PRIMARY KEY, body TEXT);
        """
    )
    db.executemany(
        "INSERT INTO users (username, role, display, balance) VALUES (?,?,?,?)",
        [("alice", "user", "Alice", 120), ("bob", "user", "Bob", 40), ("ops", "admin", "Ops Team", 9999)],
    )
    db.execute("INSERT INTO coupons (code, value) VALUES ('WELCOME50', 50)")
    db.commit()
    db.close()


@app.get("/")
def index():
    return jsonify(
        app="Ledger",
        endpoints=[
            "POST /register {username, display}",
            "GET /user/<username>",
            "POST /profile/update {username, display, ...}",
            "POST /coupon/redeem {username, code}",
            "POST /reports {username}  -> GET /reports/<id>",
            "POST /import (YAML)",
            "GET /debug/config",
        ],
    )


@app.post("/register")
def register():
    data = request.get_json(force=True)
    db = get_db()
    # Lỗi 3 (2nd-order) tiềm ẩn: username được lưu nguyên văn, không kiểm soát ký tự.
    db.execute(
        "INSERT INTO users (username, display) VALUES (?, ?)",
        (data.get("username", ""), data.get("display", "")),
    )
    db.commit()
    return jsonify(ok=True)


@app.get("/user/<username>")
def user(username):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify(error="không có"), 404)


@app.post("/profile/update")
def profile_update():
    data = request.get_json(force=True)
    db = get_db()
    # Lỗi 2 — Mass assignment: lặp qua MỌI trường client gửi lên, kể cả 'role'/'balance'.
    username = data.pop("username", None)
    if not username:
        return jsonify(error="thiếu username"), 400
    sets = ", ".join(f"{k}=?" for k in data)
    if sets:
        db.execute(f"UPDATE users SET {sets} WHERE username=?", (*data.values(), username))
        db.commit()
    row = db.execute("SELECT role, balance FROM users WHERE username=?", (username,)).fetchone()
    flag = FLAG_MASS if row and row["role"] == "admin" else None
    return jsonify(updated=True, role=row["role"] if row else None, flag=flag)


@app.post("/coupon/redeem")
def coupon_redeem():
    data = request.get_json(force=True)
    username, code = data.get("username"), data.get("code")
    db = get_db()
    # Lỗi 4 — Race condition (TOCTOU): kiểm tra 'redeemed' rồi cập nhật ở 2 bước riêng,
    # không có transaction/khoá; sleep nhỏ để làm cửa sổ race rộng hơn.
    row = db.execute("SELECT value, redeemed FROM coupons WHERE code=?", (code,)).fetchone()
    if row is None:
        return jsonify(error="mã không tồn tại"), 404
    if row["redeemed"]:
        return jsonify(error="mã đã dùng"), 409
    time.sleep(0.2)
    db.execute("UPDATE coupons SET redeemed=1 WHERE code=?", (code,))
    db.execute("UPDATE users SET balance = balance + ? WHERE username=?", (row["value"], username))
    db.commit()
    bal = db.execute("SELECT balance FROM users WHERE username=?", (username,)).fetchone()
    flag = FLAG_RACE if bal and bal["balance"] >= 200 else None
    return jsonify(ok=True, balance=bal["balance"] if bal else None, flag=flag)


@app.post("/reports")
def create_report():
    data = request.get_json(force=True)
    db = get_db()
    # Lưu username thẳng vào DB (an toàn ở bước này nhờ tham số hoá)...
    db.execute("INSERT INTO reports (body) VALUES (?)", (data.get("username", ""),))
    db.commit()
    rid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return jsonify(report_id=rid)


@app.get("/reports/<int:rid>")
def view_report(rid):
    db = get_db()
    row = db.execute("SELECT body FROM reports WHERE id=?", (rid,)).fetchone()
    if row is None:
        return jsonify(error="không có"), 404
    username = row["body"]
    # Lỗi 3 — Second-order SQLi: ...nhưng bước dựng báo cáo nối lại chuỗi đó vào SQL.
    try:
        rows = db.execute(
            f"SELECT username, balance, role FROM users WHERE username='{username}'"
        ).fetchall()
    except sqlite3.Error as exc:
        return jsonify(error=str(exc)), 500
    flag = FLAG_SECOND if any(r["role"] == "admin" for r in rows) else None
    return jsonify(report=[dict(r) for r in rows], flag=flag)


@app.post("/import")
def import_config():
    # Lỗi 5 — Expert: yaml.load với Loader không an toàn -> thực thi object Python tuỳ ý.
    raw = request.get_data(as_text=True)
    try:
        obj = yaml.load(raw, Loader=yaml.Loader)
    except Exception as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(imported=str(type(obj)), result=str(obj), flag=FLAG_YAML if "FLAG" in str(obj) else None)


@app.get("/debug/config")
def debug_config():
    # Lỗi 1 — Newbie: endpoint debug để quên bật auth, lộ token nội bộ.
    return jsonify(env="production", api_token=API_TOKEN, flag=FLAG_CONFIG)


if __name__ == "__main__":
    seed()
    app.run(host="0.0.0.0", port=8080, threaded=True)
