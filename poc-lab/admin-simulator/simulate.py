"""
Admin browser simulator — runs in sidecar container, browses admin pages on interval.
Used for XSS-triggered labs (comment2shell, click2shell).

Env vars:
  TARGET_URL     base URL of target app (e.g. http://target:80)
  ADMIN_URL      URL admin browses (e.g. http://target/wp-admin/edit-comments.php)
  ADMIN_USER     admin username (default: admin)
  ADMIN_PASS     admin password (default: admin)
  BROWSE_INTERVAL  seconds between each browse (default: 15)
  LOGIN_PATH     login form path (default: /wp-login.php)
  STARTUP_DELAY  seconds to wait before first login attempt (default: 20)
"""
import os, time, urllib.request, urllib.parse, urllib.error, http.cookiejar, sys

TARGET = os.environ.get("TARGET_URL", "http://localhost")
ADMIN_URL = os.environ.get("ADMIN_URL", TARGET + "/wp-admin/edit-comments.php")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin")
INTERVAL = int(os.environ.get("BROWSE_INTERVAL", "15"))
LOGIN_PATH = os.environ.get("LOGIN_PATH", "/wp-login.php")
STARTUP_DELAY = int(os.environ.get("STARTUP_DELAY", "20"))


def make_browser():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (Admin Browser Simulator)")]
    return opener


def wp_login(opener):
    login_url = TARGET.rstrip("/") + LOGIN_PATH
    data = urllib.parse.urlencode({
        "log": ADMIN_USER, "pwd": ADMIN_PASS,
        "wp-submit": "Log In", "redirect_to": "/wp-admin/",
        "testcookie": "1",
    }).encode()
    try:
        resp = opener.open(login_url, data, timeout=10)
        body = resp.read(2048).decode(errors="replace")
        ok = resp.status == 200 and ("Dashboard" in body or "wp-admin" in resp.geturl())
        print(f"[sim] login → {resp.status} url={resp.geturl()} ok={ok}", flush=True)
        return ok
    except Exception as e:
        print(f"[sim] login error: {e}", flush=True)
        return False


def browse(opener, url):
    try:
        resp = opener.open(url, timeout=10)
        body = resp.read(4096).decode(errors="replace")
        print(f"[sim] browse {url} → {resp.status} ({len(body)} bytes)", flush=True)
        return body
    except Exception as e:
        print(f"[sim] browse error {url}: {e}", flush=True)
        return ""


print(f"[sim] Starting. TARGET={TARGET} ADMIN_URL={ADMIN_URL} interval={INTERVAL}s", flush=True)
print(f"[sim] Waiting {STARTUP_DELAY}s for app startup...", flush=True)
time.sleep(STARTUP_DELAY)

opener = make_browser()
logged_in = False

while True:
    if not logged_in:
        logged_in = wp_login(opener)
        if not logged_in:
            print("[sim] login failed, retry in 10s", flush=True)
            time.sleep(10)
            continue
        print("[sim] logged in as admin", flush=True)
    browse(opener, ADMIN_URL)
    time.sleep(INTERVAL)
