# triage_pdfs.py - classify each manual PDF as native-text, scanned, or mixed.
# usage: python3 triage_pdfs.py <manuals_dir> <out_json>
import sys, json, subprocess, hashlib, pathlib

NATIVE_WORDS = 40   # words/page above this counts as a text page

def pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, errors="replace").stdout
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0

def words_per_page(pdf, n):
    raw = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True,
                         text=True, errors="replace").stdout
    pg = raw.split("\f")[:n]
    return [len(p.split()) for p in pg]

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

d = pathlib.Path(sys.argv[1])
res = []
for pdf in sorted(d.glob("*.pdf")):
    n = pages(pdf)
    w = words_per_page(pdf, n)
    text_pages = sum(1 for x in w if x >= NATIVE_WORDS)
    frac = text_pages / n if n else 0
    kind = "native" if frac > 0.9 else "scanned" if frac < 0.1 else "mixed"
    res.append({"file": pdf.name, "pages": n, "text_pages": text_pages,
                "avg_words": round(sum(w) / max(len(w), 1), 1), "kind": kind,
                "md5": md5(pdf)})
    print(f"{pdf.name:45s} {n:4d} pp  text {text_pages:4d}  avg {res[-1]['avg_words']:7.1f}  {kind}", flush=True)
json.dump(res, open(sys.argv[2], "w"), indent=1)
dups = {}
for r in res:
    dups.setdefault(r["md5"], []).append(r["file"])
print("duplicates:", [v for v in dups.values() if len(v) > 1])
