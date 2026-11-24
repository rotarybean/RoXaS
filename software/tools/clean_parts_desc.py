# clean_parts_desc.py - drop the French from part descriptions, using word positions from the OCR (cNNN.tsv).
# Keeps every row, part number, qty and restriction exactly as parsed; only desc_raw is shortened to its English column.
# usage: python3 clean_parts_desc.py <crop_dir> <parts_lines.jsonl> <out_jsonl>
import sys, json, csv, re, collections, pathlib
crop, src, out = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
rows = [json.loads(l) for l in open(src)]
by = collections.defaultdict(list)
for r in rows: by[r["page"]].append(r)
stats = collections.Counter()
ENG, FRE = set(), set()
OFFS = []          # (boundary - left of the PART NO header) on pages where both headers were read; median used as the fallback
def part_left(words):
    c = [int(x[6]) for x in words if x[11].upper().startswith("PART") and 100 < int(x[7]) < 180]
    return min(c) if c else None
def page_lines(p, fallback=None):
    f = crop / f"c{p:03d}.tsv"
    if not f.exists(): return None, None
    t = list(csv.reader(open(f, encoding="utf-8", errors="replace"), delimiter="\t", quoting=csv.QUOTE_NONE))[2:]
    words = [x for x in t if len(x) >= 12 and x[0] == "5" and x[11].strip()]
    hdr = sorted((int(x[6]), int(x[8])) for x in words if "RESTRICTION" in x[11].upper())
    b = (hdr[0][0] + hdr[0][1] + hdr[1][0]) / 2 if len(hdr) >= 2 else None
    if b is not None:
        for x in words:
            w = re.sub(r"[^A-Z]", "", x[11].upper())
            if len(w) >= 3 and int(x[10]) >= 60 and int(x[7]) > 190: (FRE if int(x[6]) >= b else ENG).add(w)
    pl = part_left(words)
    if b is not None and pl is not None and fallback is None: OFFS.append(b - pl)
    if b is None and pl is not None and fallback is not None: b = pl + fallback; stats["fallback_boundary"] += 1
    lines = collections.OrderedDict()
    for x in words: lines.setdefault((x[2], x[3], x[4]), []).append((x[11], int(x[6])))
    return b, list(lines.values())
for p in by: page_lines(p)                                  # pass 1: learn the typical offset
import statistics
MED = statistics.median(OFFS); stats.clear()
FONLY = (FRE - ENG) | {"DE", "DU", "DES", "ET", "AVEC", "SANS", "POUR", "ANNEAU", "RENVOI", "TIGE", "RESSORT", "MANCHON", "BLOC", "ARRETOIR",
    "AXE", "LEVIER", "CLAVETTE", "BOULON", "PLAQUE", "SELECTEUR", "GOUPILLE", "POUSSOIR", "JEU", "TORIQUE", "SEGMENT", "CROCHET", "REMPLIS",
    "CARRE", "BOULE", "CONTRE", "COUDE", "BOUCHON", "CACHE", "SIEGE", "TUYAU", "MOTEUR", "ROBINET", "COLLIER", "DURITE"}
print("french-only words learned:", len(FONLY))
def strip_fr(d):                      # fallback for rows without a usable column boundary: cut at '|' or at the first French-only word
    d = d.split("|")[0].split("!")[0]
    out_ = []
    for w in d.split():
        if any(t in FONLY for t in re.findall(r"[A-Z]+", w.upper())): break
        out_.append(w)
    return re.sub(r"^[^A-Za-z0-9]+", "", " ".join(out_))
for p, rs in sorted(by.items()):
    b, lines = page_lines(p, MED)
    for r in rs:
        d = (r.get("desc_raw") or "").split()
        if not d: stats["empty"] += 1; continue
        if b is None or lines is None:
            nd = strip_fr(r["desc_raw"])
            if nd: r["desc_raw"] = nd; stats["lexicon_cut"] += 1
            continue
        k = min(2, len(d)); hit = None
        for ln in lines:
            tx = [w for w, _ in ln]
            for i in range(len(tx) - k + 1):
                if tx[i:i + k] == d[:k]: hit = (ln, i); break
            if hit: break
        if not hit:
            nd = strip_fr(r["desc_raw"])
            if nd: r["desc_raw"] = nd
            stats["line_not_found"] += 1; continue
        ln, i = hit; keep = []
        for j, tok in enumerate(d):
            if i + j >= len(ln) or ln[i + j][0] != tok: break     # token streams diverged: stop
            if ln[i + j][1] >= b: break
            keep.append(tok)
        if keep: r["desc_raw"] = strip_fr(" ".join(keep)) or " ".join(keep); stats["cleaned"] += 1
        else: stats["empty_after_cut"] += 1
with open(out, "w") as fh:
    for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(dict(stats), "rows", len(rows))
