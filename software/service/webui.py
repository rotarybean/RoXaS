#!/usr/bin/env python3
"""webui.py - RoXaS owner console: edit catalog parts, custom replies, run maintenance commands.

Standard library only. Single owner, password protected (cookie session), meant for the home/shop LAN.
    ~/bench/venv/bin/python ~/roxas/webui.py --password-file ~/roxas/web.pass
then open  http://roxas-cm5.local:8080  (or the Pi's IP).
Hand edits go to user.sqlite and are re-applied onto roxas.sqlite (see userdata.py).
"""
import argparse, json, os, secrets, shutil, sqlite3, subprocess, sys, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import userdata as U                                  # noqa: E402

A = None            # parsed args
SESSIONS = set()
LOCK = threading.Lock()     # one writer at a time
FAILS = {"n": 0, "t": 0.0}


def user_db():
    return U.open_user(A.user_db)


def console(cmd):
    """Allow-listed maintenance commands. Nothing here runs arbitrary shell text."""
    c = cmd.strip().split()
    if not c:
        return "type 'help'"
    name, args = c[0].lower(), c[1:]
    u = user_db()
    if name == "help":
        return ("help | stats | reapply | export parts | export replies | backup | "
                "match <question> | service status | service restart | llm restart | uptime | disk")
    if name == "stats":
        r = sqlite3.connect(A.db)
        n, v = r.execute("SELECT COUNT(*), SUM(verified) FROM parts").fetchone()
        return (f"parts {n} ({v} verified) | edited rows {u.execute('SELECT COUNT(*) FROM part_state').fetchone()[0]} | "
                f"added rows {u.execute('SELECT COUNT(*) FROM part_added').fetchone()[0]} | "
                f"custom replies {u.execute('SELECT COUNT(*) FROM replies').fetchone()[0]}")
    if name == "reapply":
        return f"re-applied hand edits ({U.apply_edits(A.db, u)} row changes)"
    if name == "export" and args[:1] == ["parts"]:
        return json.dumps(U.export_parts(u), indent=1)
    if name == "export" and args[:1] == ["replies"]:
        return json.dumps(U.list_replies(u), indent=1)
    if name == "backup":
        os.makedirs(A.backup_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for f in (A.user_db, A.db):
            shutil.copy(f, os.path.join(A.backup_dir, f"{os.path.basename(f)}.{stamp}"))
        return f"backed up to {A.backup_dir} ({stamp})"
    if name == "match":
        m = U.match_reply(u, " ".join(args))
        return repr(m) if m else "no custom reply matches"
    if name == "uptime":
        return subprocess.run(["uptime", "-p"], capture_output=True, text=True).stdout.strip()
    if name == "disk":
        return subprocess.run(["df", "-h", "/"], capture_output=True, text=True).stdout.strip()
    if name in ("service", "llm") and args[:1] in (["status"], ["restart"]):
        unit = "roxas.service" if name == "service" else "roxas-llm.service"
        p = subprocess.run(["systemctl", "--user", args[0], unit], capture_output=True, text=True, timeout=30)
        return (p.stdout + p.stderr).strip() or f"{unit}: {args[0]} ok"
    return f"unknown command '{cmd}' (try 'help')"


class H(BaseHTTPRequestHandler):
    server_version = "RoXaSWeb"

    def log_message(self, *a):
        pass

    # ---- helpers
    def _send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _authed(self):
        ck = self.headers.get("Cookie", "")
        return any(p.strip() == f"rx={t}" for t in SESSIONS for p in ck.split(";"))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    # ---- routes
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, open(os.path.join(HERE, "web", "index.html"), "rb").read(), "text/html; charset=utf-8")
        if not self._authed():
            return self._send(401, {"error": "login"})
        if u.path.startswith("/img/"):
            f = os.path.join(A.img_dir, os.path.basename(u.path))
            if os.path.isfile(f):
                return self._send(200, open(f, "rb").read(), "image/jpeg")
            return self._send(404, {"error": "no image"})
        q = parse_qs(u.query)
        usr = user_db()
        if u.path == "/api/pages":
            return self._send(200, U.page_summary(A.db, usr))
        if u.path == "/api/page":
            return self._send(200, U.page_rows(A.db, usr, int(q["n"][0])))
        if u.path == "/api/replies":
            return self._send(200, U.list_replies(usr))
        if u.path == "/api/export":
            return self._send(200, U.export_parts(usr))
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        d = self._body()
        if u.path == "/api/login":
            if time.time() - FAILS["t"] < min(FAILS["n"], 8):      # slow down guessing
                return self._send(429, {"error": "wait a few seconds"})
            if secrets.compare_digest(d.get("password", ""), A.password):
                t = secrets.token_hex(24); SESSIONS.add(t); FAILS["n"] = 0
                return self._send(200, {"ok": True}, extra={"Set-Cookie": f"rx={t}; HttpOnly; SameSite=Strict; Path=/"})
            FAILS["n"] += 1; FAILS["t"] = time.time()
            return self._send(403, {"error": "wrong password"})
        if not self._authed():
            return self._send(401, {"error": "login"})
        with LOCK:
            usr = user_db()
            try:
                if u.path == "/api/part":
                    U.set_part(A.db, usr, int(d["page"]), d["pn_raw"], d["st"], d.get("pn", ""), d.get("desc", ""), d.get("qty", ""))
                    return self._send(200, {"ok": True})
                if u.path == "/api/part/undo":
                    U.undo_part(A.db, usr, int(d["page"]), d["pn_raw"])
                    return self._send(200, {"ok": True})
                if u.path == "/api/part/add":
                    return self._send(200, {"ok": True, "id": U.add_part(A.db, usr, int(d["page"]), d["pn"], d.get("desc", ""), d.get("qty", "1"))})
                if u.path == "/api/part/del_added":
                    U.del_added(A.db, usr, int(d["id"]))
                    return self._send(200, {"ok": True})
                if u.path == "/api/reply":
                    return self._send(200, {"ok": True, "id": U.save_reply(usr, d.get("id"), d["prompts"], d["replies"], d.get("mode", "contains"), d.get("action", ""), d.get("enabled", 1))})
                if u.path == "/api/reply/del":
                    U.del_reply(usr, int(d["id"]))
                    return self._send(200, {"ok": True})
                if u.path == "/api/reply/test":
                    m = U.match_reply(usr, d["q"])
                    return self._send(200, {"match": m})
                if u.path == "/api/console":
                    return self._send(200, {"out": console(d["cmd"])})
            except Exception as e:                      # surface the error in the UI instead of a dead page
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        return self._send(404, {"error": "not found"})


def main():
    global A
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "roxas.sqlite"))
    ap.add_argument("--user-db", default=os.path.join(HERE, "user.sqlite"))
    ap.add_argument("--img-dir", default=os.path.join(HERE, "img"))
    ap.add_argument("--backup-dir", default=os.path.join(HERE, "backups"))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--password-file", default=os.path.join(HERE, "web.pass"))
    A = ap.parse_args()
    if not os.path.exists(A.password_file):
        sys.exit(f"Create {A.password_file} containing the password (one line), then run again.")
    A.password = open(A.password_file).read().strip()
    if len(A.password) < 8:
        sys.exit("Password must be at least 8 characters.")
    U.open_user(A.user_db).close()
    U.apply_edits(A.db, U.open_user(A.user_db))
    print(f"RoXaS web console on http://{A.host}:{A.port}  (db {A.db})", file=sys.stderr)
    ThreadingHTTPServer((A.host, A.port), H).serve_forever()


if __name__ == "__main__":
    main()
