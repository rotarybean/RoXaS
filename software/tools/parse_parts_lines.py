# parse_parts_lines.py - parse cropped-table OCR text (cNNN.txt) into one row per part-number variant.
# usage: python3 parse_parts_lines.py <crop_dir> <out_jsonl>
# Entry structure on each page:   sep / CALLOUT-LINE / sep / PN-line (xN) / [continuation lines] / sep ...
import re, sys, json, glob, pathlib

PN = re.compile(r"^[^A-Z0-9¥@$]{0,4}([A-Z0-9¥@$]{4}-[0-9]{2}-[0-9A-Z]{3,5}|[0-9]{5}-[0-9]{4})\b\s*(.*)$")
PN_STRICT = re.compile(r"^(?:[A-Z0-9]{4}-\d{2}-[0-9A-Z]{3,5}|\d{5}-\d{4})$")
HEAD = re.compile(r"^\s*(\d{3,5}[A-Z]{0,2})\b")
# callout line whose box edges were misread (e.g. ") 15-172 1 COVER, THERMOSTAT"): callout NN-XXX, optional junk for the right edge, then UPPERCASE words
CALL = re.compile(r"^[\W_1fl]{0,3}(\d{2}-[0-9A-Za-z]{2,7})\s*[|}!1lI]?\s+([A-Z(][A-Z0-9 .,()/&'\-*]{2,}.*)$")
CALL2 = re.compile(r"(?<![A-Z0-9-])(\d{2}-[0-9A-Za-z]{2,7})\W{0,3}\s+([A-Z(][A-Z0-9 .,()/&'\-*]{2,}.*)$")   # same, but with dotted-rule junk before it
FIX = str.maketrans({"¥": "Y", "@": "8", "$": "S"})

def is_sep(line):
    s = line.strip()
    if not s:
        return True
    alnum = sum(c.isalnum() for c in s)
    return ("--" in s or alnum / max(len(s), 1) < 0.35) and not PN.match(s)

def parse_page(path, page):
    lines = [l.rstrip() for l in open(path, errors="replace").read().split("\n")]
    head = lines[0] if lines else ""
    m = HEAD.match(head)
    code = m.group(1) if m else ""
    body = [l for l in lines[2:] if "CAT. AUFA" not in l]      # skip header + table header
    kinds = []
    for i, l in enumerate(body):
        if is_sep(l):
            kinds.append("sep")
        elif PN.match(l.strip()):
            kinds.append("pn")
        else:
            kinds.append("text")
    rows, cur, last = [], None, None
    for i, (l, k) in enumerate(zip(body, kinds)):
        if k == "sep":
            continue
        prev_sep = i == 0 or kinds[i - 1] == "sep"
        next_sep = i + 1 >= len(body) or kinds[i + 1] == "sep"
        boxed = bool(re.match(r"^[\W_1fl]{0,3}\d{2}-[0-9A-Za-z]{2,7}\s*[|}!]", l.strip()))
        cm = (CALL.match(l.strip()) or CALL2.search(l.strip())) if k == "text" else None
        if k == "text" and ((prev_sep and next_sep) or boxed or cm):   # callout line
            t = re.sub(r"^[\W_1fl]{0,3}", "", l.strip())
            parts = re.split(r"\s*[|}!]\s*", t, maxsplit=1)
            if len(parts) == 1 and cm: parts = [cm.group(1), cm.group(2)]
            cur = dict(callout_raw=parts[0].strip(), desc_raw=(parts[1] if len(parts) > 1 else "").strip())
            last = None
        elif k == "pn":
            m = PN.match(l.strip())
            pn = m.group(1).translate(FIX)
            rest = m.group(2).strip()
            q = re.match(r"^([0-9lI]{1,3}|A/R|AR)\b[\]|)]*\s*(.*)$", rest)
            qty, restr = (q.group(1).replace("l", "1").replace("I", "1"), q.group(2)) if q else ("", rest)
            last = dict(page=page, section=code, header=head.strip(), part_number=pn,
                        pn_ok=bool(PN_STRICT.match(pn)), qty=qty, restr=restr,
                        callout_raw=cur["callout_raw"] if cur else "", desc_raw=cur["desc_raw"] if cur else "")
            rows.append(last)
        elif k == "text" and last is not None:                   # continuation of restrictions
            last["restr"] = (last["restr"] + " " + l.strip()).strip()
        elif k == "text" and cur is not None:                    # wrapped description
            cur["desc_raw"] = (cur["desc_raw"] + " " + l.strip()).strip()
    for r in rows:
        g = code[:2]
        mid = r["part_number"].split("-")[1] if r["part_number"].count("-") == 2 else ""
        r["group_match"] = (mid == g) if mid else None
    return rows

if __name__ == "__main__":
    d, out = pathlib.Path(sys.argv[1]), sys.argv[2]
    allr = []
    for f in sorted(glob.glob(str(d / "c*.txt"))):
        allr += parse_page(f, int(pathlib.Path(f).stem[1:]))
    with open(out, "w") as fh:
        for r in allr:
            fh.write(json.dumps(r) + "\n")
    ok = sum(r["pn_ok"] for r in allr)
    gm = sum(1 for r in allr if r["group_match"])
    qd = sum(1 for r in allr if r["qty"])
    print(f"rows {len(allr)}  pn format ok {ok} ({100*ok/len(allr):.1f}%)  group match {gm}  qty found {qd}")
