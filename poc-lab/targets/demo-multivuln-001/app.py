"""Target demo nhiều lỗ hổng: 5 lỗi cố ý cài trong 1 app "VulnNotes" tối giản.

Dùng để luyện tập pentest thủ công (KHÔNG phải CVE thật, KHÔNG wire vào harness.py).
Mỗi lỗi có 1 flag dạng FLAG{...} để tự kiểm chứng đã khai thác thành công.
Xem README.md trong thư mục này để biết danh sách lỗi + cách chạy.
Xem SOLUTIONS.md nếu bị kẹt (không đọc trước khi tự thử).
"""
import os
import sqlite3
import subprocess

from flask import Flask, g, redirect, request, session, url_for

app = Flask(__name__)
# Cố ý: secret key cứng/dễ đoán (bonus issue, không tính vào 5 lỗi chính)
app.secret_key = "dev-insecure-secret-key"

DB_PATH = "/tmp/vulnnotes.db"
FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files")

SESSION_TOKEN_FLAG = "FLAG{STORED_XSS_COOKIE_THEFT}"


def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
    return db


@app.teardown_appcontext
def close_db(_exc):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()


def seed_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            content TEXT
        );
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            author TEXT,
            body TEXT
        );
        """
    )
    db.execute(
        "INSERT INTO users (id, username, password, is_admin) VALUES (1, 'admin', ?, 1)",
        ("Adm1n_R4nd0m_PW_2026!",),
    )
    db.execute(
        "INSERT INTO users (id, username, password, is_admin) VALUES (2, 'alice', 'alicepw123', 0)"
    )
    db.execute(
        "INSERT INTO users (id, username, password, is_admin) VALUES (3, 'bob', 'bobpw456', 0)"
    )
    db.execute(
        "INSERT INTO notes (id, user_id, title, content) VALUES "
        "(1, 1, 'Admin TODO', 'Rotate creds. Root flag: FLAG{SQLI_LOGIN_BYPASS}')"
    )
    db.execute(
        "INSERT INTO notes (id, user_id, title, content) VALUES "
        "(2, 2, 'Alice private note', 'My secret: FLAG{IDOR_PRIVATE_NOTE}')"
    )
    db.execute(
        "INSERT INTO notes (id, user_id, title, content) VALUES "
        "(3, 3, 'Bob grocery list', 'milk, eggs, bread')"
    )
    db.execute(
        "INSERT INTO comments (author, body) VALUES ('system', 'Welcome to VulnNotes guestbook!')"
    )
    db.commit()
    db.close()


PAGE = """<!doctype html><html><head><title>{title}</title></head>
<body style="font-family:sans-serif;max-width:700px;margin:40px auto">
<h2><a href="/">VulnNotes</a> / {title}</h2>
{body}
</body></html>"""


@app.get("/")
def home():
    user = session.get("username")
    nav = f"Đăng nhập: <b>{user}</b> | <a href='/logout'>logout</a>" if user else "<a href='/login'>login</a>"
    body = f"""
    {nav}
    <ul>
      <li><a href="/dashboard">Dashboard / notes của tôi</a></li>
      <li><a href="/ping">Diagnostics (ping host)</a></li>
      <li><a href="/download?file=welcome.txt">Tải brochure</a></li>
      <li><a href="/comments">Guestbook (bình luận công khai)</a></li>
    </ul>
    """
    return PAGE.format(title="Home", body=body)


@app.get("/login")
def login_form():
    body = """
    <form method="post" action="/login">
      Username: <input name="username"><br>
      Password: <input name="password" type="password"><br>
      <button type="submit">Login</button>
    </form>
    <p>Tài khoản demo: <code>bob</code> / <code>bobpw456</code></p>
    """
    return PAGE.format(title="Login", body=body)


@app.post("/login")
def login_submit():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    db = get_db()
    # Lỗ hổng 1: SQL injection — nối chuỗi thẳng vào câu query, không tham số hoá.
    query = (
        "SELECT id, username, is_admin FROM users "
        f"WHERE username='{username}' AND password='{password}'"
    )
    try:
        row = db.execute(query).fetchone()
    except sqlite3.Error as exc:
        return PAGE.format(title="Login", body=f"<pre>SQL error: {exc}</pre>"), 400
    if row is None:
        return PAGE.format(title="Login", body="<p>Sai username/password.</p>"), 401
    session["user_id"], session["username"], session["is_admin"] = row
    resp = redirect(url_for("dashboard"))
    # Cookie session riêng, không HttpOnly -> có thể đọc được bằng JS (phục vụ bài XSS).
    resp.set_cookie("session_token", SESSION_TOKEN_FLAG, httponly=False)
    return resp


@app.get("/logout")
def logout():
    session.clear()
    resp = redirect(url_for("home"))
    resp.delete_cookie("session_token")
    return resp


@app.get("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login_form"))
    db = get_db()
    rows = db.execute(
        "SELECT id, title FROM notes WHERE user_id=?", (session["user_id"],)
    ).fetchall()
    items = "".join(f"<li><a href='/notes/{nid}'>{title}</a> (id={nid})</li>" for nid, title in rows)
    body = f"""
    <p>Xin chào {session['username']} (is_admin={session['is_admin']})</p>
    <p>Notes của bạn:</p>
    <ul>{items}</ul>
    <p>Xem note bất kỳ qua <code>/notes/&lt;id&gt;</code>.</p>
    """
    return PAGE.format(title="Dashboard", body=body)


@app.get("/notes/<int:note_id>")
def view_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login_form"))
    db = get_db()
    # Lỗ hổng 2: IDOR — query có tham số hoá (không SQLi) nhưng KHÔNG kiểm tra
    # note.user_id có khớp session['user_id'] hay không -> xem được note người khác.
    row = db.execute(
        "SELECT title, content FROM notes WHERE id=?", (note_id,)
    ).fetchone()
    if row is None:
        return PAGE.format(title="Note", body="<p>Không tìm thấy.</p>"), 404
    title, content = row
    return PAGE.format(title=f"Note #{note_id}", body=f"<h3>{title}</h3><p>{content}</p>")


@app.get("/ping")
def ping_form():
    body = """
    <form method="get" action="/ping/run">
      Host: <input name="host" value="127.0.0.1"><br>
      <button type="submit">Ping</button>
    </form>
    """
    return PAGE.format(title="Diagnostics", body=body)


@app.get("/ping/run")
def ping_run():
    host = request.args.get("host", "127.0.0.1")
    # Lỗ hổng 3: OS command injection — nối chuỗi thẳng vào shell command.
    out = subprocess.run(
        f"ping -c 1 {host}", shell=True, capture_output=True, text=True, timeout=5
    )
    return PAGE.format(title="Ping result", body=f"<pre>{out.stdout}{out.stderr}</pre>")


@app.get("/download")
def download():
    filename = request.args.get("file", "welcome.txt")
    # Lỗ hổng 4: path traversal — nối path trực tiếp, không chặn "..".
    path = os.path.join(FILES_DIR, filename)
    try:
        with open(path, "r", errors="replace") as fh:
            content = fh.read()
    except OSError as exc:
        return PAGE.format(title="Download", body=f"<pre>Error: {exc}</pre>"), 404
    return PAGE.format(title="Download", body=f"<pre>{content}</pre>")


@app.get("/comments")
def comments_list():
    db = get_db()
    rows = db.execute("SELECT author, body FROM comments ORDER BY id DESC").fetchall()
    # Lỗ hổng 5: stored XSS — render thẳng body của comment, không escape.
    items = "".join(f"<li><b>{author}</b>: {body}</li>" for author, body in rows)
    body = f"""
    <ul>{items}</ul>
    <form method="post" action="/comments">
      Tên: <input name="author"><br>
      Bình luận: <textarea name="body"></textarea><br>
      <button type="submit">Gửi</button>
    </form>
    """
    return PAGE.format(title="Guestbook", body=body)


@app.post("/comments")
def comments_add():
    author = request.form.get("author", "anon")
    text = request.form.get("body", "")
    db = get_db()
    db.execute("INSERT INTO comments (author, body) VALUES (?, ?)", (author, text))
    db.commit()
    return redirect(url_for("comments_list"))


@app.get("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    seed_db()
    app.run(host="0.0.0.0", port=8080)
