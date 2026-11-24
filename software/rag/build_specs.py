# build_specs.py - load specs.json into the sqlite `specs` table, VERIFYING every check string against the docs page text.
# usage: python3 build_specs.py <roxas.sqlite> [specs.json]     Exit 1 if any check string is missing from its source pages.
import sys, json, re, sqlite3, os
db = sqlite3.connect(sys.argv[1])
path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "specs.json")
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[−–—‐‑]", "-", s))
specs, bad = json.load(open(path, encoding="utf-8")), 0
for s in specs:
    txt = ""
    for f, p in s["src"]:
        r = db.execute("SELECT text FROM docs WHERE source_file LIKE ? AND page=?", (f + "%", p)).fetchone()
        if not r: print(f"MISSING PAGE {s['id']}: {f} p{p}"); bad += 1; continue
        txt += " " + norm(r[0])
    for c in s["check"]:
        if norm(c) not in txt: print(f"NOT FOUND {s['id']}: {c!r}"); bad += 1
    for n in re.findall(r"\d[\d.]*", s["text"]):   # every number in the spoken text must appear somewhere in the source pages
        if n.rstrip(".") not in txt: print(f"TEXT NUMBER NOT IN SOURCE {s['id']}: {n}"); bad += 1
db.execute("DROP TABLE IF EXISTS specs")
db.execute("CREATE TABLE specs(id TEXT PRIMARY KEY, name TEXT, keys TEXT, nots TEXT, pri INT, text TEXT, src TEXT)")
for s in specs:
    db.execute("INSERT INTO specs VALUES(?,?,?,?,?,?,?)", (s["id"], s["name"], json.dumps(s["keys"]), json.dumps(s["not"]), s["pri"], s["text"], json.dumps(s["src"])))
db.commit()
print(f"{len(specs)} specs loaded, {bad} problems")
sys.exit(1 if bad else 0)
