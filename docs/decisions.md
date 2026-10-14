# Decision log

Status values: **decided**, **hypothesis** (needs verification on the car), **open**.

## 1. Fine-tune a small pretrained model, use RAG for facts
**Decided.** Start from Qwen2.5-0.5B-Instruct, not a blank model. Manuals supply
facts through retrieval. LoRA fine-tuning later teaches behavior (concise
answers, refusing when retrieval is empty, consistent tool calls). Training runs
on a laptop with an RTX 4060 under WSL2.

## 2. Exact data lives in SQLite
**Decided.** Parts and DTC tables hold verbatim values. Matching is exact and
keyword-based (FTS5), filtered by the car's build codes. The model never
generates part numbers.

## 3. One CAN node that can send, behind a hardware gate
**Decided.** One ESP32 plus one SN65HVD230 both receives and transmits, because
reading DTCs is a request. The transceiver's Rs pin is pulled high by default
(listen-only standby). Two series MOSFETs pull it low only when a dash
keyswitch and an ESP32 GPIO both say yes. See `can-tap.md`.

## 4. Two CAN controllers on the tap node
**Decided.** The ESP32's built-in controller (TWAI) handles the busy Mazda bus.
An MCP2515 over SPI handles the low-traffic private C3M bus.

## 5. Check-engine light detection from the bus
**Hypothesis.** Hobbyist projects that drive an RX-8 cluster report that the
engine computer sends the warning-light state in frame 0x420. The exact byte,
bit, and polarity are unverified for this car. Plan: capture the bus with the
gate closed from key-off to key-on (the bulb check toggles the flag).

## 6. MIL lags the fault, so poll as well
**Decided.** The MIL lights only after a fault is seen in consecutive drive
cycles, and pending codes appear earlier. A second trigger polls OBD-II
Mode 01 PID 01 for the stored-code count while the engine runs.

## 7. CPU-only voice stack on the CM5
**Decided.** whisper.cpp (tiny.en or base.en) for STT, the 0.5B model through
llama.cpp, Piper for TTS. No GPU. XTTSv2 and a PCIe GPU were considered and
dropped for now because of driver and power complexity.

## 8. All audio through the head unit's aux input
**Decided.** The factory head unit has no aux jack, so an adapter on its
CD-changer port provides one. All sources route through aux, and fading is done
in software on the hub.

## 9. One lamp module per tail lamp
**Decided.** Left and right modules (classic ESP32, 8 RMT channels) keep LED
data lines short, isolate failures, and share one firmware. CAN carries
commands and a time-sync tick, not pixels. Legal lamp functions run from
hardwired factory signals and do not need CAN.

## Open questions

- Where the push-to-talk button goes.
- Whether the head unit is the Bose or single-CD variant.
- Which CM5 RAM size and breakout board.
- Whether the factory turn-signal circuit has bulb-out detection that LED loads
  would upset.
- Two DTCs (P0128, P0302) appear only in the manual's summary table and need
  manual handling.
