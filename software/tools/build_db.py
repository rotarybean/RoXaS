# build_db.py - build roxas.sqlite (parts + DTC + vehicle build) from derived extraction files.
# usage: python3 build_db.py <derived_dir> <out.sqlite>
# NOTE: build the file on a normal disk, then copy it into the repo (SQLite journaling can fail on mounts).
import json, re, sys, sqlite3, collections, pathlib

d = pathlib.Path(sys.argv[1]); out = sys.argv[2]
# parts_lines_en.jsonl = parts_lines.jsonl with the French stripped from descriptions (clean_parts_desc.py); same rows, same part numbers
A = [json.loads(l) for l in open(d / ("parts_lines_en.jsonl" if (d / "parts_lines_en.jsonl").exists() else "parts_lines.jsonl"))]
INDEX_ROWS = [r for r in A if r["page"] >= 292]   # pp292-298 are the part-number index (PN/group/qty only, no descriptions): not catalog rows
A = [r for r in A if r["page"] < 292]
B = [json.loads(l) for l in open(d / "parts_lines_400.jsonl")]
DTC = json.load(open(d / "dtc.json"))

SK = str.maketrans({"O": "0", "D": "0", "C": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6", "T": "7"})
sk = lambda s: s.translate(SK)
exactB = {(r["page"], r["part_number"]) for r in B}
skelB = {(r["page"], sk(r["part_number"])) for r in B}
cnt = collections.Counter(r["part_number"] for r in A)

def tags(restr):
    t, u = set(), restr.upper().replace("¥", "Y")
    if re.search(r"\(MT\)|\(CMT\)|MANU", u): t.add("MT")
    if re.search(r"\(AT\)|\(CAT\)|AUTOM", u): t.add("AT")
    if re.search(r"SPORT SUSP|SUSP\. ?SPORTIVE|\(SPORT", u): t.add("SPORT_SUSP")
    if re.search(r"NOR\. ?SUSP|SUSP ?\.? ?NRML|NORMAL SUSP", u): t.add("NORMAL_SUSP")
    if "W/O SUNROOF" in u: t.add("NO_SUNROOF")
    elif "SUNROOF" in u: t.add("SUNROOF")
    if re.search(r"W/O DSC|SANS DSC", u): t.add("NO_DSC")
    elif re.search(r"W/ ?DSC|AVEC DSC", u): t.add("DSC")
    m = re.search(r"\((\d)-? ?SPEAKER\)", u)
    if m: t.add(f"{m.group(1)}_SPEAKER")
    return sorted(t)

# build FE06 conflicts: manual trans, sport suspension, sunroof
CONFLICT = {"AT", "NORMAL_SUSP", "NO_SUNROOF", "NO_DSC", "NORMAL_POWER"}

def tags_for(pn, restr):
    tg = tags(restr)
    if pn.startswith("N3H4"): tg = sorted(set(tg) | {"NORMAL_POWER"})
    return tg, int(bool(set(tg) & CONFLICT))

db = sqlite3.connect(out)
db.executescript("""
DROP TABLE IF EXISTS parts; DROP TABLE IF EXISTS parts_fts; DROP TABLE IF EXISTS dtc;
DROP TABLE IF EXISTS dtc_fts; DROP TABLE IF EXISTS vehicle;
CREATE TABLE parts(id INTEGER PRIMARY KEY, source_file TEXT, page INT, section TEXT, callout_raw TEXT,
  part_number TEXT, qty TEXT, desc_raw TEXT, restrictions TEXT, tags TEXT, conflicts_fe06 INT, confidence TEXT, verified INT DEFAULT 0, pn_raw TEXT);
CREATE INDEX parts_pn ON parts(part_number);
CREATE VIRTUAL TABLE parts_fts USING fts5(desc_raw, restrictions, part_number, content='parts', content_rowid='id');
CREATE TABLE dtc(code TEXT PRIMARY KEY, title TEXT, description TEXT, monitor TEXT, causes TEXT,
  detect_full TEXT, source_file TEXT, page INT, kind TEXT DEFAULT 'full', note TEXT);
CREATE VIRTUAL TABLE dtc_fts USING fts5(code, title, description, causes, content='dtc', content_rowid='rowid');
CREATE TABLE vehicle(key TEXT PRIMARY KEY, value TEXT, note TEXT);
""")
conf_count = collections.Counter()
for r in A:
    pn, pg = r["part_number"], r["page"]
    if (pg, pn) in exactB or cnt[pn] >= 2: conf = "high"
    elif (pg, sk(pn)) in skelB: conf = "medium"
    else: conf = "low"
    conf_count[conf] += 1
    tg = tags(r["restr"])
    if pn.startswith("N3H4"):          # Normal-power engine assembly code (catalog p4); FE06 is High power (N3H6)
        tg = sorted(set(tg) | {"NORMAL_POWER"})
    db.execute("INSERT INTO parts(source_file,page,section,callout_raw,part_number,qty,desc_raw,restrictions,tags,conflicts_fe06,confidence)"
               " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               ("14Parts.pdf", pg, r["section"], r["callout_raw"], pn, r["qty"], r["desc_raw"], r["restr"],
                json.dumps(tg), int(bool(CONFLICT & set(tg))), conf))
# human verification (data/verified_parts.json, exported by the verification sheet): ok -> verified, fixed -> corrected+verified, bad -> removed, add -> new verified row
db.execute("UPDATE parts SET pn_raw=part_number")   # raw OCR PN: stable key for verified_parts.json
vp = pathlib.Path(d).parent.parent / "data" / "verified_parts.json"
if vp.exists():
    V = json.load(open(vp))
    for v in V.get("rows", {}).values():
        # target the first not-yet-verified row with this raw PN on the page (a PN can repeat on a page: AT/MT rows)
        t = db.execute("SELECT id FROM parts WHERE page=? AND pn_raw=? AND verified=0 ORDER BY id LIMIT 1", (v["page"], v["orig"])).fetchone()
        if not t: continue
        i = t[0]
        if v["st"] == "bad": db.execute("DELETE FROM parts WHERE id=?", (i,)); continue
        if v.get("desc"): db.execute("UPDATE parts SET desc_raw=? WHERE id=?", (v["desc"], i))
        if v.get("restr"):
            _pn = v["pn"] if v["st"] == "fixed" else db.execute("SELECT part_number FROM parts WHERE id=?", (i,)).fetchone()[0]
            _tg, _cf = tags_for(_pn, v["restr"])
            db.execute("UPDATE parts SET restrictions=?, tags=?, conflicts_fe06=? WHERE id=?", (v["restr"], json.dumps(_tg), _cf, i))
        if v.get("qty") not in (None, ""): db.execute("UPDATE parts SET qty=? WHERE id=?", (str(v["qty"]), i))
        if v["st"] == "ok": db.execute("UPDATE parts SET verified=1 WHERE id=?", (i,))
        elif v["st"] == "fixed": db.execute("UPDATE parts SET part_number=?, verified=1, confidence='high' WHERE id=?", (v["pn"], i))
    for a in V.get("add", []):
        _tg, _cf = tags_for(a["pn"], a.get("restr", ""))
        db.execute("INSERT INTO parts(source_file,page,section,callout_raw,part_number,qty,desc_raw,restrictions,tags,conflicts_fe06,confidence,verified,pn_raw)"
                   " VALUES('14Parts.pdf',?,'', '',?,?,?,?,?,?,'high',1,?)", (a["page"], a["pn"], a.get("qty", ""), a.get("desc", ""), a.get("restr", ""), json.dumps(_tg), _cf, a["pn"]))
    print("verified parts applied:", db.execute("SELECT count(*) FROM parts WHERE verified=1").fetchone()[0])
# OCR-confusion normalization of unverified part numbers (pn_normalize.py); verified rows are never touched
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pn_normalize import prefix_counts, normalize
_pc = prefix_counts([r[0] for r in db.execute("SELECT part_number FROM parts")])
_n = 0
for _id, _pn in db.execute("SELECT id, part_number FROM parts WHERE verified=0").fetchall():
    _new = normalize(_pn, _pc)
    if _new != _pn: db.execute("UPDATE parts SET part_number=? WHERE id=?", (_new, _id)); _n += 1
print("part numbers normalized:", _n)
db.execute("INSERT INTO parts_fts(rowid,desc_raw,restrictions,part_number) SELECT id,desc_raw,restrictions,part_number FROM parts")
for r in DTC:
    db.execute("INSERT OR REPLACE INTO dtc VALUES(?,?,?,?,?,?,?,?,'full','')",
               (r["code"], r["title"], r["description"], r["monitor"], json.dumps(r["causes"]),
                r["detect_full"], r["source"], r["page"]))
for r in json.load(open(d / "dtc_extra.json")):
    db.execute("INSERT OR REPLACE INTO dtc VALUES(?,?,?,?,?,?,?,?,?,?)",
               (r["code"], r["title"], r["description"], r["monitor"], json.dumps(r["causes"]),
                r["detect_full"], r["source"], r["page"], r["kind"], r["note"]))
db.execute("INSERT INTO dtc_fts(rowid,code,title,description,causes) SELECT rowid,code,title,description,causes FROM dtc")
for k, v, n in [("chassis", "FE06", "user-stated build"), ("paint", "A3F", "Brilliant Black; repainting flat black"),
                ("interior", "FF4", "black/red"), ("engine", "N3H6-02-000", "6-port; Mazda-remanufactured Renesis, tag April 2017"),
                ("transmission", "Y610-17-01XG", "manual"), ("options", "FE04-07-000", "sunroof and sport suspension"),
                ("model_table", "FE06: High power, 6MT, sunroof, DSC, sport suspension, limited-slip diff", "from catalog p2 (read from the page image; DSC confirmed on the car by owner)")]:
    db.execute("INSERT INTO vehicle VALUES(?,?,?)", (k, v, n))
db.commit()
print("parts", len(A), dict(conf_count), "| dtc", len(DTC))
