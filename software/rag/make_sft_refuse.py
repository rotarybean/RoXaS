"""Natural-language 'plausible but not in the manuals' refusal examples, with REAL retrieved (off-topic) context.
usage: make_sft_refuse.py <sqlite> <derived_dir>  -> sft_refuse.jsonl. Keeps a question only if its key term has 0 hits in docs+parts."""
import sys, json, random, re, sqlite3
sys.path.insert(0, "software/rag")
from rag import retrieve, context_for_model
from prompt import messages
random.seed(11)
db = sqlite3.connect(sys.argv[1]); out = sys.argv[2]
ban = set()
import glob
for p in glob.glob(out + "/eval_*.jsonl"):
    for l in open(p): ban |= set(re.findall(r"[a-z0-9]+", json.loads(l)["question"].lower()))
T = {  # key term -> list of phrasings
 "supercharger": ["What boost pressure is safe with a supercharger on my RX-8?", "How do I mount a supercharger belt?"],
 "turbocharger": ["What size turbocharger fits my RX-8?", "How much boost can the stock apex seals take with a turbocharger?"],
 "dyno": ["What horsepower should my RX-8 make on a dyno?", "What dyno settings do I use to tune the car?"],
 "tint": ["What window tint percentage is legal on the RX-8?", "How do I apply window tint to the rear glass?"],
 "subwoofer": ["Which subwoofer fits under the seat?", "How do I wire a subwoofer into the Bose amp?"],
 "spoiler": ["How do I install a rear spoiler?", "What torque do the spoiler bolts get?"],
 "coilover": ["What spring rate do the coilovers use?", "How do I set coilover ride height?"],
 "wideband": ["Where do I mount the wideband sensor?", "What air-fuel ratio should the wideband read at idle?"],
 "flowmaster": ["What is the part number for a Flowmaster muffler?"],
 "carbon": ["How do I remove carbon from the rotor housings with a chemical cleaner?"],
 "methanol": ["How much methanol can I inject with the fuel?", "How do I set up methanol injection?"],
 "ethanol": ["Can I run ethanol blends above ten percent in my RX-8?"],
 "headers": ["What are the best aftermarket headers for the RX-8?", "How do I install headers?"],
 "bluetooth": ["How do I pair my phone over Bluetooth?", "What is the Bluetooth pairing code?"],
 "carplay": ["How do I get CarPlay in the dash?"],
 "remap": ["How do I remap the ECU for more power?", "Which ECU remap software works with the PCM?"],
 "valet": ["How do I turn on valet mode?"],
 "lowering": ["How much does lowering the car by an inch change the alignment?"],
 "snow": ["What snow tire size should I run?", "Do I need snow chains on the RX-8?"],
 "diesel": ["Can I put diesel in the tank?"],
 "oilcooler": [],
 "recall": ["Is there a recall on the ignition coils?", "What recalls apply to my VIN?"],
 "warranty": ["How long is the powertrain warranty?", "Does the warranty cover the engine rebuild?"],
 "insurance": ["What insurance group is the RX-8 in?"],
 "mpg": ["What mpg does the RX-8 get on the highway?"],
 "towing": ["What is the towing capacity?", "Can I tow a trailer with the RX-8?"],
 "roof rack": ["How do I install a roof rack?"],
 "cruise": ["How do I add cruise control to the RX-8?"],
 "nos": [], "hydraulic": [],
}
rows = []
REF = ["The manuals don't cover {t}, so I can't help with that from them.",
       "I don't have {t} in the manuals, so I won't guess.",
       "{t} isn't covered in the factory manuals I have.",
       "That isn't in the manuals I have, so I can't answer it."]
def hits(t):
    n = 0
    for tab in ("docs_fts", "parts_fts"):
        try: n += db.execute(f"SELECT count(*) FROM {tab} WHERE {tab} MATCH ?", (f'"{t}"',)).fetchone()[0]
        except Exception: pass
    return n
kept = []
for t, qs in T.items():
    if not qs or t in ban or hits(t) > 0: continue
    for q in qs:
        if set(re.findall(r"[a-z0-9]+", q.lower())) & {"jacking"}: continue
        ctx = context_for_model(retrieve(db, q, k=5))
        a = random.choice(REF).format(t=t.capitalize() if " " not in t else t)
        if a.startswith(("The manuals don't cover", "I don't have", )) is False and "{t}" in a: pass
        rows.append({"cat": "unknown_topic2", "messages": messages(q, ctx) + [{"role": "assistant", "content": a}]})
    kept.append(t)
random.shuffle(rows)
with open(out + "/sft_refuse.jsonl", "w") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows), "examples; terms kept:", kept)
