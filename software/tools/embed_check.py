"""PC-side reference for bench_embed.py: same questions, sentence-transformers, same top-3 chunk ids.
usage: python software/tools/embed_check.py data/derived/doc_emb.npz"""
import sys; sys.path.insert(0, "software/rag")
from embed import EmbIndex
QS = ["How do I check the manual transmission oil level?", "What torque do I use on the brake caliper bleeder screw?", "Where are the correct jacking points?", "What is the minimum apex seal height?", "What does cooling fan number one draw in amps?"]
ix = EmbIndex(sys.argv[1])
for q in QS: print([d for d, _ in ix.search(q, 3)], "|", q)
