"""Build the SFT mix. usage: make_sft_mix.py <derived_dir>   (run make_sft_spec.py first)
train: all DTC examples + authored spec/procedure examples + refusals trimmed to ~25% of the mix; dev: held-out slice of each category."""
import sys, json, random
D = sys.argv[1]; random.seed(7)
L = lambda f: [json.loads(l) for l in open(f"{D}/{f}.jsonl")]
tr, dv, sp = L("sft_train"), L("sft_dev"), L("sft_spec_authored")
import os
rf = L("sft_refuse") if os.path.exists(f"{D}/sft_refuse.jsonl") else []
by = lambda R, c: [r for r in R if r.get("cat") == c]
random.shuffle(sp); nd = max(8, len(sp) // 10)
sp_dev, sp_tr = sp[:nd], sp[nd:]
keep = len(by(tr, "dtc_meaning")) + len(by(tr, "dtc_causes")) + len(sp_tr)
ref_n = int(keep / 3)                         # refusals = 25% of the final mix
cnf, unk = by(tr, "code_not_found"), by(tr, "unknown_topic")
random.shuffle(cnf); random.shuffle(unk)
nc = min(len(cnf), int(ref_n * 0.58)); nu = min(len(unk), ref_n - nc)
train = rf[3:] + by(tr, "dtc_meaning") + by(tr, "dtc_causes") + sp_tr + cnf[:nc] + unk[:nu]
dev = rf[:3] + by(dv, "dtc_meaning") + by(dv, "dtc_causes") + sp_dev + by(dv, "code_not_found")[:9] + by(dv, "unknown_topic")[:4]
random.shuffle(train); random.shuffle(dev)
for name, R in (("sft_mix_train", train), ("sft_mix_dev", dev)):
    with open(f"{D}/{name}.jsonl", "w") as f:
        for r in R: f.write(json.dumps(r, ensure_ascii=False) + "\n")
import collections
print("train", len(train), dict(collections.Counter(r.get("cat", r.get("category")) for r in train)))
print("dev", len(dev), dict(collections.Counter(r.get("cat", r.get("category")) for r in dev)))
