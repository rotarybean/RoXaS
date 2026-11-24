#!/usr/bin/env python3
"""Pi benchmark for the retrieval embedding step (bge-small-en-v1.5 through onnxruntime, no torch).
Setup once:  ~/bench/venv/bin/pip install onnxruntime tokenizers numpy huggingface_hub
Run:         ~/bench/venv/bin/python bench/bench_embed.py [doc_emb.npz]
Reports load time, per-question latency (cold first call, then warm), peak RAM, and the top-3 manual chunk ids per question
(compare with software/tools/embed_check.py on the PC to confirm the Pi gets the same results)."""
import sys, time, resource, statistics
import numpy as np
t0 = time.perf_counter()
from huggingface_hub import hf_hub_download
import onnxruntime as ort
from tokenizers import Tokenizer
onnx = hf_hub_download("BAAI/bge-small-en-v1.5", "onnx/model.onnx")
tokp = hf_hub_download("BAAI/bge-small-en-v1.5", "tokenizer.json")
tok = Tokenizer.from_file(tokp); tok.enable_truncation(512); tok.enable_padding()
so = ort.SessionOptions(); so.intra_op_num_threads = 4
sess = ort.InferenceSession(onnx, so, providers=["CPUExecutionProvider"])
need = {i.name for i in sess.get_inputs()}
QPREFIX = "Represent this sentence for searching relevant passages: "
QS = ["How do I check the manual transmission oil level?", "What torque do I use on the brake caliper bleeder screw?", "Where are the correct jacking points?", "What is the minimum apex seal height?", "What does cooling fan number one draw in amps?"]
def enc(q):
    e = tok.encode(QPREFIX + q)
    f = {"input_ids": np.array([e.ids], dtype=np.int64), "attention_mask": np.array([e.attention_mask], dtype=np.int64),
         "token_type_ids": np.zeros((1, len(e.ids)), dtype=np.int64)}
    out = sess.run(None, {k: v for k, v in f.items() if k in need})[0]
    v = out[0, 0]; return v / np.linalg.norm(v)
load = time.perf_counter() - t0
t = time.perf_counter(); enc(QS[0]); first = time.perf_counter() - t
warm = []
for _ in range(10):
    for q in QS:
        t = time.perf_counter(); enc(q); warm.append(time.perf_counter() - t)
print(f"load+download {load:.1f}s | first call {first*1000:.0f} ms | warm median {statistics.median(warm)*1000:.0f} ms (min {min(warm)*1000:.0f}, max {max(warm)*1000:.0f}) | peak RAM {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f} MB")
if len(sys.argv) > 1:
    z = np.load(sys.argv[1]); ids, M = z["ids"], z["vecs"].astype(np.float32)
    for q in QS:
        t = time.perf_counter(); s = M @ enc(q); top = np.argsort(-s)[:3]; dt = time.perf_counter() - t
        print(f"{dt*1000:.0f} ms | {[int(ids[i]) for i in top]} | {q}")
