"""userdata.py - everything the owner edits by hand lives in user.sqlite, NOT in roxas.sqlite.

roxas.sqlite is rebuilt and re-deployed from the manuals whenever the pipeline changes. Hand edits are kept as a
small log in user.sqlite and re-applied on top of every fresh roxas.sqlite (apply_edits is idempotent), so a deploy
never loses work.

  part_state : one row per catalog row that was checked (ok / fixed / bad), keyed by (page, pn_raw) like verified_parts.json
  part_added : rows typed in by hand
  replies    : custom prompt -> reply table (plus an optional `action`, reserved for CAN-bus commands later)
"""
import json, re, sqlite3, time, itertools

SCHEMA = """
CREATE TABLE IF NOT EXISTS part_state(page INT, pn_raw TEXT, st TEXT, pn TEXT, descr TEXT, qty TEXT, orig TEXT, ts REAL,
  PRIMARY KEY(page, pn_raw));
CREATE TABLE IF NOT EXISTS part_added(id INTEGER PRIMARY KEY, page INT, pn TEXT, descr TEXT, qty TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS replies(id INTEGER PRIMARY KEY, prompts TEXT, replies TEXT, mode TEXT DEFAULT 'contains',
  action TEXT DEFAULT '', enabled INT DEFAULT 1, ts REAL);
"""


def open_user(path):
    db = sqlite3.connect(path, timeout=10)
    db.executescript(SCHEMA)
    return db


def norm(s):
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


# ---------------------------------------------------------------- parts
def _fts_rebuild(rag):
    rag.execute("INSERT INTO parts_fts(parts_fts) VALUES('rebuild')")


def apply_edits(rag_path, user):
    """Re-apply every hand edit onto roxas.sqlite. Safe to run any number of times."""
    rag = sqlite3.connect(rag_path, timeout=10)
    n = 0
    for page, pn_raw, st, pn, descr, qty in user.execute("SELECT page,pn_raw,st,pn,descr,qty FROM part_state"):
        if st == "bad":
            n += rag.execute("DELETE FROM parts WHERE page=? AND pn_raw=?", (page, pn_raw)).rowcount
        else:
            n += rag.execute("UPDATE parts SET part_number=?, desc_raw=COALESCE(NULLIF(?,''),desc_raw), "
                             "qty=COALESCE(NULLIF(?,''),qty), verified=1, confidence='high' WHERE page=? AND pn_raw=?",
                             (pn, descr, qty, page, pn_raw)).rowcount
    for aid, page, pn, descr, qty in user.execute("SELECT id,page,pn,descr,qty FROM part_added").fetchall():
        key = f"web{aid}"
        if rag.execute("SELECT 1 FROM parts WHERE pn_raw=?", (key,)).fetchone():
            rag.execute("UPDATE parts SET part_number=?, desc_raw=?, qty=? WHERE pn_raw=?", (pn, descr, qty, key))
            continue
        src = rag.execute("SELECT source_file, section FROM parts WHERE page=? LIMIT 1", (page,)).fetchone() or ("14Parts.pdf", "")
        rag.execute("INSERT INTO parts(source_file,page,section,callout_raw,part_number,qty,desc_raw,restrictions,tags,"
                    "conflicts_fe06,confidence,verified,pn_raw) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (src[0], page, src[1], "", pn, qty, descr, "", "[]", 0, "high", 1, key))
        n += 1
    _fts_rebuild(rag)
    rag.commit(); rag.close()
    return n


def page_rows(rag_path, user, page):
    rag = sqlite3.connect(rag_path, timeout=10)
    st = {r[0]: r[1:] for r in user.execute("SELECT pn_raw,st,pn,descr,qty,orig FROM part_state WHERE page=?", (page,))}
    rows = []
    for r in rag.execute("SELECT id,pn_raw,part_number,qty,desc_raw,restrictions,confidence,verified FROM parts WHERE page=? ORDER BY id", (page,)):
        rows.append(dict(id=r[0], pn_raw=r[1], pn=r[2], qty=r[3], desc=r[4], restr=r[5], conf=r[6], verified=r[7],
                         st=(st.get(r[1]) or [None])[0], added=str(r[1]).startswith("web")))
    # rows deleted as 'bad' no longer exist in roxas.sqlite; show them so they can be undone
    have = {r["pn_raw"] for r in rows}
    for pn_raw, (s, pn, descr, qty, orig) in st.items():
        if s == "bad" and pn_raw not in have:
            o = json.loads(orig or "{}")
            rows.append(dict(id=None, pn_raw=pn_raw, pn=o.get("part_number", ""), qty=o.get("qty", ""), desc=o.get("desc_raw", ""),
                             restr=o.get("restrictions", ""), conf=o.get("confidence", ""), verified=0, st="bad", added=False))
    rag.close()
    return rows


def set_part(rag_path, user, page, pn_raw, st, pn="", descr="", qty=""):
    rag = sqlite3.connect(rag_path, timeout=10)
    cur = user.execute("SELECT orig FROM part_state WHERE page=? AND pn_raw=?", (page, pn_raw)).fetchone()
    if cur and cur[0]:
        orig = cur[0]
    else:
        r = rag.execute("SELECT id,source_file,page,section,callout_raw,part_number,qty,desc_raw,restrictions,tags,"
                        "conflicts_fe06,confidence,verified,pn_raw FROM parts WHERE page=? AND pn_raw=?", (page, pn_raw)).fetchone()
        cols = "id source_file page section callout_raw part_number qty desc_raw restrictions tags conflicts_fe06 confidence verified pn_raw".split()
        orig = json.dumps(dict(zip(cols, r))) if r else "{}"
    rag.close()
    user.execute("INSERT OR REPLACE INTO part_state VALUES(?,?,?,?,?,?,?,?)", (page, pn_raw, st, pn.strip().upper(), descr.strip(), qty.strip(), orig, time.time()))
    user.commit()
    return apply_edits(rag_path, user)


def undo_part(rag_path, user, page, pn_raw):
    row = user.execute("SELECT orig FROM part_state WHERE page=? AND pn_raw=?", (page, pn_raw)).fetchone()
    user.execute("DELETE FROM part_state WHERE page=? AND pn_raw=?", (page, pn_raw)); user.commit()
    if not row or not row[0]:
        return 0
    o = json.loads(row[0])
    if not o:
        return 0
    rag = sqlite3.connect(rag_path, timeout=10)
    rag.execute("DELETE FROM parts WHERE page=? AND pn_raw=?", (page, pn_raw))
    rag.execute("INSERT INTO parts(id,source_file,page,section,callout_raw,part_number,qty,desc_raw,restrictions,tags,"
                "conflicts_fe06,confidence,verified,pn_raw) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(o.values()))
    _fts_rebuild(rag); rag.commit(); rag.close()
    return 1


def add_part(rag_path, user, page, pn, descr, qty):
    cur = user.execute("INSERT INTO part_added(page,pn,descr,qty,ts) VALUES(?,?,?,?,?)", (page, pn.strip().upper(), descr.strip(), qty.strip(), time.time()))
    user.commit()
    apply_edits(rag_path, user)
    return cur.lastrowid


def del_added(rag_path, user, aid):
    user.execute("DELETE FROM part_added WHERE id=?", (aid,)); user.commit()
    rag = sqlite3.connect(rag_path, timeout=10)
    rag.execute("DELETE FROM parts WHERE pn_raw=?", (f"web{aid}",)); _fts_rebuild(rag); rag.commit(); rag.close()


def page_summary(rag_path, user):
    rag = sqlite3.connect(rag_path, timeout=10)
    out = {}
    for page, n, v in rag.execute("SELECT page, COUNT(*), SUM(verified) FROM parts GROUP BY page"):
        out[page] = dict(page=page, rows=n, verified=v or 0)
    for page, n in user.execute("SELECT page, COUNT(*) FROM part_state GROUP BY page"):
        out.setdefault(page, dict(page=page, rows=0, verified=0))["edited"] = n
    rag.close()
    return sorted(out.values(), key=lambda d: d["page"])


def export_parts(user):
    """verified_parts.json-compatible dump of the hand edits (for the repo's merge/rebuild)."""
    rows = {}
    for page, pn_raw, st, pn, descr, orig in user.execute("SELECT page,pn_raw,st,pn,descr,orig FROM part_state"):
        o = json.loads(orig or "{}")
        rows[f"w{page}_{pn_raw}"] = dict(st=("ok" if st == "ok" else st), pn=pn or pn_raw, orig=pn_raw, page=page, desc=descr or o.get("desc_raw", ""))
    add = [dict(page=p, pn=pn, desc=d, qty=q) for p, pn, d, q in user.execute("SELECT page,pn,descr,qty FROM part_added")]
    return dict(rows=rows, add=add)


# ---------------------------------------------------------------- custom replies
_rot = itertools.count()


def list_replies(user):
    return [dict(id=i, prompts=p, replies=r, mode=m, action=a, enabled=e)
            for i, p, r, m, a, e in user.execute("SELECT id,prompts,replies,mode,action,enabled FROM replies ORDER BY id")]


def save_reply(user, id_, prompts, replies, mode, action, enabled):
    if id_:
        user.execute("UPDATE replies SET prompts=?,replies=?,mode=?,action=?,enabled=?,ts=? WHERE id=?", (prompts, replies, mode, action, int(enabled), time.time(), id_))
    else:
        id_ = user.execute("INSERT INTO replies(prompts,replies,mode,action,enabled,ts) VALUES(?,?,?,?,?,?)", (prompts, replies, mode, action, int(enabled), time.time())).lastrowid
    user.commit()
    return id_


def del_reply(user, id_):
    user.execute("DELETE FROM replies WHERE id=?", (id_,)); user.commit()


def match_reply(user, question):
    """-> (reply_text, action) for the best custom match, else None. 'exact' beats 'contains'; longer prompt wins."""
    q = norm(question)
    best = None
    for p, r, m, a in user.execute("SELECT prompts,replies,mode,action FROM replies WHERE enabled=1"):
        for line in (p or "").splitlines():
            n = norm(line)
            if not n:
                continue
            hit = (q == n) if m == "exact" else bool(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", q))
            if hit and (best is None or (m == "exact", len(n)) > best[0]):
                best = ((m == "exact", len(n)), r, a)
    if not best:
        return None
    variants = [x.strip() for x in (best[1] or "").splitlines() if x.strip()]
    return (variants[next(_rot) % len(variants)] if variants else ""), best[2]
