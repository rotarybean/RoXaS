#!/usr/bin/env bash
# Build the three voice-stack components on the CM5 and fetch test models.
# Run on the Pi (Raspberry Pi OS Lite, 64-bit) as your normal user.
# Everything lands in ~/bench. Safe to re-run.
set -euo pipefail

BENCH="${BENCH_DIR:-$HOME/bench}"
mkdir -p "$BENCH" && cd "$BENCH"

sudo apt-get update
sudo apt-get install -y git cmake build-essential python3-venv python3-pip \
    libsndfile1 sox alsa-utils curl

# --- whisper.cpp (STT) ---
[ -d whisper.cpp ] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp
( cd whisper.cpp
  cmake -B build -DCMAKE_BUILD_TYPE=Release
  cmake --build build -j4 --config Release
  for m in tiny.en base.en; do
      [ -f "models/ggml-$m.bin" ] || bash models/download-ggml-model.sh "$m"
  done )

# --- llama.cpp (LLM) ---
[ -d llama.cpp ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp
( cd llama.cpp
  cmake -B build -DCMAKE_BUILD_TYPE=Release
  cmake --build build -j4 --config Release )
mkdir -p models
if [ ! -f models/qwen2.5-0.5b-instruct-q4_k_m.gguf ]; then
    curl -L -o models/qwen2.5-0.5b-instruct-q4_k_m.gguf \
      https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
fi

# --- Piper (TTS) ---
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install piper-tts
mkdir -p voices
./venv/bin/python -m piper.download_voices en_US-lessac-medium --data-dir voices || \
    echo "Voice download failed: check current Piper docs for the download command."

echo "Setup done. Next: python3 run_bench.py"
