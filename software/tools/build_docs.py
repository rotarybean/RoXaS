# build_docs.py - add searchable manual text (one chunk per page) to roxas.sqlite.
# usage: python3 build_docs.py <manuals_dir> <sqlite_path>
# Skips scanned PDFs (13Electrical, parts catalog); parts and DTCs are handled by build_db.py.
import re, sys, sqlite3, subprocess, pathlib

md, dbp = pathlib.Path(sys.argv[1]), sys.argv[2]
SKIP = {"13Electrical.pdf", "14Parts.pdf", "parts_catalog.pdf", "Ignition coil test- correction Manual3 page218.pdf"}
NOISE = re.compile(r"^\s*(\(w\)\s+)?[A-Za-z &/]+\s*\n?\s*Page \d+\s*$|^\s*End Of Sie\s*$", re.M)

def clean(t):
    t = t.replace("", "-").replace(" ", " ")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", t)).strip()

def heading(txt):
    for line in txt.splitlines()[:12]:
        s = line.strip()
        if 4 <= len(s) <= 80 and sum(c.isupper() for c in s) / max(sum(c.isalpha() for c in s), 1) > 0.6 \
           and not re.match(r"^(DTC )?[A-Z]\d{4}$", s) and not s.startswith("Page"):
            return s
    return ""

db = sqlite3.connect(dbp)
db.executescript("""
DROP TABLE IF EXISTS docs; DROP TABLE IF EXISTS docs_fts;
CREATE TABLE docs(id INTEGER PRIMARY KEY, source_file TEXT, page INT, heading TEXT, text TEXT);
CREATE VIRTUAL TABLE docs_fts USING fts5(heading, text, content='docs', content_rowid='id', tokenize='porter unicode61');
""")
total = 0
for pdf in sorted(md.glob("*.pdf")):
    if pdf.name in SKIP:
        continue
    raw = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True,
                         errors="replace").stdout
    last, n = "", 0
    for pg, txt in enumerate(raw.split("\f"), 1):
        txt = clean(txt)
        if len(txt.split()) < 25:
            continue
        h = heading(txt) or last
        last = h
        db.execute("INSERT INTO docs(source_file,page,heading,text) VALUES(?,?,?,?)", (pdf.name, pg, h, txt))
        n += 1
    total += n
    print(f"{pdf.name:50s} {n:4d} chunks", flush=True)
db.execute("INSERT INTO docs_fts(rowid,heading,text) SELECT id,heading,text FROM docs")
db.commit()
print("total chunks", total)
