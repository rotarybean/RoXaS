# pick_windows.py - choose spec/procedure passages for authoring SFT Q/A (excludes eval pages and eval topics).
# usage: python3 pick_windows.py <roxas.sqlite> <out_json> <n_per_source>
import sys, re, json, sqlite3, random
db = sqlite3.connect(sys.argv[1]); out = sys.argv[2]; per = int(sys.argv[3])
random.seed(11)
EXCL = {("03EngineDetails.pdf", p) for p in (11, 23, 32, 63, 64, 65, 66, 219, 220, 322, 323, 324)} | \
       {("05Transmissions.pdf", p) for p in (2, 3, 9, 12, 25)} | {("09Suspension.pdf", p) for p in (58, 69, 71)} | \
       {("01Info.pdf", 29), ("07Brakes.pdf", 2), ("11Body.pdf", 200), ("11Body.pdf", 201), ("11Body.pdf", 114)}
UNIT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mm|N·m|kPa|rpm|°C|°F|L\b|kg|V\b|A\b|ohm|Ω|Hz|min|s\b|psi|ft·lbf|in\b)")
SKIP = {"collision_manual.pdf", "12Safety.pdf"}
cands = {}
for f, p, h, t in db.execute("SELECT source_file,page,heading,text FROM docs"):
    if f in SKIP or (f, p) in EXCL or len(t) < 500:
        continue
    best, bs = 0, -1
    for m in UNIT.finditer(t):
        st = max(0, m.start() - 200); w = t[st:st + 640]
        sc = len(UNIT.findall(w)) * 2 + len(re.findall(r"\n\d+\.", w))
        if sc > bs: bs, best = sc, st
    if bs >= 6:
        cands.setdefault(f, []).append((bs, f, p, h, ("…" if best else "") + t[best:best + 640]))
sel = []
for f, L in cands.items():
    L.sort(reverse=True)
    top = L[: per * 3]
    random.shuffle(top)
    sel += top[:per]
random.shuffle(sel)
res = [dict(i=i, file=f, page=p, heading=h, text=t) for i, (s, f, p, h, t) in enumerate(sel)]
json.dump(res, open(out, "w"), indent=0)
print(len(res), "windows from", {f: len(v) for f, v in cands.items()})
