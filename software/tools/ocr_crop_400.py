# ocr_crop.py - second-pass (400 dpi) re-OCR only the parts-table column of each catalog page (resumable).
# usage: python3 ocr_crop.py <pdf> <report.json> <out_dir>
# report.json comes from parse_parts.py (per-page anchor x "A"); pages without one use the right 32%.
import os, sys, json, subprocess, tempfile, pathlib, glob
from multiprocessing import Pool
from PIL import Image

os.environ["OMP_THREAD_LIMIT"] = "1"
pdf, rep, out = sys.argv[1], json.load(open(sys.argv[2])), pathlib.Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
anchor = {r["page"]: r.get("A") for r in rep}

def work(p):
    txt, tsv = out / f"d{p:03d}.txt", out / f"d{p:03d}.tsv"
    if txt.exists() and tsv.exists():
        return p, "skip"
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "pg")
        subprocess.run(["pdftoppm", "-r", "400", "-gray", "-png", "-f", str(p), "-l", str(p), pdf, base], check=True)
        im = Image.open(glob.glob(base + "*.png")[0])
        a = anchor.get(p)
        left = max(0, int((int(a) - 200) * 4 / 3)) if a else int(im.width * 0.68)
        crop = os.path.join(td, "crop.png")
        im.crop((left, 0, im.width, im.height)).save(crop)
        d = subprocess.run(["tesseract", crop, "-", "--psm", "6", "tsv"], capture_output=True, text=True).stdout
        t = subprocess.run(["tesseract", crop, "-", "--psm", "6"], capture_output=True, text=True).stdout
    tsv.write_text(f"#left_offset\t{left}\n" + d)
    txt.write_text(t)
    return p, "ok"

if __name__ == "__main__":
    n = len(rep)
    with Pool(2) as pool:
        for p, s in pool.imap_unordered(work, range(1, n + 1)):
            print(p, s, flush=True)
    print("done")
