# make_verify.py - build the part-number verification sheet (static HTML + page images).
# usage: python3 make_verify.py <roxas.sqlite> <parts_catalog.pdf> <ocr_crop_dir> <out_dir> [pages_per_call_budget_seconds]
# Output: <out_dir>/index.html + <out_dir>/img/pNNN.jpg. Open index.html in Chrome; mark rows; press Export -> verified_parts.json.
# Resumable: existing images are skipped, so re-run until it prints "images complete".
import sys, os, re, json, sqlite3, subprocess, tempfile, glob, time
from PIL import Image
db_path, pdf, crop_dir, out = sys.argv[1:5]
budget = float(sys.argv[5]) if len(sys.argv) > 5 else 150
os.makedirs(f"{out}/img", exist_ok=True)
db = sqlite3.connect(db_path); db.row_factory = sqlite3.Row
rows = [dict(r) for r in db.execute("SELECT id,page,part_number,pn_raw,qty,desc_raw,confidence,tags,verified FROM parts ORDER BY page,id")]
def desc(d):
    out_ = []
    for w in (d or "").split("|")[0].split():
        if len(w) >= 3 and w.islower(): break
        out_.append(w)
    return " ".join(out_).strip(" ,.")
PRI = re.compile(r"FILTER|PLUG|BELT|PAD|DISC|ROTOR|WIPER|CAP|THERMOSTAT|HOSE|CLUTCH|BRAKE|BULB|FUSE|RELAY|GASKET|SEAL|OIL|COOL|RADIATOR|MASTER|CYLINDER|BEARING|BATTERY|SENSOR|PUMP|COIL|HOSE|BOOT|JOINT|ARM|LINK|SHOCK|SPRING|MIRROR|LAMP|LIGHT", re.I)
pages = {}
for r in rows:
    pages.setdefault(r["page"], []).append(dict(id=r["id"], pn=r["part_number"], orig=r["pn_raw"], qty=r["qty"], d=desc(r["desc_raw"]), c=r["confidence"], v=int(r["verified"] or 0)))
meta = [dict(page=p, rows=v, pri=sum(bool(PRI.search(x["d"])) for x in v), low=sum(x["c"] != "high" for x in v), xr=sum(x["v"] > 0 for x in v)) for p, v in sorted(pages.items())]
import os as _o
if _o.environ.get('ONLY_TODO'): meta = [m for m in meta if m['xr'] < 0.8 * len(m['rows'])]
t0, done = time.time(), 0
for m in meta:
    p = m["page"]; dst = f"{out}/img/p{p:03d}.jpg"
    if os.path.exists(dst): continue
    if time.time() - t0 > budget: break
    tsv = f"{crop_dir}/c{p:03d}.tsv"
    left300 = int(open(tsv).readline().split("\t")[1]) if os.path.exists(tsv) else None
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "170", "-gray", "-png", "-f", str(p), "-l", str(p), pdf, f"{td}/pg"], check=True)
        im = Image.open(glob.glob(f"{td}/pg*.png")[0])
        left = int((left300 or im.width * 0.68 * 300 / 170) * 170 / 300)
        im.crop((max(0, left - 20), 0, im.width, im.height)).convert("L").save(dst, quality=72)
    done += 1
left = sum(not os.path.exists(f"{out}/img/p{m['page']:03d}.jpg") for m in meta)
data = json.dumps(meta, ensure_ascii=False)
open(f"{out}/index.html", "w", encoding="utf-8").write(open(os.path.join(os.path.dirname(__file__), "verify_template.html"), encoding="utf-8").read().replace("__DATA__", data))
print(f"{done} images this run, {left} pages still to render" if left else "images complete", f"({len(meta)} pages, {len(rows)} rows)")
