# train_lora.py - LoRA fine-tune of Qwen2.5-0.5B-Instruct for RoXaS behavior (not facts).
# Plain transformers + peft, manual assistant-only loss masking. Run on the RTX 4060 (Windows or WSL).
# usage: python train_lora.py --train data/derived/sft_mix_train.jsonl --dev data/derived/sft_mix_dev.jsonl --out data/derived/lora_run1
# After training: python train_lora.py --merge data/derived/lora_run1/epoch3 --out data/derived/lora_run1/merged
import argparse, json, math, os, random, time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

BASE = "Qwen/Qwen2.5-0.5B-Instruct"
ap = argparse.ArgumentParser()
ap.add_argument("--train"); ap.add_argument("--dev"); ap.add_argument("--out", required=True)
ap.add_argument("--merge", help="adapter dir to merge into the base model; writes to --out")
ap.add_argument("--epochs", type=int, default=3)
ap.add_argument("--lr", type=float, default=2e-4)
ap.add_argument("--r", type=int, default=16)
ap.add_argument("--micro_bs", type=int, default=2)
ap.add_argument("--accum", type=int, default=8)
ap.add_argument("--max_len", type=int, default=1536)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()

tok = AutoTokenizer.from_pretrained(BASE)

if a.merge:
    from peft import PeftModel
    m = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float16)
    m = PeftModel.from_pretrained(m, a.merge).merge_and_unload()
    m.save_pretrained(a.out); tok.save_pretrained(a.out)
    print("merged ->", a.out); raise SystemExit

assert torch.cuda.is_available(), "CUDA not available (need the cu124 torch build)"
from peft import LoraConfig, get_peft_model
random.seed(a.seed); torch.manual_seed(a.seed)

def encode(rec):
    msgs = rec["messages"]
    prefix = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(msgs, tokenize=False)
    assert full.startswith(prefix)
    p = tok(prefix, add_special_tokens=False)["input_ids"]
    f = tok(full, add_special_tokens=False)["input_ids"]
    if len(f) > a.max_len: return None
    labels = [-100] * len(p) + f[len(p):]      # loss on assistant tokens only
    return f, labels

def load(path):
    rows, skipped = [], 0
    for line in open(path, encoding="utf-8"):
        e = encode(json.loads(line))
        if e is None: skipped += 1
        else: rows.append(e)
    print(f"{path}: {len(rows)} examples, {skipped} over {a.max_len} tokens skipped")
    return rows

def batches(rows, bs, shuffle):
    idx = list(range(len(rows)))
    if shuffle: random.shuffle(idx)
    for i in range(0, len(idx), bs):
        chunk = [rows[j] for j in idx[i:i + bs]]
        L = max(len(x[0]) for x in chunk)
        ids = torch.full((len(chunk), L), tok.pad_token_id); lab = torch.full((len(chunk), L), -100)
        att = torch.zeros((len(chunk), L), dtype=torch.long)
        for k, (x, y) in enumerate(chunk):
            ids[k, :len(x)] = torch.tensor(x); lab[k, :len(y)] = torch.tensor(y); att[k, :len(x)] = 1
        yield ids.cuda(), att.cuda(), lab.cuda()

train, dev = load(a.train), load(a.dev)
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16).cuda()
model.gradient_checkpointing_enable(); model.enable_input_require_grads()
cfg = LoraConfig(r=a.r, lora_alpha=2 * a.r, lora_dropout=0.05, task_type="CAUSAL_LM",
                 target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
model = get_peft_model(model, cfg); model.print_trainable_parameters()
params = [p for p in model.parameters() if p.requires_grad]
opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.0)
steps_total = a.epochs * math.ceil(len(train) / (a.micro_bs * a.accum))
warm = max(1, int(0.05 * steps_total))
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / warm) * max(0.0, 0.5 * (1 + math.cos(math.pi * s / steps_total))))

def dev_loss():
    model.eval(); tot, n = 0.0, 0
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
        for ids, att, lab in batches(dev, 4, False):
            out = model(input_ids=ids, attention_mask=att, labels=lab)
            k = (lab[:, 1:] != -100).sum().item(); tot += out.loss.item() * k; n += k
    model.train(); return tot / max(n, 1)

os.makedirs(a.out, exist_ok=True)
print(f"baseline dev loss {dev_loss():.4f}")
model.train(); step = 0; t0 = time.time()
for ep in range(1, a.epochs + 1):
    run, cnt, micro = 0.0, 0, 0
    for ids, att, lab in batches(train, a.micro_bs, True):
        with torch.autocast("cuda", dtype=torch.bfloat16):
            loss = model(input_ids=ids, attention_mask=att, labels=lab).loss
        (loss / a.accum).backward(); run += loss.item(); cnt += 1; micro += 1
        if micro % a.accum == 0:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True); step += 1
            if step % 10 == 0: print(f"  step {step}/{steps_total} loss {run/cnt:.4f} lr {sched.get_last_lr()[0]:.2e}")
    opt.step(); opt.zero_grad(set_to_none=True)   # flush leftover micro-batches
    d = dev_loss(); print(f"epoch {ep}: train {run/cnt:.4f} dev {d:.4f} ({time.time()-t0:.0f}s)")
    model.save_pretrained(f"{a.out}/epoch{ep}")
print("done. adapters in", a.out)
