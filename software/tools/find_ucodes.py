# find_ucodes.py - locate every U-code (and the two shared P-code sections) across the manual set.
# usage: python3 find_ucodes.py <manuals_dir> <ocr13_dir>
import re, sys, glob, subprocess, pathlib, collections
md = pathlib.Path(sys.argv[1])
UC = re.compile(r"\b(U[0-9]{4})\b")
hits = collections.defaultdict(list)          # code -> [(file, page, line)]
for pdf in sorted(md.glob("*.pdf")):
    if pdf.name in ("parts_catalog.pdf", "14Parts.pdf", "13Electrical.pdf"):
        continue
    raw = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True,
                         errors="replace").stdout
    for pg, txt in enumerate(raw.split("\f"), 1):
        for line in txt.splitlines():
            for c in UC.findall(line):
                hits[c].append((pdf.name, pg, " ".join(line.split())[:110]))
for f in sorted(glob.glob(sys.argv[2] + "/p*.txt")):
    pg = int(pathlib.Path(f).stem[1:])
    for line in open(f, errors="replace"):
        for c in UC.findall(line):
            hits[c].append(("13Electrical.pdf(OCR)", pg, " ".join(line.split())[:110]))
for c in sorted(hits):
    print(c, len(hits[c]))
    for h in hits[c][:4]:
        print("   ", h)
raw = subprocess.run(["pdftotext", "-layout", str(md / "04EngineControl.pdf"), "-"], capture_output=True,
                     text=True, errors="replace").stdout
for pg, txt in enumerate(raw.split("\f"), 1):
    for m in re.finditer(r"^\s*DTC (P0126, P0128|P0301, P0302)\s*$", txt, re.M):
        print("SHARED SECTION", m.group(1), "page", pg)
    for code in ("P0128", "P0302"):
        for line in txt.splitlines():
            if re.match(rf"^{code}\s{{2,}}", line):
                print("SUMMARY ROW", pg, " ".join(line.split()))
