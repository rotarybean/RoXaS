"""usage: python3 build_embeddings.py <roxas.sqlite> <out doc_emb.npz>   (pip install sentence-transformers; downloads bge-small once)"""
import sys, sqlite3, numpy as np
sys.path.insert(0, __file__.rsplit("tools", 1)[0] + "rag")
from embed import Embedder
db = sqlite3.connect(sys.argv[1])
rows = db.execute("SELECT id, heading, text FROM docs ORDER BY id").fetchall()
texts = [f"{h or ''}\n{t}"[:2000] for _, h, t in rows]
E = Embedder().encode(texts)
np.savez_compressed(sys.argv[2], ids=np.array([r[0] for r in rows]), vecs=E.astype(np.float16))
print("embedded", len(rows), "chunks ->", sys.argv[2], E.shape)
