#!/usr/bin/env python3
"""CM5 voice-stack benchmark: STT, LLM, TTS, then one chained pass.

Run on the CM5 after setup_bench.sh. Prints a markdown table and writes
results to ~/bench/results-<timestamp>.md and .json.
Uses only the standard library.

Notes
- Each timing is wall-clock for a whole command, so it includes model load.
  The real service keeps models resident, so --repeat shows warm numbers.
- Temperature and throttle state are sampled before and after, so a slow
  result can be matched against heat or power limits.
"""
import argparse, json, os, re, statistics, subprocess, sys, time
from pathlib import Path

BENCH = Path(os.environ.get("BENCH_DIR", Path.home() / "bench"))
WHISPER = BENCH / "whisper.cpp"
LLAMA = BENCH / "llama.cpp"
MODEL_LLM = BENCH / "models" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
VOICE = BENCH / "voices" / "en_US-lessac-medium.onnx"
PIPER_PY = BENCH / "venv" / "bin" / "python"

PROMPT = ("You are the assistant in a 2004 Mazda RX-8. "
          "In one short sentence, what does code P0300 mean?")
SPOKEN = "Check engine light is on. Code P0300, random misfire detected."


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def timed(cmd, **kw):
    t = time.perf_counter()
    r = sh(cmd, **kw)
    return time.perf_counter() - t, r


def vcgen(*args):
    r = sh(["vcgencmd", *args])
    return r.stdout.strip() if r.returncode == 0 else "n/a"


def snapshot():
    return {"temp": vcgen("measure_temp"), "throttled": vcgen("get_throttled")}


def find_bin(root, names):
    for n in names:
        for p in (root / "build" / "bin" / n, root / n):
            if p.exists():
                return p
    sys.exit(f"Missing binary {names} under {root}. Run setup_bench.sh first.")


def bench_stt(model, wav, threads, repeat):
    exe = find_bin(WHISPER, ["whisper-cli", "main"])
    mp = WHISPER / "models" / f"ggml-{model}.bin"
    times = []
    for _ in range(repeat):
        t, r = timed([str(exe), "-m", str(mp), "-f", str(wav),
                      "-t", str(threads), "-nt"])
        if r.returncode:
            sys.exit(r.stderr[-500:])
        times.append(t)
    return times


def llm_exe_and_flags():
    """llama.cpp keeps renaming its non-interactive options. Prefer llama-completion (one prompt, then exit);
    otherwise ask llama-cli's --help which of the known flags it still has."""
    try:
        return find_bin(LLAMA, ["llama-completion"]), []
    except SystemExit:
        pass
    exe = find_bin(LLAMA, ["llama-cli"])
    h = sh([str(exe), "--help"]); h = h.stdout + h.stderr
    for flag in ("-no-cnv", "--no-conversation", "-st"):
        if re.search(r"(^|[\s,])" + re.escape(flag) + r"([\s,]|$)", h):
            return exe, [flag]
    return exe, []


def bench_llm(threads, repeat, n_predict):
    exe, extra = llm_exe_and_flags()
    times, tps = [], []
    for _ in range(repeat):
        t, r = timed([str(exe), "-m", str(MODEL_LLM), "-p", PROMPT,
                      "-n", str(n_predict), "-t", str(threads),
                      "--no-display-prompt"] + extra, stdin=subprocess.DEVNULL)
        if r.returncode:
            sys.exit((r.stderr or r.stdout)[-500:])
        times.append(t)
        m = re.findall(r"([\d.]+) tokens per second", r.stderr + r.stdout)
        if m:
            tps.append(float(m[-1]))
    return times, tps


def bench_tts(repeat):
    out = BENCH / "tts_test.wav"
    times = []
    for _ in range(repeat):
        t, r = timed([str(PIPER_PY), "-m", "piper", "-m", str(VOICE),
                      "-f", str(out), "--", SPOKEN])
        if r.returncode:
            sys.exit(r.stderr[-500:])
        times.append(t)
    dur = sh(["soxi", "-D", str(out)]).stdout.strip()
    return times, float(dur) if dur else None


def fmt(xs):
    if not xs:
        return "n/a"
    return f"{statistics.median(xs):.2f}s (min {min(xs):.2f}, max {max(xs):.2f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default=str(WHISPER / "samples" / "jfk.wav"),
                    help="speech clip for STT; use a real ~4s car-cabin clip too")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--n-predict", type=int, default=48)
    a = ap.parse_args()

    before = snapshot()
    res = {"before": before, "stt": {}}

    for m in ("tiny.en", "base.en"):
        res["stt"][m] = bench_stt(m, a.wav, a.threads, a.repeat)
    res["llm_s"], res["llm_tps"] = bench_llm(a.threads, a.repeat, a.n_predict)
    res["tts_s"], res["tts_audio_s"] = bench_tts(a.repeat)
    res["after"] = snapshot()

    # Chained estimate: STT (tiny) + LLM + TTS, medians, cold-load included.
    chain = (statistics.median(res["stt"]["tiny.en"])
             + statistics.median(res["llm_s"])
             + statistics.median(res["tts_s"]))
    res["chain_estimate_s"] = chain

    lines = [
        f"# CM5 benchmark {time.strftime('%Y-%m-%d %H:%M')}",
        f"threads={a.threads} repeat={a.repeat} wav={a.wav}",
        f"before: {before}", f"after: {res['after']}", "",
        "| Stage | Median (min, max) | Notes |", "|---|---|---|",
        f"| STT tiny.en | {fmt(res['stt']['tiny.en'])} | whole command incl. model load |",
        f"| STT base.en | {fmt(res['stt']['base.en'])} | same |",
        f"| LLM Qwen2.5-0.5B Q4_K_M | {fmt(res['llm_s'])} | {a.n_predict} tokens; "
        f"{fmt([]) if not res['llm_tps'] else str(round(statistics.median(res['llm_tps']),1))+' tok/s'} |",
        f"| TTS Piper lessac-medium | {fmt(res['tts_s'])} | audio length {res['tts_audio_s']}s |",
        f"| Chained (tiny+LLM+TTS) | {chain:.2f}s | cold-load upper bound |",
    ]
    text = "\n".join(lines)
    print(text)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (BENCH / f"results-{stamp}.md").write_text(text + "\n")
    (BENCH / f"results-{stamp}.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
