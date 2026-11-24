"""OCR-confusion normalizer for Mazda part numbers.  Mazda PNs never contain the letters O or I, and the middle
group is always two digits, so those are unambiguous.  A rare prefix is snapped to a frequent one only when a
single confusable-character swap reaches exactly one frequent prefix.  Returns the PN unchanged if unsure."""
import re, collections
D = {"S": "5", "B": "8", "Z": "2", "G": "6", "L": "1", "Q": "0"}                 # letter -> digit (digit slots)
SWAP = {"S": "35", "3": "S", "5": "S", "8": "B", "B": "8", "6": "G", "G": "6", "2": "Z", "Z": "2", "1": "L", "L": "1", "0": "Q"}
FORM = re.compile(r"^([A-Z0-9]{4})-([A-Z0-9]{2})-([0-9A-Z]{3,4})$")

def prefix_counts(pns):
    c = collections.Counter()
    for p in pns:
        m = FORM.match(p.replace("O", "0").replace("I", "1"))
        if m: c[m.group(1)] += 1
    return c

def normalize(pn, pc):
    m0 = re.match(r"^(.{7})(-KNOB)$", pn)                                       # word tails (KNOB, MOLD...) are real: protect them
    head, wordtail = (m0.group(1), m0.group(2)) if m0 else (pn, "")
    p = head.replace("O", "0").replace("I", "1") + wordtail
    m = FORM.match(p) if not wordtail else FORM.match(head.replace("O", "0").replace("I", "1") + "-ABC")
    if not m: return p if re.fullmatch(r"[0-9]{5}-[0-9]{4}", p) else pn
    pre, mid, tail = m.groups()
    if wordtail: tail = wordtail[1:]
    mid = "".join(D.get(ch, ch) for ch in mid)
    if pre[:2] == "N3" and pre[2].isalpha() and pre[3].isalpha(): pre = pre[:3] + D.get(pre[3], pre[3])   # N3HG -> N3H6
    if pc[pre] < 25:                                                                  # unusual prefix: try one confusable swap
        cands = {pre[:i] + s + pre[i+1:] for i, ch in enumerate(pre) for s in SWAP.get(ch, "")}
        good = [c for c in cands if pc[c] >= 8 and pc[c] >= 3 * pc[pre]]
        if len(good) == 1: pre = good[0]
    return f"{pre}-{mid}-{tail}"
