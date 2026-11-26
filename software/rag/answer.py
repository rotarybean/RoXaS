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

# ---- this car's own specs (vehicle_specs table: VIN decode + build codes). Spoken sentence, no citation. ----
_VFILL = set("what whats s is are the my mine car rx8 rx 8 mazda how much many does do it its make makes have has i me a an of for on in at to and or tell give about this that run running stock factory spec specs specification number yours your please can you size big large metric imperial kilowatts kilowatt kw newton meters meter liters litres kilograms kg millimeters mm celsius".split())
_VMET = re.compile(r"\bmetric\b|newton|\bn.?m\b|kilo|millimet|\bliters?\b|\blitres?\b|\bkg\b|\bkw\b|meters?|celsius", re.I)
_VUNIT = {"A": "amps", "qt": "quarts", "gal": "gallons", "in": "inches", "lb": "pounds", "ft": "feet", "ft3": "cubic feet",
          "mpg": "mpg", "turns": "turns", "L": "liters", "kg": "kilograms", "mm": "millimeters", "m": "meters"}

def _vspeak(r, metric):
    key, label, value, unit, mv, mu, src, note = r
    if key == "paint_code": return f"It's {note}, paint code {value}."
    if key == "interior_code": return f"{note.replace('/', ' and ').capitalize()}, trim code {value}."
    if key == "drivetrain": return "It's rear wheel drive."
    if key == "wheels": return "Wheels are 18 by 8 inch alloys, front and rear."
    if key in ("mpg_city", "mpg_hwy"):
        where = "city" if key == "mpg_city" else "highway"
        return f"EPA {where} fuel economy is {mv} liters per 100 kilometers." if metric and mv else f"EPA {where} fuel economy is {value} mpg."
    if key in ("horsepower", "torque"):
        n, rpm = [x.strip() for x in value.split("@")]
        if metric:
            n2 = round(float(n) * (0.7457 if key == "horsepower" else 1.35582))
            return f"It makes {n2} {'kilowatts' if key == 'horsepower' else 'newton-meters of torque'} at {rpm} rpm." if key == "horsepower" else f"Torque is {n2} newton-meters at {rpm} rpm."
        return f"It makes {n} horsepower at {rpm} rpm." if key == "horsepower" else f"Torque is {n} lb-ft at {rpm} rpm."
    paren = ""
    import re as _re
    m = _re.search(r"\s*\(([^)]*)\)", label)
    if m: label, paren = label.replace(m.group(0), ""), ", " + m.group(1)
    if metric and mv: value, unit = mv, mu
    u = _VUNIT.get(unit, unit)
    if unit == ":1": value, u = f"{value} to 1", ""
    if unit == "in" and "x" in value: u = ""            # "18 x 8.0 alloy" already says inches in the label
    tail = f" {u}" if u else ""
    if r[6] == "parts_catalog" and note and key not in ("build_code", "cabin_code"): paren += f", {note}"
    if key == "cabin_code": paren = ", sunroof and sport suspension"
    return f"{label} is {value}{tail}{paren}.".replace("  ", " ")

def vehicle_answer(db, question, metric=None):
    """Answer 'my car' spec questions (hp, tires, gear ratios, paint...) from vehicle_specs. None if no clean match."""
    try: rows = db.execute("SELECT key,label,value,unit,metric_value,metric_unit,aliases,source,note FROM vehicle_specs WHERE applies=1").fetchall()
    except Exception: return None
    if PROC.search(question): return None
    ws = {_stem(w) for w in re.findall(r"[a-z0-9]+", question.lower())}
    best = None
    for key, label, value, unit, mv, mu, aliases, src, note in rows:
        lw = {_stem(w) for w in re.findall(r"[a-z0-9]+", label.lower())}
        sc = 0
        for a in [x.strip() for x in aliases.split(",") if x.strip()]:
            aw = {_stem(w) for w in re.findall(r"[a-z0-9]+", a.lower())}
            if aw and aw <= ws: sc = max(sc, len(a))
        if not sc: continue
        sc += 5 * len((lw & ws))
        k = (sc, src == "mazdaforum_decode")
        if best is None or k > best[0]: best = (k, (key, label, value, unit, mv, mu, src, note), lw, aliases)
    if not best: return None
    allowed = _VFILL | best[2] | {_stem(w) for w in re.findall(r"[a-z0-9]+", best[3].lower())}
    if ws - {_stem(w) for w in allowed}: return None      # other words present: probably about a part or something else
    if metric is None: metric = bool(_VMET.search(question))
    return _vspeak(best[1], metric)

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
    if db is not None and not res.get("pn_missing"):
        v = vehicle_answer(db, question)       # this car's own figures first: strict word guard, so part questions fall through
        if v and not (v.startswith("Total cooling") and spec_answer(db, question)): return v
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
