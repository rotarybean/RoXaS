"""Build authored spec/procedure SFT examples. Usage: make_sft_spec.py <sqlite> <derived_dir>"""
import sys, json, glob, re, os, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from rag import retrieve, context_for_model
from prompt import messages

db = sqlite3.connect(sys.argv[1]); db.row_factory = sqlite3.Row
D = sys.argv[2]
W = {w["i"]: w for w in json.load(open(f"{D}/windows.json"))}
num = re.compile(r"\d[\d,]*(?:\.\d+)?")
def nums(s): return {n.rstrip(",").replace(",", "") for n in num.findall(s)}
def ok(ans, ctx): 
    c = ctx.replace(",", "")
    return all(re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", c) for n in nums(ans))

out, stats = [], {"retrieved": 0, "injected": 0, "dropped": 0}
for f in sorted(glob.glob(f"{D}/authored_*.json")):
    for item in json.load(open(f)):
        w = W[item["w"]]
        src = re.sub(r"\.pdf$", "", w["file"]).strip()
        for q, a in item["qa"]:
            a = f"{a} (Source: {src}, p{w['page']}.)"
            ctx = context_for_model(retrieve(db, q))
            inj = False
            if not ok(a.rsplit(" (Source", 1)[0], ctx):
                ctx += f"\n--- DOC {src} p{w['page']} ---\n{w['text']}"
                inj = True
            if not ok(a.rsplit(" (Source", 1)[0], ctx):
                stats["dropped"] += 1; print("DROP", q); continue
            stats["injected" if inj else "retrieved"] += 1
            m = messages(q, ctx) + [{"role": "assistant", "content": a}]
            out.append({"messages": m, "category": "spec_authored", "injected": inj})
with open(f"{D}/sft_spec_authored.jsonl", "w") as fh:
    for r in out: fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(stats, len(out))
