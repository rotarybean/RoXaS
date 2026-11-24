# eval_heldout.py - held-out question set (written AFTER the retrieval fixes, none used to tune them).
# usage: python3 eval_heldout.py <roxas.sqlite> <rag_dir> <out_eval_jsonl>
# Part-number ground truth for H12-H14 was read directly off the catalog page image (p119), not from the database.
import sys, json, sqlite3, collections
sys.path.insert(0, sys.argv[2])
from rag import retrieve
from eval_retrieval import D, N, hit

SK = str.maketrans({"O": "0", "D": "0", "C": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6", "T": "7"})
sk = lambda s: s.translate(SK)

H = [
 D(101, "dtc", "What does P0300 mean?", ["random", "misfire"], code="P0300"),
 D(102, "dtc", "What does DTC P2503 indicate?", ["charging"], code="P2503"),
 D(103, "dtc", "What is U2017?", ["air bag"], code="U2017"),
 D(104, "spec", "What brake fluid should I use?", ["DOT-3"], [["07Brakes.pdf", 2], ["05Transmissions.pdf", 2]]),
 D(105, "spec", "What is the standard compression pressure?", ["830"], [["03EngineDetails.pdf", 11], ["03EngineDetails.pdf", 322]]),
 D(106, "spec", "What is the minimum allowable compression pressure?", ["680"], [["03EngineDetails.pdf", 11], ["03EngineDetails.pdf", 322]]),
 D(107, "spec", "What is the idle speed for the manual transmission?", ["750-850"], [["03EngineDetails.pdf", 23]]),
 D(108, "spec", "What tire air pressure does the manual list?", ["220"], [["09Suspension.pdf", 71]]),
 D(109, "spec", "What is the front wheel total toe-in specification?", ["1.2"], [["09Suspension.pdf", 58], ["09Suspension.pdf", 69]]),
 D(110, "procedure", "How do I replace the headlight bulb?", ["bulb"], [["11Body.pdf", 200], ["11Body.pdf", 201]]),
 D(111, "procedure", "How do I replace the windshield wiper blade?", ["wiper"], [["11Body.pdf", 114]]),
 D(112, "part", "What is the part number for the clutch release cylinder?", [], pn=["F151-41-920"]),
 D(113, "part", "What is the part number for the clutch bleeder screw?", [], pn=["GA5R-33-691"]),
 D(114, "part", "What is the part number for the clutch push rod?", [], pn=["GA2A-41-341A"]),
 N(115, "What ratio of 2-stroke oil should I premix with the fuel?", "premix is not in the manuals"),
 N(116, "What does DTC P3000 mean?", "not a code in the manuals"),
 N(117, "How do I flash a tune to the ECU with an Accessport?", "aftermarket tuning, not covered"),
]

if __name__ == "__main__":
    db = sqlite3.connect(sys.argv[1])
    with open(sys.argv[3], "w") as f:
        for it in H:
            f.write(json.dumps(it) + "\n")
    by = collections.defaultdict(lambda: [0, 0])
    notes = []
    for it in H:
        res = retrieve(db, it["question"], k=5)
        ok = hit(it, res, 5)
        if it["category"] == "part" and not ok:
            got = [p["part_number"] for p in res["parts"][:5]]
            near = [g for g in got if sk(g) == sk(it["pns"][0])]
            notes.append((it["id"], "OCR-near-miss " + near[0] if near else "not retrieved", it["pns"][0]))
        by[it["category"]][0] += ok
        by[it["category"]][1] += 1
        print(("ok  " if ok else "MISS"), f"#{it['id']} {it['category']:9s} {it['question'][:60]}")
    print({k: f"{a}/{b}" for k, (a, b) in by.items()}, f"TOTAL {sum(v[0] for v in by.values())}/{len(H)}")
    for n in notes:
        print("  part miss:", n)
