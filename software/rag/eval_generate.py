# eval_generate.py - run the eval sets through retrieval + a small LLM and classify every failure.
# Needs the RTX 4060: run in WSL2 (paths /mnt/c/...) or in Windows Python with a CUDA torch build (paths C:/...).   pip install torch transformers accelerate
#   python3 eval_generate.py --db /mnt/c/Users/ArkAn/Desktop/RoXaS/RoXaS-CM5/rx8-c3m/data/derived/roxas.sqlite \
#       --rag software/rag --evals data/derived/eval_set.jsonl data/derived/eval_heldout.jsonl \
#       --model Qwen/Qwen2.5-0.5B-Instruct --out data/derived/gen_baseline.jsonl
# Failure classes per question:
#   pass            retrieval had the evidence AND the answer is right
#   retrieval_fail  the evidence never reached the model (fix retrieval, not the model)
#   generation_fail evidence was in the context but the answer is wrong/incomplete  -> candidate for LoRA
#   bad_refusal     answerable question, model refused
#   no_refusal      unanswerable question, model answered anyway (the dangerous one)
# Separately counted: invented_pn = a part number in the answer that is NOT in the retrieved context.
import argparse, json, re, sqlite3, sys, time, collections

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True); ap.add_argument("--rag", required=True)
ap.add_argument("--evals", nargs="+", required=True); ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
ap.add_argument("--gguf", default=None, help="GGUF file name inside --model dir (loads dequantized: measures quantization error)")
ap.add_argument("--hybrid", action="store_true", help="part-number and DTC questions answered by code (answer.py), not the LLM")
ap.add_argument("--emb_w", type=float, default=0.5); ap.add_argument("--emb", default=None, help="doc_emb.npz from build_embeddings.py: fuse dense retrieval with FTS"); ap.add_argument("--out", required=True); ap.add_argument("--max_new", type=int, default=160)
a = ap.parse_args()
sys.path.insert(0, a.rag)
from rag import retrieve, context_for_model
EMB = None
from eval_retrieval import hit

import torch
if not torch.cuda.is_available():
    sys.exit("CUDA not available in this Python (torch %s). Install a CUDA build: "
             "pip install torch --index-url https://download.pytorch.org/whl/cu124" % torch.__version__)
from transformers import AutoTokenizer, AutoModelForCausalLM
tok = AutoTokenizer.from_pretrained(a.model, gguf_file=a.gguf) if a.gguf else AutoTokenizer.from_pretrained(a.model)
model = AutoModelForCausalLM.from_pretrained(a.model, gguf_file=a.gguf, torch_dtype=torch.float16, device_map="cuda") if a.gguf else AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.float16, device_map="cuda")

from prompt import SYSTEM, messages
if a.emb:
    from embed import EmbIndex
    EMB = EmbIndex(a.emb)
from answer import deterministic
PN = re.compile(r"\b[A-Z0-9]{4}-\d{2}-[0-9A-Z]{3,5}\b|\b\d{5}-\d{4}\b")
REFUSE = re.compile(r"(don't have|do not have|don't see|do not see|not (found|covered|listed|in the manual)|no information|can't find|cannot find|isn't in|not available|(don't|do not|doesn't|does not) cover|can't help|won't guess|(isn't|is not|aren't|are not) covered)", re.I)

def ask(question, ctx):
    msgs = messages(question, ctx)
    enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True)
    ids = enc["input_ids"].to("cuda")
    t = time.time()
    with torch.no_grad():
        out = model.generate(ids, max_new_tokens=a.max_new, do_sample=False)
    return tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True).strip(), time.time() - t

db = sqlite3.connect(a.db)
rows, tally = [], collections.Counter()
for path in a.evals:
    for line in open(path):
        it = json.loads(line)
        res = retrieve(db, it["question"], k=5, emb=EMB, emb_w=a.emb_w)
        ctx = context_for_model(res)
        det = deterministic(it["question"], res, db) if a.hybrid else None
        ans, sec = (det, 0.0) if det else ask(it["question"], ctx)
        got_ctx = hit(it, res, 5)
        refused = bool(REFUSE.search(ans))
        if it["answerable"]:
            if not got_ctx and not det: cls = "retrieval_fail"
            elif refused: cls = "bad_refusal"
            else:
                want = it["must_contain"] + it["pns"]
                right = all(w.lower() in ans.lower() for w in it["must_contain"]) and \
                        (not it["pns"] or any(p in ans for p in it["pns"]))
                cls = "pass" if right else "generation_fail"
        else:
            cls = "pass" if refused else "no_refusal"
        invented = [p for p in PN.findall(ans) if p not in ctx]
        tally[cls] += 1
        tally["invented_pn"] += bool(invented)
        rows.append(dict(id=it["id"], category=it["category"], question=it["question"], answer=ans, cls=cls,
                         invented_pn=invented, seconds=round(sec, 2), context_chars=len(ctx), route=res["route"], by_code=bool(det), docs=[(d["source"][:14], d["page"]) for d in res.get("docs", [])[:6]]))
        print(f"{cls:15s} #{it['id']:<3} {it['question'][:55]:55s} {sec:4.1f}s {'INVENTED '+str(invented) if invented else ''}", flush=True)
with open(a.out, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(dict(tally), "| mean latency", round(sum(r["seconds"] for r in rows) / len(rows), 2), "s")
