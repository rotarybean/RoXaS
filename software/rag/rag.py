import collections
# rag.py (v2) - retrieval layer for RoXaS. Exact lookups first (DTC codes), FTS5 + bm25 for the rest.
# The model never invents facts: it only sees what retrieve() returns, each item with its source file + page.
import re, sqlite3

STOP = set("""a an and are as at be by can do does for from how i in is it its me my of on or the to what which
when where why with you your should would could need get give tell about this that these those there into out up
car rx8 rx-8 mazda please goes go take takes use uses used long kind type reader shows show remember forget know find looking wondering hey roxas thanks sure cant couldnt dont anyone file listed database stock have metric imperial units""".split())
CODE = re.compile(r"\b([PUBC][0-9]{4})\b", re.I)

# Manual wording differs from how people ask. General domain synonyms (not tuned to any one question).
SYN = {
    "start": ["initial"], "open": ["opening"], "opens": ["opening"],
    "much": ["capacity", "quantity"], "many": ["quantity"], "amount": ["capacity", "quantity"],
    "change": ["replacement", "replace"], "replace": ["replacement", "removal", "installation"],
    "tighten": ["tightening", "torque"], "tight": ["tightening", "torque"], "torque": ["tightening"],
    "gap": ["clearance"], "spec": ["specification"], "specs": ["specification"], "size": ["specification"],
    "remove": ["removal"], "install": ["installation"], "bleed": ["air"], "gear": ["oil"],
    "check": ["inspection"], "test": ["inspection"], "fix": ["repair"], "temp": ["temperature"],
    "weight": ["mass"], "pressure": ["psi", "kpa"],
}
# Parts-catalog abbreviations (the catalog prints CYL., ASSY, FRT, ...)
PSYN = {
    "cylinder": ["cyl"], "assembly": ["assy"], "front": ["frt", "fr"], "rear": ["rr"], "right": ["rh"], "left": ["lh"],
    "sensor": ["sens"], "bracket": ["brkt"], "number": [], "transmission": ["trans"], "temperature": ["temp"], "shift": ["change"], "standard": ["std"], "headlight": ["head lamp"], "headlamp": ["head lamp"], "passenger": ["pass"], "reserve": ["sub"],
}

def terms(q):
    return [w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) > 2 and w not in STOP]

def group(w, table):
    alts = [w] + table.get(w, [])
    return "(" + " OR ".join(f'"{a}"' if len(a) > 3 else f'"{a}"*' if table is PSYN else f'"{a}"' for a in alts) + ")"

def fts_query(ws, mode, table):
    gs = [group(w, table) for w in ws]
    return (" AND " if mode == "and" else " OR ").join(gs)

PNRE = re.compile(r"\b[A-Z0-9]{4}-\d{2}-[0-9A-Z]{3,4}\b|\b\d{5}-\d{4}\b")

def retrieve(db, q, k=5, emb=None, emb_w=0.5):
    out = {"dtc": [], "parts": [], "docs": [], "route": []}
    codes = [c.upper() for c in CODE.findall(q)]
    for c in codes:
        r = db.execute("SELECT code,title,monitor,causes,source_file,page,kind,note FROM dtc WHERE code=?", (c,)).fetchone()
        if r:
            out["dtc"].append(dict(code=r[0], title=r[1], monitor=r[2], causes=r[3], source=r[4], page=r[5], kind=r[6], note=r[7]))
    if codes:
        out["route"].append("dtc")
    # a part number typed in the question: look it up exactly (OCR-confusion tolerant), do not text-search it
    for m in PNRE.finditer(q.upper().replace("O", "0").replace("I", "1")):
        pn = m.group(0)
        got = db.execute("SELECT part_number,qty,desc_raw,restrictions,confidence,page,tags,verified FROM parts WHERE "
                         "replace(replace(part_number,'O','0'),'I','1')=? OR replace(replace(pn_raw,'O','0'),'I','1')=? "
                         "ORDER BY verified DESC, page LIMIT 5", (pn, pn)).fetchall()
        for r in got:
            out["parts"].append(dict(part_number=r[0], qty=r[1], desc=r[2], restrictions=r[3], confidence=r[4], page=r[5], tags=r[6], verified=r[7]))
        if got and "parts" not in out["route"]:
            out["route"].append("parts")
        if not got:
            out.setdefault("pn_missing", []).append(pn)
    if out["parts"] or out.get("pn_missing"):
        out["unmatched"] = []
        return out
    ws = terms(q)
    wants_part = bool(re.search(r"part\s*(number|no|#)|\bpn\b|order|buy", q, re.I))
    if wants_part and ws:
        ws2 = [w for w in ws if w not in ("part", "number", "order", "buy")]
        rows, seen = [], set()
        for mode in ("and", "or"):
            got = db.execute(
                "SELECT p.part_number,p.qty,p.desc_raw,p.restrictions,p.confidence,p.page,p.tags,p.verified FROM parts_fts "
                "JOIN parts p ON p.id=parts_fts.rowid WHERE parts_fts MATCH ? AND p.conflicts_fe06=0 AND length(trim(p.desc_raw))>2 "
                "ORDER BY bm25(parts_fts,4.0,1.0,1.0) LIMIT ?", (fts_query(ws2, mode, PSYN), k * 3)).fetchall()
            for r in got:
                if r[0] not in seen and re.search(r"[A-Za-z]{3}", r[2] or ""):   # skip rows whose description is OCR junk
                    seen.add(r[0]); rows.append(r)
            if len(rows) >= k:
                break
        qset = {w.lower() for w in ws2} | {x for w in ws2 for a in PSYN.get(w, []) for x in a.split()}
        def extras(r):   # description words the question did not ask for: "THERMOSTAT" beats "COVER, THERMOSTAT" for "thermostat"
            dw = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", re.sub(r"^[^A-Za-z0-9(]+", "", r[2] or "").split("|")[0])]
            return sum(w not in qset and w.rstrip("s") not in qset for w in dw)
        def cover(r):     # query words present in description + restrictions (a "trailing side" plug has those words in the restriction line)
            tw = {w.lower().rstrip("s") for w in re.findall(r"[A-Za-z]{2,}", re.sub(r"^[^A-Za-z0-9(]+", "", (r[2] or "") + " " + (r[3] or "")))}
            return sum(w.rstrip("s") in tw or any(a.rstrip("s") in tw for a in PSYN.get(w, [])) for w in ws2)
        rows = sorted(rows, key=lambda r: (-cover(r), extras(r), -(r[7] or 0)))               # stable: bm25 order is kept among ties
        if rows:                                      # question words the best row's description does not cover (e.g. "clutch" for a plain bleeder screw)
            top = {w.lower().rstrip("s") for w in re.findall(r"[A-Za-z]{2,}", re.sub(r"^[^A-Za-z0-9(]+", "", (rows[0][2] or "") + " " + (rows[0][3] or "")))}
            out["parts_missing"] = [w for w in ws2 if w.rstrip("s") not in top and not any(a.rstrip("s") in top for a in PSYN.get(w, []))
                                    and not (len(w) > 4 and any(t.startswith(w[:4]) for t in top))]
        out["parts"] = [dict(part_number=r[0], qty=r[1], desc=r[2], restrictions=r[3], confidence=r[4], page=r[5], tags=r[6], verified=r[7])
                        for r in rows]
        out["route"].append("parts")
    if not codes and ws:
        rows, seen = [], set()
        # 1) adjacent-word phrases ("idle speed", "air pressure") are the strongest signal: rank them first
        for a_, b_ in zip(ws, ws[1:]):
            df = db.execute("SELECT count(*) FROM docs_fts WHERE docs_fts MATCH ?", (f'"{a_} {b_}"',)).fetchone()[0]
            if df == 0 or df > 40:          # generic compounds ("manual transmission") only add noise
                continue
            got = db.execute(
                "SELECT d.source_file,d.page,d.heading,d.text FROM docs_fts JOIN docs d ON d.id=docs_fts.rowid "
                "WHERE docs_fts MATCH ? ORDER BY bm25(docs_fts,6.0,1.0) LIMIT 2", (f'"{a_} {b_}"',)).fetchall()
            for r in got:
                if (r[0], r[1]) not in seen and len(rows) < 4:
                    seen.add((r[0], r[1])); rows.append(r)
        # 2) all terms (with synonyms), then 3) any term
        for mode in ("and", "or"):
            got = db.execute(
                "SELECT d.source_file,d.page,d.heading,d.text FROM docs_fts JOIN docs d ON d.id=docs_fts.rowid "
                "WHERE docs_fts MATCH ? ORDER BY bm25(docs_fts,6.0,1.0) LIMIT ?",
                (fts_query(ws, mode, SYN), k * 2)).fetchall()
            for r in got:
                if (r[0], r[1]) not in seen:
                    seen.add((r[0], r[1])); rows.append(r)
            if len(rows) >= k:
                break
        if emb is not None:                           # fuse dense hits with the keyword ranking (reciprocal rank, k=60)
            score = collections.defaultdict(float); byp = {}
            for i, r in enumerate(rows):
                score[(r[0], r[1])] += 1.0 / (60 + i); byp[(r[0], r[1])] = r
            seen_p = set()
            for j, (did, sim) in enumerate(emb.search(q, 8)):
                d = db.execute("SELECT source_file,page,heading,text FROM docs WHERE id=?", (did,)).fetchone()
                if d is None or (d[0], d[1]) in seen_p: continue
                seen_p.add((d[0], d[1])); score[(d[0], d[1])] += emb_w / (60 + j); byp.setdefault((d[0], d[1]), d)
            rows = [byp[k_] for k_, _ in sorted(score.items(), key=lambda kv: -kv[1])]
        out["docs"] = [dict(source=r[0], page=r[1], heading=r[2], text=r[3]) for r in rows[:max(k, 8)]]
        out["route"].append("docs")
    # terms that occur nowhere in the manuals/catalog: a strong "not covered" signal for the model
    out["unmatched"] = []
    for w in ws:
        n = db.execute("SELECT count(*) FROM docs_fts WHERE docs_fts MATCH ?", (f'"{w}"',)).fetchone()[0]
        if n == 0:
            n = db.execute("SELECT count(*) FROM parts_fts WHERE parts_fts MATCH ?", (f'"{w}"',)).fetchone()[0]
        if n == 0:
            out["unmatched"].append(w)
    out["terms"] = sorted({t for w in ws for t in [w] + SYN.get(w, [])})
    out["codes_missing"] = [c for c in codes if c not in {d["code"] for d in out["dtc"]}]
    return out

def best_window(text, ts, width=520):
    """Return the width-char slice of text where the most distinct query terms occur (not just the page start)."""
    low = text.lower()
    starts = [m.start() for t in ts for m in re.finditer(re.escape(t), low)]
    if not starts:
        return text[:width]
    best_score, best_start = -1, 0
    for s in starts:
        st = max(0, s - 120)
        win = low[st:st + width]
        score = sum(1 for t in ts if t in win)
        if score > best_score:
            best_score, best_start = score, st
    return ("…" if best_start else "") + text[best_start:best_start + width]

def context_for_model(res, max_chars=2800):
    """Compact text block handed to the LLM. 'NOT FOUND' lines tell it to refuse instead of guessing."""
    parts = []
    for d in res["dtc"]:
        parts.append(f"[DTC {d['code']}] {d['title']}. Monitor: {d['monitor'] or 'n/a'}. Causes: {d['causes']}. "
                     f"({d['source']} p{d['page']}) {d['note'] or ''}")
    for p in res["parts"][:5]:
        parts.append(f"[PART] {p['part_number']} - {p['desc']} qty {p['qty']} (catalog p{p['page']}, OCR confidence {p['confidence']})")
    for d in res["docs"][:4]:
        parts.append(f"[MANUAL {d['source']} p{d['page']} - {d['heading']}]\n{best_window(d['text'], res.get('terms', []))}")
    if res.get("codes_missing"):
        parts.append("NOT FOUND: DTC " + ", ".join(res["codes_missing"]) + " is not in the manuals.")
    if res.get("unmatched"):
        parts.append("NOT FOUND IN MANUALS: " + ", ".join(res["unmatched"]))
    return "\n\n".join(parts)[:max_chars]
