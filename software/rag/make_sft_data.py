# make_sft_data.py - build the behavior-training set for the LoRA fine-tune (deterministic categories).
# usage: python3 make_sft_data.py <roxas.sqlite> <rag_dir> <out_dir> <eval_jsonl> [<eval_jsonl> ...]
# Examples use the EXACT inference prompt (prompt.messages + rag.context_for_model), so training matches serving.
# Categories built here:  dtc_meaning, dtc_causes, code_not_found, unknown_topic.
# Spec/procedure answers (needs authored, number-verified Q/A) go in <out_dir>/sft_spec_authored.jsonl later.
# Eval leakage guard: DTC codes and brand terms used by the eval sets are excluded from training.
import sys, json, random, re, sqlite3, collections
db_path, rag_dir, out_dir, evals = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
sys.path.insert(0, rag_dir)
from rag import retrieve, context_for_model
from prompt import messages

random.seed(7)
db = sqlite3.connect(db_path)
ban_codes, ban_words = set(), set()
for p in evals:
    for line in open(p):
        it = json.loads(line)
        if it.get("dtc"): ban_codes.add(it["dtc"])
        ban_words |= set(re.findall(r"[a-z0-9]+", it["question"].lower()))
        for c in re.findall(r"\b[PUBC]\d{4}\b", it["question"], re.I): ban_codes.add(c.upper())

def ex(cat, q, answer):
    ctx = context_for_model(retrieve(db, q, k=5))
    return {"cat": cat, "messages": messages(q, ctx) + [{"role": "assistant", "content": answer}]}

rows = []
# --- A) DTC meaning / causes (exact facts from the dtc table) ---
MEAN = ["What does {c} mean?", "What is {c}?", "My scanner shows {c}. What's that?", "Explain DTC {c}.", "{c} code?"]
CAUSE = ["What can cause {c}?", "What are the possible causes of {c}?", "Why would I get {c}?"]
for code, title, causes, src, page in db.execute("SELECT code,title,causes,source_file,page FROM dtc"):
    if code in ban_codes: continue
    t = title if title[:2].isupper() else title[0].lower() + title[1:]   # keep acronyms (APP, ECT, ...)
    for tpl in random.sample(MEAN, 2):
        rows.append(ex("dtc_meaning", tpl.format(c=code), f"{code} is {t}. Source: {src}, page {page}."))
    cl = json.loads(causes) if causes else []
    if cl:
        rows.append(ex("dtc_causes", random.choice(CAUSE).format(c=code),
                       f"Possible causes of {code}: {', '.join(cl[:4])}. Source: {src}, page {page}."))
# --- B) code not in the manuals -> refuse ---
known = {r[0] for r in db.execute("SELECT code FROM dtc")}
REF_CODE = ["I don't have {c} in the manuals, so I can't tell you what it means.",
            "{c} isn't in the manuals I have. A scan tool or a Mazda dealer can look it up.",
            "I don't have anything on {c} in the manuals."]
ASK_CODE = ["What does {c} mean?", "My scanner shows {c}, what is it?", "Explain DTC {c}.", "{c} - what's wrong?"]
n = 0
while n < 130:
    c = random.choice("PPPBCU") + f"{random.randint(0, 3)}{random.randint(0, 999):03d}"
    if c in known or c in ban_codes: continue
    rows.append(ex("code_not_found", random.choice(ASK_CODE).format(c=c), random.choice(REF_CODE).format(c=c)))
    n += 1
# --- C) topics the manuals never mention (aftermarket brands etc.) -> refuse ---
BRANDS = ["cobb", "mishimoto", "hondata", "edelbrock", "haltech", "megasquirt", "greddy", "apexi", "garrett", "tein",
          "bilstein", "nitrous", "e85", "hks", "innovate", "aem", "walbro", "injen", "borla", "vortech"]
absent = []
for b in BRANDS:
    if b in ban_words: continue
    n1 = db.execute("SELECT count(*) FROM docs_fts WHERE docs_fts MATCH ?", (f'"{b}"',)).fetchone()[0]
    n2 = db.execute("SELECT count(*) FROM parts_fts WHERE parts_fts MATCH ?", (f'"{b}"',)).fetchone()[0]
    if n1 + n2 == 0: absent.append(b)
ASK_T = ["What torque do the {t} bolts get?", "What is the part number for a {t}?", "How do I install a {t} on my RX-8?",
         "What settings should I run with the {t}?", "Will a {t} work with my engine?", "What does the manual say about {t}?"]
REF_T = ["The manuals don't cover {t}, so I can't help with that from them.",
         "I don't have {t} in the manuals, so I won't guess.",
         "{t} isn't covered in the factory manuals I have."]
for b in absent:
    for tpl in random.sample(ASK_T, 5):
        rows.append(ex("unknown_topic", tpl.format(t=b.upper() if len(b) <= 3 else b.capitalize()),
                       random.choice(REF_T).format(t=b.upper() if len(b) <= 3 else b.capitalize())))
random.shuffle(rows)
dev = rows[: len(rows) // 10]; train = rows[len(rows) // 10:]
for name, data in (("sft_train.jsonl", train), ("sft_dev.jsonl", dev)):
    with open(f"{out_dir}/{name}", "w") as f:
        for r in data: f.write(json.dumps(r) + "\n")
c = collections.Counter(r["cat"] for r in rows)
print("train", len(train), "dev", len(dev), dict(c), "| absent brands used:", absent)
for r in random.sample(rows, 3):
    print("\n[" + r["cat"] + "] Q:", r["messages"][1]["content"], "\n    A:", r["messages"][2]["content"])
