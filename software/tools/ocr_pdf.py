# ocr_pdf.py - resumable per-page OCR for scanned manuals.
# usage: python3 ocr_pdf.py <pdf> <out_dir> [first_page] [last_page]
# Writes <out_dir>/pNNN.txt (plain text) and pNNN.tsv (word boxes + confidence).
# Pages already done are skipped, so it is safe to rerun after an interruption.
import os, sys, subprocess, tempfile, pathlib, glob
from multiprocessing import Pool

os.environ["OMP_THREAD_LIMIT"] = "1"   # one tesseract thread per worker

pdf, out = sys.argv[1], pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

def npages():
    info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    return int(next(l.split()[1] for l in info.splitlines() if l.startswith("Pages:")))

def ocr(p):
    txt, tsv = out / f"p{p:03d}.txt", out / f"p{p:03d}.tsv"
    if txt.exists() and tsv.exists():
        return p, "skip"
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "pg")
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", "-f", str(p), "-l", str(p), pdf, base],
                       check=True)
        img = glob.glob(base + "*.png")[0]
        t = subprocess.run(["tesseract", img, "-", "--psm", "6"], capture_output=True, text=True).stdout
        d = subprocess.run(["tesseract", img, "-", "--psm", "6", "tsv"], capture_output=True, text=True).stdout
    tsv.write_text(d)
    txt.write_text(t)      # written last: marks the page complete
    return p, "ok"

if __name__ == "__main__":
    n = npages()
    a = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    b = int(sys.argv[4]) if len(sys.argv) > 4 else n
    with Pool(2) as pool:
        for p, s in pool.imap_unordered(ocr, range(a, b + 1)):
            print(p, s, flush=True)
    print("done")
