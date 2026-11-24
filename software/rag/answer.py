# answer.py - deterministic answers for part numbers and DTCs. The LLM never writes these; code composes them from matched rows.
# deterministic(question, res) -> str or None.  None = not a part/DTC question, hand off to the LLM with retrieved context.
import json, re

def _stem(w): return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w

PROC = re.compile(r"precaution|caution|warning|how (do|to|can|should)|remov|replac|install|procedure|\bsteps?\b|diagnos|troubleshoot|symptom|why", re.I)

def spec_answer(db, question):
    if PROC.search(question): return None     # procedure/diagnosis questions go to the LLM with doc context
    # best specs-table row whose key words are all in the question; longest key, then pri, wins. None if no match.
    ws = {_stem(w) for w in re.findall(r"[a-z0-9]+", question.lower())}
    best = None
    for sid, keys, nots, pri, text, src in db.execute("SELECT id,keys,nots,pri,text,src FROM specs"):
        if any(_stem(n) in ws for n in json.loads(nots)): continue
        n = max((len(k) for k in json.loads(keys) if all(_stem(w) in ws for w in k)), default=0)
        if n and (best is None or (n, pri) > best[0]): best = ((n, pri), text, json.loads(src))
    if not best: return None
    pages = sorted({(f, p) for f, p in best[2]})
    first = [(f, p) for f, p in best[2]][0]
    return f"{best[1]} (Source: {first[0]}, p{first[1]}.)"

CAUSE = re.compile(r"cause|why|diagnos|troubleshoot|fix|check|fault|wrong|reason|trigger", re.I)
CONF = {"high": "", "medium": ", medium confidence", "low": ", low confidence, not verified"}

def _list(s):
    try: return json.loads(s) if isinstance(s, str) else (s or [])
    except Exception: return []

def _desc(d):
    d = re.sub(r"^[^A-Za-z0-9(]+", "", d or "").split("|")[0]      # drop leading OCR junk ('| KNOB ...')
    out = []
    for w in d.split():
        if len(w) >= 3 and re.search(r"[a-z]", w): break      # OCR junk tail starts at the first word with lowercase letters
        out.append(w)
    return " ".join(out).strip(" ,.")

def _src(p): return re.sub(r"\.pdf$", "", p or "").strip()

def dtc_answer(d, want_causes):
    s = f"{d['code']}: {d['title']} ({_src(d['source'])}, p{d['page']})."
    if d["kind"] == "definition":
        return s + (f" {d['note']}" if d.get("note") else " Only the definition is available; troubleshooting is in the body multiplex section.")
    if d["kind"] == "shared_section":
        s += f" {d['note']}" if d.get("note") else ""
    cs = _list(d.get("causes"))
    if want_causes and cs:
        s += " Possible causes: " + "; ".join(cs[:4]) + "."
    return s

SOFT = {"windshield", "side", "car", "vehicle"}     # words a catalog row legitimately omits

def part_answer(parts, missing=None):
    if not parts:
        return "I don't find that part in the catalog."
    missing = [w for w in (missing or []) if w not in SOFT]
    if missing:       # best row lacks a word the question used: say so, show the top candidates with their descriptions
        return "I don't see that part listed in my database."
    p = parts[0]
    d = _desc(p["desc"])
    q = f", qty {p['qty']}" if p.get("qty") else ""
    if p.get("verified"):
        s = f"{d}: {p['part_number']}{q} (parts catalog p{p['page']}, verified)."
        alts = [f"{x['part_number']} (p{x['page']})" for x in parts[1:3] if x.get("verified")]
        return s + (" Also: " + ", ".join(alts) + "." if alts else "")
    s = f"Closest catalog row, not verified: {p['part_number']} - {d}{q} (parts catalog p{p['page']}{CONF.get(p['confidence'], '')})."
    alts = [f"{x['part_number']} (p{x['page']})" for x in parts[1:3]]
    if alts: s += " Other candidates: " + ", ".join(alts) + "."
    return s + f" The number is read from a scan and may contain errors, so check page {p['page']} before ordering."

ASKCODE = re.compile(r"\b(what|which)\b.*\bcodes?\b|\bcodes? (for|of)\b", re.I)

def code_lookup(db, question):
    """'what's the code for a rotor 2 misfire?' -> the DTC whose title words are all in the question."""
    q = re.sub(r"rotor\s*(1|one)\b", "front rotor", question.lower())
    q = re.sub(r"rotor\s*(2|two)\b", "rear rotor", q)
    ws = {_stem(w) for w in re.findall(r"[a-z0-9]+", q)}
    best = None
    for code, title in db.execute("SELECT code,title FROM dtc"):
        tw = [_stem(w) for w in re.findall(r"[a-z]+", title.lower()) if len(w) > 3 and w != "detected"]
        if tw and all(w in ws for w in tw) and (best is None or len(tw) > best[0]): best = (len(tw), code, title)
    return f"That'd be a {best[1]}, {best[2][0].lower() + best[2][1:].replace(' detected', '')}." if best else None

def deterministic(question, res, db=None):
    if res.get("codes_missing"):
        return " ".join(f"I don't see {c} listed in my database." for c in res["codes_missing"])
    if res.get("pn_missing"):
        return " ".join(f"I don't see part number {p} listed in my database." for p in res["pn_missing"])
    if not res.get("dtc") and db is not None and ASKCODE.search(question):
        a = code_lookup(db, question)
        if a: return a
    if res.get("dtc"):
        return " ".join(dtc_answer(d, bool(CAUSE.search(question))) for d in res["dtc"][:2])
    if "parts" in res.get("route", []):
        if res.get("unmatched"):     # a named term (brand, accessory) is absent from the corpus: don't hand back a look-alike part
            return f"I don't see {', '.join(res['unmatched'])} listed in my database."
        return part_answer(res["parts"], res.get("parts_missing"))
    if db is not None:
        a = spec_answer(db, question)
        if a and res.get("unmatched"):   # a named term (other vehicle, brand) is absent from the corpus: the spec would be for something else
            return f"I don't see {', '.join(res['unmatched'])} listed in my database."
        return a
    return None
