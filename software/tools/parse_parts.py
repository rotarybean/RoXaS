# parse_parts.py - turn per-page OCR word boxes (pNNN.tsv) of the parts catalog into rows.
# usage: python3 parse_parts.py <ocr_dir> <out_jsonl>
# Layout (300 dpi): table at the right of each spread. Per entry: a boxed index callout
# (e.g. 17-321) with EN/FR descriptions on that line, the real part number and qty on the
# line below, restriction text in the columns to the right. Columns are offsets from the
# median x of the callouts on the page, so small scan shifts do not matter.
import csv, glob, json, re, sys, statistics, pathlib

CALL = re.compile(r'^\d{2}-\d{3,4}[A-Z]{0,2}$')
PN_FIND = re.compile(r'[A-Z0-9]{4}-\d{2}-[0-9A-Z]{3,5}(?![a-z])|\d{5}-\d{4}')
PN = re.compile(r'^(?:[A-Z0-9]{4}-\d{2}-[0-9A-Z]{3,5}|\d{5}-\d{4}|[A-Z0-9]{4}-[0-9A-Z]{2}-[0-9A-Z]{3,5})$')

def norm(t):
    return (t.replace('¥', 'Y').replace('€', 'E').replace('—', '-').replace('_', '-')
             .replace('|', '').strip())

def load(f):
    out = []
    for r in csv.DictReader(open(f), delimiter='\t', quoting=3):
        t = (r['text'] or '').strip()
        if not t or float(r['conf']) < 0:
            continue
        out.append(dict(t=t, x=int(r['left']), y=int(r['top']), w=int(r['width']),
                        h=int(r['height']), c=float(r['conf'])))
    return out

def join(ws):
    ws = sorted(ws, key=lambda w: (round(w['y'] / 30), w['x']))
    return ' '.join(w['t'] for w in ws).strip()

def parse_page(f, pageno):
    W = load(f)
    bars = [w for w in W if set(w['t']) <= set('|!Il1') and w['h'] > 15]
    def sides(c):
        left = any(0 < c['x'] - b['x'] < 120 and abs(b['y'] - c['y']) < 40 for b in bars)
        right = any(0 < b['x'] - (c['x'] + c['w']) < 200 and abs(b['y'] - c['y']) < 40 for b in bars)
        return left, right
    cand = [(w, sides(w)) for w in W if CALL.match(norm(w['t']))]
    strict = [w for w, (l, r) in cand if l and r]
    loose = [w for w, (l, r) in cand if l or r]
    anchor_set = strict or loose
    if anchor_set:
        A0 = statistics.median(sorted(w['x'] for w in anchor_set)[len(anchor_set) // 2:])
        calls = [w for w in loose if abs(w['x'] - A0) < 60]
    else:
        calls = []
    head = join([w for w in W if w['y'] < 140 and w['x'] > 2700])
    m = re.match(r'^(\d{3,4}[A-Z]?)\b', head)
    group = m.group(1) if m else ''
    if len(calls) < 1:
        return [], dict(page=pageno, header=head, status='no_table')
    A = statistics.median(w['x'] for w in calls)
    calls.sort(key=lambda w: w['y'])
    rows = []
    for i, c in enumerate(calls):
        y0 = c['y'] - 30
        y1 = calls[i + 1]['y'] - 30 if i + 1 < len(calls) else c['y'] + 260
        E = [w for w in W if y0 <= w['y'] < y1 and w['x'] >= A - 120]
        pn_ws = [w for w in E if A - 120 <= w['x'] < A + 170 and w['y'] > c['y'] + 25]
        pn_line = norm(' '.join(w['t'] for w in sorted(pn_ws, key=lambda w: w['x']))).replace(' ', '')
        found = PN_FIND.findall(pn_line)
        pn_raw = found[0] if found else pn_line
        pn_conf = min([w['c'] for w in pn_ws], default=0)
        qty_ws = [w for w in E if A + 170 <= w['x'] < A + 260 and w['y'] > c['y'] + 25 or
                  (A + 170 <= w['x'] < A + 260 and abs(w['y'] - c['y']) < 25 and w['t'].isdigit())]
        qty = join(qty_ws)
        col = lambda a, b: join([w for w in E if A + a <= w['x'] < A + b])
        rows.append(dict(
            page=pageno, group=group, callout=norm(c['t']), part_number=pn_raw,
            pn_conf=pn_conf, pn_ok=bool(PN.match(pn_raw)), qty=qty,
            desc_en=col(200, 530), desc_fr=col(530, 840),
            restr=col(840, 1170), from_to=col(1170, 3000), y=c['y']))
    return rows, dict(page=pageno, header=head, status='ok', n=len(rows), A=A)

if __name__ == '__main__':
    d, out = pathlib.Path(sys.argv[1]), sys.argv[2]
    allrows, report = [], []
    for f in sorted(glob.glob(str(d / 'p*.tsv'))):
        n = int(pathlib.Path(f).stem[1:])
        r, rep = parse_page(f, n)
        allrows += r
        report.append(rep)
    with open(out, 'w') as fh:
        for r in allrows:
            fh.write(json.dumps(r) + '\n')
    json.dump(report, open(out + '.report.json', 'w'), indent=0)
    ok = sum(r['pn_ok'] for r in allrows)
    print(f"pages {len(report)}  table pages {sum(r['status']=='ok' for r in report)}  "
          f"rows {len(allrows)}  pn regex ok {ok} ({100*ok/max(len(allrows),1):.1f}%)")
