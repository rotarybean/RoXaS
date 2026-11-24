"""Dense retrieval for the manuals (docs table): bge-small-en-v1.5 embeddings fused with FTS5 by reciprocal rank.
build:  python3 software/tools/build_embeddings.py <roxas.sqlite> <doc_emb.npz>      (run on the PC, needs sentence-transformers)
use:    retrieve(db, q, emb=EmbIndex("doc_emb.npz"))                                  (eval_generate.py --emb doc_emb.npz)
The 384-dim float16 matrix is ~2 MB for 2,373 chunks; query embedding is one forward pass of a 33M-param encoder."""
import numpy as np

MODEL = "BAAI/bge-small-en-v1.5"
QPREFIX = "Represent this sentence for searching relevant passages: "

class Embedder:
    def __init__(self, name=MODEL):
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer(name, device="cpu")
        self.m.max_seq_length = 512
    def encode(self, texts, query=False):
        if query: texts = [QPREFIX + t for t in texts]
        return np.asarray(self.m.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False), dtype=np.float32)

class OnnxEmbedder:
    """Same vectors as Embedder, without torch: onnxruntime + tokenizers (what the CM5 runs; 16 ms per question)."""
    def __init__(self, name=MODEL, threads=4):
        from huggingface_hub import hf_hub_download
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tok = Tokenizer.from_file(hf_hub_download(name, "tokenizer.json"))
        self.tok.enable_truncation(512); self.tok.enable_padding()
        so = ort.SessionOptions(); so.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(hf_hub_download(name, "onnx/model.onnx"), so, providers=["CPUExecutionProvider"])
        self.need = {i.name for i in self.sess.get_inputs()}
    def encode(self, texts, query=False):
        if query: texts = [QPREFIX + t for t in texts]
        out = []
        for t in texts:
            e = self.tok.encode(t)
            f = {"input_ids": np.array([e.ids], dtype=np.int64), "attention_mask": np.array([e.attention_mask], dtype=np.int64),
                 "token_type_ids": np.zeros((1, len(e.ids)), dtype=np.int64)}
            v = self.sess.run(None, {k: x for k, x in f.items() if k in self.need})[0][0, 0]
            out.append(v / np.linalg.norm(v))
        return np.asarray(out, dtype=np.float32)

def make_embedder():
    """sentence-transformers on the PC, onnxruntime on the Pi."""
    try:
        import sentence_transformers  # noqa: F401
        return Embedder()
    except Exception:
        return OnnxEmbedder()

class EmbIndex:
    def __init__(self, path, embedder=None):
        z = np.load(path)
        self.ids, self.M = z["ids"], z["vecs"].astype(np.float32)
        self.embedder = embedder
    def search(self, q, topn=8):
        if self.embedder is None: self.embedder = make_embedder()
        v = self.embedder.encode([q], query=True)[0]
        s = self.M @ v
        top = np.argsort(-s)[:topn]
        return [(int(self.ids[i]), float(s[i])) for i in top]
