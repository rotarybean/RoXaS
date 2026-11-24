# CM5 voice-stack benchmark

Measures speech-to-text, the 0.5B LLM, and text-to-speech on the Compute
Module 5, then adds them up. Run it on the Pi, not on your PC.

```
bash setup_bench.sh        # about 20-30 min: builds whisper.cpp and llama.cpp
python3 run_bench.py       # about 2-5 min
```

Read the results as "how long until the car starts answering". The chained
number includes model load, so it is a worst case. A resident service will be
faster. Record the numbers in docs/decisions.md under decision 7.

Run it twice: once cold (right after boot) and once after the board has been
busy for 10 minutes, to see heat throttling. A nonzero `throttled` value
means the Pi hit a power or temperature limit.

Test with a real clip too: record 4 seconds of yourself in the car and pass
it with `--wav`. whisper.cpp wants 16 kHz mono WAV
(`sox in.wav -r 16000 -c 1 out.wav`).

Untested: written without access to the hardware. Binary names and flags
follow current whisper.cpp, llama.cpp and Piper conventions, which change.
Fix them in run_bench.py if a command errors.
