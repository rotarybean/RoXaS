# extract_dtcs.py - pull per-DTC records out of a factory engine-control manual
# (PDF with a native text layer; you supply your own copy).
# usage: python extract_dtcs.py data/manuals/04EngineControl.pdf
#   -> dtc.json, dtc.sqlite in the current directory (both git-ignored)
import re, sys, json, sqlite3, subprocess

pdf = sys.argv[1]
raw = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True,
                     text=True, errors="replace").stdout
pages = raw.split("\f")

def clean(s):
    s = s.replace("\uf8e7", "-")                      # symbol-font dash -> "-"
    return re.sub(r"\(w\)\s+Engine Diagnostics & Control\s*\n?\s*Page \d+", "", s)

HEAD = re.compile(r"^\s*DTC\s+([A-Z]\d{4})\s{2,}(\S.*)$", re.M)
rows = []
for i, p in enumerate(pages):
    m = HEAD.search(p)
    if not m:
        continue
    code = m.group(1)
    title = re.sub(r"^(DTC\s+[A-Z]\d{4}\s+)+", "", m.group(2).strip())
    body = clean(p[m.end():])
    if not re.search(r"\n\s*POSSIBLE\b", body) and i + 1 < len(pages):  # causes spill to next page
        body += "\n" + clean(pages[i + 1])
    parts = re.split(r"\n\s*POSSIBLE\b", body, maxsplit=1)   # label may share a line with the first bullet
    det = parts[0]
    cause = parts[1] if len(parts) > 1 else ""
    det = re.sub(r"^\s*(DETECTION|CONDITION)\s*$", "", det, flags=re.M)
    detect_full = " ".join(det.replace("•", " ").split())
    description = detect_full.split("Diagnostic support note")[0].strip()
    mon = re.search(r"This is an? (.+?) monitor", detect_full)
    cause = re.split(r"\n\s*(?:DTC [A-Z]\d{4}|[A-Z ]{12,})\s*\n", cause)[0]
    causes = [" ".join(c.split()) for c in re.findall(r"•\s*(.+)", cause)]
    rows.append({"code": code, "title": title, "description": description,
                 "monitor": mon.group(1) if mon else "", "causes": causes,
                 "detect_full": detect_full, "source": pdf.split("/")[-1], "page": i + 1})

json.dump(rows, open("dtc.json", "w"), indent=1)
db = sqlite3.connect("dtc.sqlite")
db.execute("DROP TABLE IF EXISTS dtc")
db.execute("CREATE TABLE dtc(code TEXT PRIMARY KEY,title TEXT,description TEXT,monitor TEXT,causes TEXT,detect_full TEXT,source TEXT,page INT)")
db.executemany("INSERT OR REPLACE INTO dtc VALUES(?,?,?,?,?,?,?,?)",
    [(r["code"], r["title"], r["description"], r["monitor"], json.dumps(r["causes"]),
      r["detect_full"], r["source"], r["page"]) for r in rows])
db.commit()
print(f"{len(rows)} DTCs written; {sum(1 for r in rows if not r['causes'])} with no causes")
