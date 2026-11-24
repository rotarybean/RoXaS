# eval_retrieval.py - the 25-question RoXaS eval set + retrieval-only scoring.
# usage: python3 eval_retrieval.py <roxas.sqlite> <rag_dir> <out_eval_jsonl>
# Each item says what a correct answer must contain and where the evidence is, so a failure can be
# classified: RETRIEVAL failure (evidence not in what we hand the model) vs GENERATION failure
# (evidence was there, answer still wrong). Generation scoring is run separately with the real model.
import sys, json, sqlite3
sys.path.insert(0, sys.argv[2])
from rag import retrieve

def D(i, cat, q, must, src=None, code=None, pn=None, check=False):
    return dict(id=i, category=cat, question=q, answerable=True, must_contain=must,
                sources=src or [], dtc=code, pns=pn or [], needs_human_check=check)

def N(i, q, note):
    return dict(id=i, category="refuse", question=q, answerable=False, must_contain=[], sources=[], dtc=None,
                pns=[], needs_human_check=False, note=note)

E = [
 D(1, "dtc", "What does P0301 mean?", ["front rotor", "misfire"], code="P0301"),
 D(2, "dtc", "My code reader shows P0420. What is that?", ["catal"], code="P0420"),
 D(3, "dtc", "What does U0121 mean?", ["ABS"], code="U0121"),
 D(4, "dtc", "What is DTC P0128?", ["thermostat"], code="P0128"),
 D(5, "dtc", "What does P0302 mean?", ["rear rotor", "misfire"], code="P0302"),
 D(6, "dtc_causes", "What can cause P0301?", ["ECT sensor"], code="P0301"),
 D(7, "dtc_causes", "What are the possible causes of a P0420?", ["purge"], code="P0420"),
 D(8, "spec", "What temperature does the thermostat start to open at?", ["80-84"], [["03EngineDetails.pdf", 66], ["03EngineDetails.pdf", 324]]),
 D(9, "spec", "How much oil does an oil change take, without changing the filter?", ["3.3"], [["03EngineDetails.pdf", 32], ["03EngineDetails.pdf", 323]]),
 D(10, "spec", "What engine oil viscosity does the RX-8 use?", ["5W"], [["03EngineDetails.pdf", 32], ["03EngineDetails.pdf", 323]]),
 D(11, "spec", "How much gear oil goes in the manual transmission?", ["1.75"], [["05Transmissions.pdf", 25]]),
 D(12, "spec", "What gear oil grade does the transmission take?", ["GL-4"], [["05Transmissions.pdf", 25]]),
 D(13, "spec", "What is the standard spark plug gap?", ["1.15"], [["03EngineDetails.pdf", 220]]),
 D(14, "spec", "What torque do the lug nuts get?", ["89"], [["09Suspension.pdf", 71]]),
 D(15, "spec", "What is the tightening torque for the transmission oil filler plug?", ["27"], [["05Transmissions.pdf", 25]]),
 D(16, "procedure", "How do I bleed the clutch hydraulic system?", ["bleed"], [["05Transmissions.pdf", 2], ["05Transmissions.pdf", 3], ["05Transmissions.pdf", 9], ["05Transmissions.pdf", 12]]),
 D(17, "procedure", "How do I remove and install the thermostat?", ["thermostat"], [["03EngineDetails.pdf", 63], ["03EngineDetails.pdf", 64], ["03EngineDetails.pdf", 65]]),
 D(18, "procedure", "Where are the correct jacking points?", ["jack"], [["01Info.pdf", 29]]),
 D(19, "procedure", "What precautions apply when removing a spark plug?", ["spark plug"], [["03EngineDetails.pdf", 219]]),
 D(20, "part", "What is the part number for the thermostat?", [], pn=["N3H1-15-170A", "N3H1-15-171"], check=True),
 D(21, "part", "What is the part number for the clutch master cylinder?", [], pn=["FE05-41-990A"], check=True),
 D(22, "part", "What is the part number for the clutch release fork?", [], pn=["N317-16-520"], check=True),
 N(23, "What torque do the bolts on my Sohn oil metering adapter get?", "Sohn adapter is not in any manual"),
 N(24, "What does DTC P9999 mean?", "not a code in the manuals"),
 N(25, "What is the part number for a Sohn adapter?", "aftermarket, not in the catalog"),
]

def hit(item, res, k):
    if not item["answerable"]:
        return bool(res["codes_missing"] or res["unmatched"])          # refusal signal present
    if item["dtc"]:
        return any(d["code"] == item["dtc"] for d in res["dtc"])
    if item["pns"]:
        return any(p["part_number"] in item["pns"] for p in res["parts"][:k])
    got = {(d["source"], d["page"]) for d in res["docs"][:k]}
    return any(tuple(s) in got for s in item["sources"])

if __name__ == "__main__":
    db = sqlite3.connect(sys.argv[1])
    with open(sys.argv[3], "w") as f:
        for it in E:
            f.write(json.dumps(it) + "\n")
    import collections
    by = collections.defaultdict(lambda: [0, 0])
    for it in E:
        res = retrieve(db, it["question"], k=5)
        ok = hit(it, res, 5)
        by[it["category"]][0] += ok
        by[it["category"]][1] += 1
        flag = "ok  " if ok else "MISS"
        top = (res["docs"][0]["source"], res["docs"][0]["page"]) if res["docs"] else (res["parts"][0]["part_number"] if res["parts"] else "-")
        print(f"{flag} #{it['id']:2d} {it['category']:10s} {it['question'][:58]:58s} top={top} unmatched={res['unmatched']}")
    tot = sum(v[0] for v in by.values()); n = sum(v[1] for v in by.values())
    print({k: f"{a}/{b}" for k, (a, b) in by.items()}, f"TOTAL {tot}/{n}")
