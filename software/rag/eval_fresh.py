# eval_fresh.py - FRESH TEST SET #4 (ids 301+). Written after the cross-read/embedding work; none of these questions were seen while tuning.
# DO NOT TUNE ON THIS SET. Run it once for a report; if something must be fixed, write a NEW set afterwards.
# Ground truth: part numbers read off catalog page images p34/p64/p66/p68 (NOT from the database); specs read from manual pages and
# checked against the page text before any test run; DTC meanings/causes from the DTC table (tests retrieval + wording, not extraction).
# usage: python3 eval_fresh.py <roxas.sqlite> <rag_dir> <out_eval_jsonl>
import sys, json, re, sqlite3
sys.path.insert(0, sys.argv[2])
from eval_retrieval import D, N

F = [
 # --- DTC ---
 D(301, "dtc", "What does P0327 mean?", ["low"], code="P0327"),
 D(302, "dtc", "scan tool shows P0481 - what is that?", ["cooling fan"], code="P0481"),
 D(303, "dtc", "What is DTC P0850?", ["neutral switch"], code="P0850"),
 D(304, "dtc", "What does P0101 indicate?", ["maf"], code="P0101"),
 D(305, "dtc", "Code P0500 came up, what's wrong?", ["vss"], code="P0500"),
 D(306, "dtc", "What does P2138 mean?", ["app sensor"], code="P2138"),
 D(307, "dtc", "What can cause P0139?", ["fuel pump"], code="P0139"),
 D(308, "dtc", "What are the causes of P0850?", ["neutral switch"], code="P0850"),
 N(309, "What does P0777 mean?", "not a code in the manuals"),
 N(310, "What does U1234 mean?", "not a code in the manuals"),
 # --- parts (ground truth from page images) ---
 D(311, "part", "What is the part number for the ignition coil?", [], pn=["N3H1-18-100"]),
 D(312, "part", "What is the part number for the starter?", [], pn=["N3H1-18-400"]),
 D(313, "part", "What is the part number for the alternator?", [], pn=["N3H1-18-300"]),
 D(314, "part", "What is the part number for the air flow sensor?", [], pn=["ZL01-13-215"]),
 D(315, "part", "What is the part number for the alternator voltage regulator?", [], pn=["Z599-18-W70"]),
 D(316, "part", "What is the part number for the standard trailing side spark plug?", [], pn=["N3H1-18-110A"]),
 D(317, "part", "What is the part number for the starter pinion?", [], pn=["N3H1-18-X25"]),
 D(318, "part", "What is the part number for the air cleaner?", [], pn=["N3H3-13-320F"]),
 N(319, "What is the part number for a Hondata fuel pump controller?", "aftermarket brand, not in catalog"),
 # --- specs and procedures from the manuals ---
 D(320, "spec", "What is the initial opening temperature of the thermostat?", ["80-84"], [["03EngineDetails.pdf", 66]]),
 D(321, "spec", "What is the standard spark plug gap?", ["1.15-1.25"], [["03EngineDetails.pdf", 220]]),
 D(322, "spec", "What torque should the wheel nuts be tightened to?", ["88-118"], [["07Brakes.pdf", 142]]),
 D(323, "spec", "What is the clutch pedal free play?", ["5-15"], [["05Transmissions.pdf", 34]]),
 D(324, "spec", "What is the standard parking brake lever stroke?", ["1-3"], [["07Brakes.pdf", 69]]),
 D(325, "spec", "What is the brake pedal height?", ["175"], [["07Brakes.pdf", 3]]),
 D(326, "spec", "How much play is allowed in the steering wheel?", ["0-30"], [["08Steering.pdf", 2]]),
 D(327, "spec", "At what temperature is the thermostat fully open?", ["95"], [["03EngineDetails.pdf", 66]]),
 D(328, "spec", "How do I inspect the parking brake lever stroke?", ["notches"], [["07Brakes.pdf", 69]]),
 D(329, "spec", "what force do I pull the parking brake lever with when checking the stroke", ["98"], [["07Brakes.pdf", 69]]),
 D(330, "spec", "rx8 lug nut torque?", ["88-118"], [["07Brakes.pdf", 142]]),
 D(331, "spec", "plug gap on the rx8", ["1.15"], [["03EngineDetails.pdf", 220]]),
 # --- should refuse ---
 N(332, "What is the towing capacity of the RX-8?", "not in these manuals"),
 N(333, "How do I install a turbo kit on the RX-8?", "aftermarket, not covered"),
 N(334, "What is the transmission fluid capacity of a Honda Civic?", "different vehicle"),
 N(335, "What tires do you recommend for autocross?", "opinion/aftermarket, not covered"),
 N(336, "How do I tune the ECU for more power?", "aftermarket tuning, not covered"),
]

if __name__ == "__main__":
    db = sqlite3.connect(sys.argv[1])
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[−–—‐‑]", "-", s)).lower()
    bad = 0
    for it in F:                      # sanity: spec answers must literally appear on the cited page
        for sf, pg in it["sources"]:
            t = db.execute("SELECT text FROM docs WHERE source_file LIKE ? AND page=?", (sf[:10] + "%", pg)).fetchone()
            if not t or not all(norm(m) in norm(t[0]) for m in it["must_contain"]):
                print("CHECK FAILED", it["id"], sf, pg, it["must_contain"]); bad += 1
    with open(sys.argv[3], "w") as f:
        for it in F: f.write(json.dumps(it) + "\n")
    print(len(F), "questions written;", bad, "failed source checks")
