#!/usr/bin/env python3
"""RoXaS service (text mode): question in -> retrieval -> code answer or LLM answer -> text out.
The microphone (whisper.cpp) and speaker (Piper) plug in at the two marked hooks; this file is what they will call.

Layout on the Pi (deploy with software/service/deploy.ps1 or the scp lines in docs/service.md):
  ~/roxas/roxas.py  ~/roxas/rag/{rag,answer,prompt,embed}.py  ~/roxas/roxas.sqlite  ~/roxas/doc_emb.npz
  model: ~/bench/models/roxas-Q4_0.gguf     server: ~/bench/llama.cpp/build/bin/llama-server
Python deps (in ~/bench/venv): numpy onnxruntime tokenizers huggingface_hub

usage:  python3 roxas.py                      interactive: type a question, Enter
        python3 roxas.py --ask "What does P0301 mean?"
        python3 roxas.py --server-url http://127.0.0.1:8099   use an already running llama-server
"""
import argparse, json, os, re, signal, sqlite3, subprocess, sys, time, urllib.request, urllib.error
HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "rag")); sys.path.insert(0, os.path.join(HERE, "..", "rag"))
from rag import retrieve, context_for_model, terms, PNRE  # noqa: E402
from answer import deterministic                      # noqa: E402
from prompt import messages                           # noqa: E402
import userdata                                       # noqa: E402

SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")


def sentences(chunks):
    """Group streamed text into whole sentences so TTS can start on the first one (HOOK 2)."""
    buf = ""
    for c in chunks:
        buf += c
        parts = SENT_END.split(buf)
        for s in parts[:-1]:
            if s.strip(): yield s.strip()
        buf = parts[-1]
    if buf.strip(): yield buf.strip()


class LlamaServer:
    def __init__(self, a):
        self.url, self.proc = a.server_url, None
        if not self.url:
            self.url = f"http://127.0.0.1:{a.port}"
            cmd = [a.server_bin, "-m", a.model, "-c", str(a.n_ctx), "-t", str(a.threads), "--host", "127.0.0.1",
                   "--port", str(a.port), "-np", "1"]
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=open("/tmp/llama-server.log", "w"))
        for _ in range(240):
            try:
                if urllib.request.urlopen(self.url + "/health", timeout=1).status == 200: return
            except Exception:
                if self.proc and self.proc.poll() is not None:
                    sys.exit("llama-server exited; see /tmp/llama-server.log")
                time.sleep(0.5)
        sys.exit("llama-server did not become ready; see /tmp/llama-server.log")

    def stream(self, msgs, max_tokens):
        body = json.dumps({"messages": msgs, "temperature": 0, "max_tokens": max_tokens, "stream": True,
                           "cache_prompt": True}).encode()
        req = urllib.request.Request(self.url + "/v1/chat/completions", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            for line in r:
                line = line.decode().strip()
                if not line.startswith("data:") or line.endswith("[DONE]"): continue
                d = json.loads(line[5:])["choices"][0].get("delta", {}).get("content")
                if d: yield d

    def close(self):
        if self.proc: self.proc.terminate()


class Roxas:
    def __init__(self, a, llm=None):
        self.a = a
        self.db = sqlite3.connect(a.db)
        self.emb = None
        if a.emb and os.path.exists(a.emb):
            from embed import EmbIndex
            self.emb = EmbIndex(a.emb)
            self.emb.search("warm up", 1)        # load the embedding model now, not on the first question
        self.llm = llm; self.pending = None; self.last_spec = None
        self.user_path = os.path.join(os.path.dirname(os.path.abspath(a.db)), "user.sqlite")
        u = userdata.open_user(self.user_path)
        print(f"re-applied {userdata.apply_edits(a.db, u)} hand edits", file=sys.stderr); u.close()

    def answer(self, question):
        """Returns (route, chunks_iterator, timings dict). HOOK 1 (speech-to-text) feeds `question`."""
        t0 = time.perf_counter()
        pend, self.pending = self.pending, None
        if _THANKS.search(question): return "chat", iter([next(_BYE)]), {"retrieve_ms": 0}
        if pend and _YES.search(question): return "chat", iter([pend]), {"retrieve_ms": 0}
        if _NO.search(question) and len(question.split()) <= 3: return "chat", iter(["No problem."]), {"retrieve_ms": 0}
        u = userdata.open_user(self.user_path)                 # custom prompt/reply table, edited from the web console
        try: cm = userdata.match_reply(u, question)
        finally: u.close()
        if cm:
            reply, action = cm
            if action: print(f"  [custom action (not executed yet): {action}]", file=sys.stderr)
            return "custom", iter([reply or "Okay."]), {"retrieve_ms": 0}
        res = retrieve(self.db, question, k=5, emb=self.emb, emb_w=0.5)
        tm = {"retrieve_ms": (time.perf_counter() - t0) * 1000}
        det = deterministic(question, res, self.db)
        if not det and _MET.search(question) and self.last_spec and len(terms(question)) <= 4:
            return "chat", iter([spec_voice(self.last_spec, True)]), tm      # "what's that in metric?"
        if det:
            top = (res.get("parts") or [None])[0]
            if top and top.get("verified") and "parts" in res.get("route", []) and not PNRE.search(question.upper()) \
                    and not det.startswith("I don't"):
                self.pending = part_spoken(det)
                return "code", iter([next(_OFFER)]), tm
            if _PAGE.search(question):
                pg = page_reply(det)
                if pg: return "code", iter([pg]), tm
            if "(Source:" in det:
                self.last_spec = det
                return "code", iter([spec_voice(det, bool(_MET.search(question)))]), tm
            return "code", iter([voice(det)]), tm
        v = vague_reply(question)         # too vague to retrieve on: ask, don't let the model riff on stray context
        if v:
            return "clarify", iter([v]), tm
        ctx = context_for_model(res, self.a.ctx_chars)
        return "llm", self.llm.stream(messages(question, ctx), self.a.max_tokens), tm


import itertools
_VAGUE = set("any some there thing things stuff option options available other kind kinds type types one ones all have has got need want get list show tell about more".split())
_NODB = ["I don't see that listed in my database.",
         "Nothing in my database on that.",
         "That isn't in my database, so I won't guess.",
         "I don't have that in my database."]
_ASK = ["I'm not sure what you're asking. Which part or system do you mean?",
        "I need a bit more to go on. Which part or system is this about?"]
_nodb, _ask = itertools.cycle(_NODB), itertools.cycle(_ASK)

def vague_reply(question):
    ws = [w for w in terms(question) if w not in _VAGUE]
    if len(ws) >= 2: return None
    if ws: return f"What {ws[0]} are you asking about? Tell me the part or system."
    return next(_ask)

_CITE = re.compile(r"\s*\((?:Source: )?[^()]*\bp\d+[^()]*\)")
_PN = re.compile(r"^.*?:\s*([A-Z0-9]{4}-\d{2}-[0-9A-Z]{3,4})(?:,? qty (\d+))?")
_YES = re.compile(r"^\W*(yes|yeah|yep|yup|sure|ok|okay|go ahead|go|ready|please|shoot|read it)\b", re.I)
_NO = re.compile(r"^\W*(no|nope|nah|never ?mind|cancel|skip)\b", re.I)
_THANKS = re.compile(r"^\W*(thanks|thank you|thx|cheers|appreciate)", re.I)
_BYE = itertools.cycle(["You're welcome!", "Anytime.", "Happy to help."])
_OFFER = itertools.cycle(["Yep, I sure do. You ready for it?", "I've got that one. Ready for it?", "Yes, it's on file. Want it now?"])

_IMP = re.compile(r"ft·lbf|in·lbf|\bpsi\b|US qt|\bin\b|°F|\blbf\b|fl oz|\boz\b")
_MET = re.compile(r"\bmetric\b|newton|\bn·?m\b|kpa|kilopascal|millimet|\bliters?\b|\blitres?\b|celsius|\bkg\b|kilogram", re.I)
_PAGE = re.compile(r"\bpage\b|\bwhere\b.*\b(find|listed|located|written)\b", re.I)
_CITE2 = re.compile(r"\((?:Source: )?([^(),]+?)[, ]\s*p(\d+)")
_PAREN = re.compile(r"(\d[\d.,]*(?:-[\d.,]+)?(?:±[\d.]+)?\s*(?:N·m|kPa|L|mm|°C|g|ml|N)\b)\s*\(([^()]*)\)")

def _swap(m, metric):
    if metric: return m.group(1)
    parts = [x.strip() for x in m.group(2).split(", ")]
    imp = next((x for x in parts if "US qt" in x), None) or next((x for x in parts if _IMP.search(x)), None)
    return imp if imp else m.group(0)

def spec_voice(text, metric=False):
    """Specs speak imperial by default; metric on request. One short sentence, no source."""
    t = _CITE.sub("", text)
    sents = [x for x in re.split(r"(?<=[.])\s+", t) if "safe overlap" not in x]
    t = " ".join(sents).replace(" in the suspension technical data", "")
    t = _PAREN.sub(lambda m: _swap(m, metric), t)
    if metric: t = re.sub(r"\s*\([^()]*(?:kgf|psi|US qt|Imp qt|°F|ft·lbf|in·lbf)[^()]*\)", "", t)
    t = re.sub(r"^([A-Z][^:.]{3,40}): (?=\d)", r"\1 is ", t)
    if not metric: t = t.replace("ft·lbf", "ft-lbs").replace("in·lbf", "in-lbs")
    t = re.sub(r"(?<![\d.])(\d+)\.0+(?!\d)", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip()

def page_reply(text):
    m = _CITE2.search(text)
    if not m: return None
    name = re.sub(r"^\d+", "", m.group(1)); name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).replace("_", " ")
    return f"That's on page {m.group(2)} of the {name} section." if name.lower() != "parts catalog" else f"That's on page {m.group(2)} of the parts catalog."

def voice(text):
    """Spoken style: drop page/source citations."""
    return re.sub(r"\s{2,}", " ", _CITE.sub("", text)).strip()

def part_spoken(text):
    m = _PN.match(text)
    if not m: return voice(text)
    return f"That's {m.group(1)}." + (f" You need {m.group(2)}." if m.group(2) and m.group(2) != "1" else "")

_REFUSAL = re.compile(r"manuals?\b|can'?t help|can'?t answer|won'?t guess|not covered|isn'?t covered|aren'?t covered|don'?t cover|don'?t have|don'?t see", re.I)

def scrub(sents):
    """Model refusals vary in wording and cite 'the manuals'; say one short fixed line instead, once."""
    said = False
    for s in sents:
        if _REFUSAL.search(s):
            if not said: yield next(_nodb)
            said = True
        else:
            yield s


def run_one(rx, q, out=print):
    t0 = time.perf_counter()
    route, chunks, tm = rx.answer(q)
    first_s, text = None, []
    for s in (scrub(sentences(chunks)) if route == 'llm' else sentences(chunks)):   # HOOK 2: send each finished sentence to Piper here
        if first_s is None: first_s = time.perf_counter() - t0
        text.append(s); out(s)
    tot = time.perf_counter() - t0
    print(f"  [{route} | retrieve {tm['retrieve_ms']:.0f} ms | first sentence {first_s or 0:.2f}s | total {tot:.2f}s]", file=sys.stderr)
    return " ".join(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(HERE, "roxas.sqlite"))
    ap.add_argument("--emb", default=os.path.join(HERE, "doc_emb.npz"))
    ap.add_argument("--model", default=os.path.join(HOME, "bench/models/roxas-Q4_0.gguf"))
    ap.add_argument("--server-bin", default=os.path.join(HOME, "bench/llama.cpp/build/bin/llama-server"))
    ap.add_argument("--server-url"); ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--n-ctx", type=int, default=2048); ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--ctx-chars", type=int, default=2800); ap.add_argument("--max-tokens", type=int, default=96)
    ap.add_argument("--ask")
    a = ap.parse_args()
    llm = LlamaServer(a)
    signal.signal(signal.SIGTERM, lambda *_: (llm.close(), sys.exit(0)))
    try:
        rx = Roxas(a, llm)
        if a.ask: run_one(rx, a.ask); return
        print("RoXaS ready. Type a question (blank line or Ctrl+D to quit).", file=sys.stderr)
        while True:
            try: q = input("> ").strip()
            except EOFError: break
            if not q: break
            run_one(rx, q)
    finally:
        llm.close()


if __name__ == "__main__":
    main()
