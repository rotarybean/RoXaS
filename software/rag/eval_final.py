# eval_final.py - FINAL TEST SET (ids 201+). Written after the spec table and answer path existed. DO NOT TUNE ON THIS SET.
# Run it for a report, change nothing in response to individual failures; if a fix is needed, write a NEW set afterwards.
# Part-number ground truth was read off the catalog page images (p36, p49, p265), NOT from the database.
# usage: python3 eval_final.py <roxas.sqlite> <rag_dir> <out_eval_jsonl>
import sys, json, re, sqlite3
sys.path.insert(0, sys.argv[2])
from eval_retrieval import D, N

R = "RENESIS Rotary Engine Workshop Manual.pdf"
F = [
 # --- DTC (meaning / causes / unknown / phrasing) ---
 D(201, "dtc", "What does P0171 mean?", ["too lean"], code="P0171"),
 D(202, "dtc", "What is DTC P0335?", ["eccentric shaft"], code="P0335"),
 D(203, "dtc", "My scan tool says P0112, what does that indicate?", ["iat"], code="P0112"),
 D(204, "dtc", "What does U0100 mean?", ["tcm"], code="U0100"),
 D(205, "dtc", "check engine light came on, code p0301 - what is it", ["misfire"], code="P0301"),
 D(206, "dtc", "What can cause P0172?", ["fuel pump"], code="P0172"),
 D(207, "dtc", "What are the possible causes of P0446?", ["connector"], code="P0446"),
 N(208, "What does DTC P0999 mean?", "not a code in the manuals"),
 N(209, "What does U9999 mean?", "not a code in the manuals"),
 # --- parts (ground truth from page images) ---
 D(210, "part", "What is the part number for the radiator cap?", [], pn=["D316-15-205"]),
 D(211, "part", "What is the part number for the radiator drain cock?", [], pn=["NF01-15-203"]),
 D(212, "part", "What is the part number for the coolant reserve tank?", [], pn=["N3H1-15-350C"]),
 D(213, "part", "What is the part number for the air cleaner element?", [], pn=["N3H1-13-Z40"]),
 D(214, "part", "What is the part number for the left front wiper blade?", [], pn=["DC20-67-330"]),
 D(215, "part", "What is the part number for the passenger side wiper arm?", [], pn=["FE02-67-321"]),
 N(216, "What is the part number for a Skunk2 intake manifold?", "aftermarket brand, not in catalog"),
 # --- specs and procedures from the narrative manuals ---
 D(217, "spec", "What is the standard battery electrolyte gravity?", ["1.27-1.29"], [["03EngineDetails.pdf", 205], ["03EngineDetails.pdf", 324]]),
 D(218, "spec", "What is the standard voltage when checking the keyless transmitter battery?", ["2.7"], [["11Body.pdf", 337]]),
 D(219, "spec", "How full should the coolant reserve tank be after refilling?", ["F mark"], [["03EngineDetails.pdf", 54]]),
 D(220, "spec", "What torque do I use on the brake caliper bleeder screw?", ["6.9-9.8"], [["07Brakes.pdf", 2]]),
 D(221, "spec", "What is the fuel injector resistance?", ["13.8"], [["03EngineDetails.pdf", 324]]),
 D(222, "spec", "What is the maximum rotor housing width difference?", ["0.06"], [[R, 68]]),
 D(223, "spec", "What is the minimum apex seal height?", ["4.3"], [[R, 68]]),
 D(224, "spec", "What is the maximum wheel bearing play on the front axle?", ["0.05"], [["06DriveTrain.pdf", 43]]),
 D(225, "spec", "What should the generator rotor resistance be between the slip rings?", ["1.6-2.0"], [["03EngineDetails.pdf", 324]]),
 D(226, "spec", "What is the minimum remaining tire tread?", ["1.6"], [["09Suspension.pdf", 71]]),
 D(227, "spec", "What is the maximum radial runout for a wheel and tire?", ["1.5"], [["09Suspension.pdf", 71]]),
 D(228, "spec", "How do I check the manual transmission oil level?", ["brim"], [["05Transmissions.pdf", 24]]),
 D(229, "spec", "What is the standard backlash between the drive pinion and ring gear?", ["0.09-0.11"], [["06DriveTrain.pdf", 43]]),
 D(230, "spec", "What current does cooling fan No.1 draw?", ["8.9-11.9"], [["03EngineDetails.pdf", 324]]),
 D(231, "spec", "What do I check when inspecting a seat belt?", ["damage"], [["12Safety.pdf", 156]]),
 # --- casual phrasing ---
 D(232, "spec", "rx8 coolant capacity?", ["8.7"], [["03EngineDetails.pdf", 324]]),
 D(233, "spec", "how much air do I put in the tires", ["220"], [["09Suspension.pdf", 71]]),
 D(234, "spec", "what oil do I use in the engine", ["5W-20"], [["03EngineDetails.pdf", 323]]),
 # --- should refuse ---
 N(235, "What boost pressure does the stock turbo run?", "no turbo on this car"),
 N(236, "How do I install a Skunk2 intake manifold?", "aftermarket, not covered"),
 N(237, "What is the engine oil capacity of a Miata?", "different vehicle"),
 N(238, "How do I pair a Bluetooth phone with the head unit?", "not in these manuals"),
 N(239, "What is a good aftermarket exhaust for more horsepower?", "aftermarket advice, not covered"),
]

if __name__ == "__main__":
    db = sqlite3.connect(sys.argv[1])
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[−–—‐‑]", "-", s)).lower()
    bad = 0
    for it in F:   # authoring check: every must_contain string must appear on one of its claimed source pages
        if it["answerable"] and it["sources"]:
            txt = ""
            for f, p in it["sources"]:
                r = db.execute("SELECT text FROM docs WHERE source_file=? AND page=?", (f, p)).fetchone()
                txt += " " + norm(r[0]) if r else ""
            for m in it["must_contain"]:
                if norm(m) not in txt: print("GROUND TRUTH NOT FOUND", it["id"], m); bad += 1
    with open(sys.argv[3], "w") as f:
        for it in F: f.write(json.dumps(it) + "\n")
    print(len(F), "questions,", bad, "ground-truth problems")
