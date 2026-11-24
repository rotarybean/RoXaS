# make_english_ocr.py - rebuild cNNN.txt from the OCR word table (cNNN.tsv), keeping only the ENGLISH column of the parts table.
# The catalog table is: PART NO | QTY | English | French | (unused) | FROM-TO. The column boundary is the midpoint between the first two
# "MODEL/RESTRICTION" header words. Low-confidence lowercase OCR junk (from the dotted rules) is dropped.
# usage: python3 make_english_ocr.py <crop_dir> <out_dir> [--control]   (--control: no column cut and no junk filter, to verify the rebuild)
import sys, glob, os, re, csv, collections, pathlib
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); control = "--control" in sys.argv
out.mkdir(parents=True, exist_ok=True)
nocut = []
for f in sorted(glob.glob(str(src / "c*.tsv"))):
    rows = list(csv.reader(open(f, encoding="utf-8", errors="replace"), delimiter="\t", quoting=csv.QUOTE_NONE))[2:]
    words = [r for r in rows if len(r) >= 12 and r[0] == "5" and r[11].strip()]
    hdr = sorted([int(r[6]) for r in words if r[11].startswith("MODEL/RESTR")] ) if not control else []
    hw = {int(r[6]): int(r[8]) for r in words if r[11].startswith("MODEL/RESTR")}
    b = None
    if len(hdr) >= 2: b = (hdr[0] + hw[hdr[0]] + hdr[1]) / 2
    elif not control: nocut.append(os.path.basename(f))
    lines = collections.OrderedDict()
    for r in words:
        k = (r[2], r[3], r[4])
        if b is not None and int(r[6]) >= b: continue
        if not control and int(r[10]) < 50 and re.search(r"[a-z]", r[11]): continue
        lines.setdefault(k, []).append(r[11])
    txt = [" ".join(v) for v in lines.values()]
    if txt and txt[0].startswith("PART NUMBER INDEX"): txt.insert(1, "")      # index pages have no table-header line; keep the blank tesseract emits
    (out / (os.path.basename(f)[:-4] + ".txt")).write_text("\n".join(txt) + "\n")
print(f"{len(glob.glob(str(src / 'c*.tsv')))} pages; no column cut on {len(nocut)}: {nocut[:10]}")
