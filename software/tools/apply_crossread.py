"""usage: apply_crossread.py <crossread.json> ...   Each file: {"page":N,"rows":[[db_pn|null, true_pn, "DESC", qty], ...]}  (transcribed from the page image)
Merges into data/verified_parts.json: db_pn is the PN currently in the DB (matched via pn_raw or part_number); null = row missing from the DB (add)."""
import json, sys, sqlite3, pathlib
root = pathlib.Path(__file__).resolve().parents[2]
db = sqlite3.connect(root / "data/derived/roxas.sqlite")
vp = root / "data/verified_parts.json"
V = json.load(open(vp)); R = V["rows"]; A = V["add"]
for f in sys.argv[1:]:
    X = json.load(open(f)); pg = X["page"]
    R = {k: v for k, v in R.items() if v["page"] != pg or v["st"] == "bad"}          # re-running a page replaces its earlier rows
    A = [a for a in A if a["page"] != pg]
    for i, row in enumerate(X["rows"]):
        dbpn, pn, desc, qty = row[:4]; restr = row[4] if len(row) > 4 else ""
        if dbpn is None: A.append({"page": pg, "pn": pn, "desc": desc, "qty": str(qty), "restr": restr}); continue
        r = db.execute("SELECT pn_raw FROM parts WHERE page=? AND (part_number=? OR pn_raw=?) ORDER BY (pn_raw=?) DESC", (pg, dbpn, dbpn, dbpn)).fetchone()
        if not r: print("NOT FOUND", pg, dbpn); continue
        d = {"st": "ok" if r[0] == pn else "fixed", "pn": pn, "orig": r[0], "page": pg, "desc": desc, "qty": str(qty), "restr": restr}
        R[f"cr{pg}_{i}"] = d
    print(f, len(X["rows"]), "rows")
V["rows"], V["add"] = R, A
json.dump(V, open(vp, "w"), indent=0)
