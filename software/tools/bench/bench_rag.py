#!/usr/bin/env python3
"""Realistic-prompt LLM benchmark: the real RoXaS system prompt plus ~2063 characters of retrieved manual text.
Reports prompt-processing speed, generation speed, total time and peak memory. Run on the Pi: python3 bench/bench_rag.py [model.gguf]"""
import re, subprocess, sys, time, os, shutil
from pathlib import Path
BENCH = Path(os.environ.get("BENCH_DIR", Path.home() / "bench"))
LLAMA = BENCH / "llama.cpp"; MODEL = Path(sys.argv[1]) if len(sys.argv) > 1 else BENCH / "models" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
PROMPT = "<|im_start|>system\nYou are RoXaS, the assistant in a 2004 Mazda RX-8. Answer ONLY from the CONTEXT below. Be brief: one or two sentences. Quote part numbers, codes and specs exactly as written in the context and say the source page. If the context says NOT FOUND or does not contain the answer, say you don't have that in the manuals. Never guess a part number.\n\nCONTEXT:\n[MANUAL 05Transmissions.pdf p26 - OIL SEAL (EXTENSION HOUSING)]\n…5. Apply the specified oil to the oil seal lip.\n 6. Install in the reverse order of removal.\n 7. Add transmission oil.\n\nMANUAL TRANSMISSION\nTRANSMISSION REMOVAL/INSTALLATION\n\n 1. Remove the engine cover.\n 2. Remove the battery cover.\n 3. Disconnect the negative battery cable.\n 4. Drain the transmission oil.\n 5. Remove in the order indicated in the table.\n 6. Install in the reverse order of removal.\n 7. Add transmission oil.\n\n (w) RX-8 Transmission (Manual & Auto)\n Page 26\n\n[MANUAL 05Transmissions.pdf p24 - TRANSMISSION/TRANSAXLE OIL]\nTRANSMISSION/TRANSAXLE OIL\nTRANSMISSION OIL INSPECTION\n\n 1. Position the vehicle on level ground.\n 2. Remove oil filler plug.\n\n 3. Verify that the oil is near the brim of the plug port.\n • If the oil is not near the brim of the plug port, add the specified amount and type of oil.\n\n Specified oil grade\n\n o API Service GL-4 or GL-5\n\n Specified oil viscosity\n\n o SAE 75W-90\n 4. Install oil filler plug and a new washer.\n\n Tightening torque\n\n o 27-48 N·m {2.8-4.9 kgf·m, 20-35 ft·lbf}\n\nTRANSMISSION OIL REPLACEMENT\n\n 1. Po\n\n[MANUAL 11Body.pdf p415 - OIL LEVEL SWITCH]\nOIL LEVEL SWITCH\nOIL LEVEL SWITCH INSPECTION\n\n 1. Disconnect the oil level switch connector.\n 2. Verify the continuity between the oil level switch terminals.\n • If the continuity is not as indicated in the tables, replace the oil level switch. (See OIL PAN\n REMOVAL/INSTALLATION .)\n\n (w) RX-8 Body\n Page 415\n\n[MANUAL 11Body.pdf p391 - (See OIL LEVEL SWITCH INSPECTION )]\n(See OIL LEVEL SWITCH INSPECTION )\n Fuel gauge sender unit\n7\n (See FUEL GAUGE SENDER UNIT INSPECTION )\n\nINSTRUMENT CLUSTER\nINSTRUMENT CLUSTER REMOVAL/INSTALLATION\n\nCAUTION:\n\n • When replacing the instrument cluster, the configuration procedure must be performed before removing\n the instrument cluster.Replacing the instrument cluster without performing the configuration procedure\n will result in system malfunction.\n\n 1. Perform the instrument cluster configuration when replacing it.(See INSTRUMENT CLUSTER\n CONFIGURA<|im_end|>\n<|im_start|>user\nHow do I check the manual transmission oil level?<|im_end|>\n<|im_start|>assistant\n"
exe = next((p for n in ("llama-completion", "llama-cli") for p in (LLAMA / "build" / "bin" / n, LLAMA / n) if p.exists()), None)
if not exe: sys.exit("no llama binary found under " + str(LLAMA))
extra = []
if exe.name == "llama-cli":
    h = subprocess.run([str(exe), "--help"], capture_output=True, text=True); h = h.stdout + h.stderr
    for f in ("-no-cnv", "--no-conversation", "-st"):
        if re.search(r"(^|[\s,])" + re.escape(f) + r"([\s,]|$)", h): extra = [f]; break
cmd = [str(exe), "-m", str(MODEL), "-p", PROMPT, "-n", "60", "-t", "4", "-c", os.environ.get("CTX", "2048"), "--no-display-prompt"] + extra
tbin = shutil.which("time") or ("/usr/bin/time" if os.path.exists("/usr/bin/time") else None)
if tbin: cmd = [tbin, "-v"] + cmd
for i in range(3):
    t = time.perf_counter(); r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL); dt = time.perf_counter() - t
    if r.returncode: e = (r.stderr or r.stdout); sys.exit(e[:400] + (' ... ' + e[-300:] if len(e) > 700 else e[400:]))
    o = r.stderr + r.stdout
    pe = re.search(r"prompt eval time\s*=\s*([\d.]+) ms\s*/\s*(\d+) tokens.*?([\d.]+) tokens per second", o)
    ge = re.findall(r"[^t] eval time\s*=\s*([\d.]+) ms\s*/\s*(\d+) (?:runs|tokens).*?([\d.]+) tokens per second", o)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", o)
    print(f"run {i+1}: total {dt:.2f}s | prompt {pe.group(2) if pe else '?'} tok at {pe.group(3) if pe else '?'} tok/s ({float(pe.group(1))/1000:.2f}s) | "
          f"gen {ge[-1][2] if ge else '?'} tok/s | peak RAM {int(rss.group(1))/1024:.0f} MB" if rss else f"run {i+1}: total {dt:.2f}s | prompt {pe.group(2) if pe else '?'} tok at {pe.group(3) if pe else '?'} tok/s | gen {ge[-1][2] if ge else '?'} tok/s")
