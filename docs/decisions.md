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

**Hardware (decided).** Raspberry Pi CM5 with 4GB RAM and 32GB eMMC on the
KiCad CM5 IO board in a case kit, running Raspberry Pi OS Lite 64-bit
(Trixie), hostname RoXaS-CM5. Bootloader EEPROM updated. It uses the Cave
WiFi for the foreseeable future, so the car and bench share one network. An
NVMe drive for models, databases, and logs is planned once a spare is
available (enable PCIe in config.txt, keep the OS on eMMC).

**Measured (2026-11-23, CM5 4GB, 4 threads, cold, no throttling, 58 C):**
whisper.cpp tiny.en 2.2 s and base.en 5.1 s for an 11 s clip (includes model
load); Qwen2.5-0.5B Q4_K_M 29.9 tok/s generating 48 tokens from a short prompt
(2.3 s including load); Piper lessac-medium 1.3 s for 5.2 s of audio. Chained
tiny.en + LLM + TTS: 5.8 s, a cold-load upper bound. Not yet measured:
prompt processing with a real 2,000+ character retrieved context, peak memory,
and the embedding step. `bench/bench_rag.py` covers the first two.

## 8. All audio through the head unit's aux input
**Decided.** The factory head unit has no aux jack, so an adapter on its
CD-changer port provides one. All sources route through aux, and fading is done
in software on the hub.

## 9. One lamp module per tail lamp
**Decided.** Left and right modules (classic ESP32, 8 RMT channels) keep LED
data lines short, isolate failures, and share one firmware. CAN carries
commands and a time-sync tick, not pixels. Legal lamp functions run from
hardwired factory signals and do not need CAN.

## 10. Sohn adapter for oil metering, with a reservoir level alarm
**Decided (adapter).** Keep the factory oil metering pump (OMP) and use a Sohn
adapter with a separate 2-stroke oil reservoir, instead of deleting the OMP.
The ECU keeps metering normally, the sump runs full synthetic engine oil, and
only the 2-stroke oil is burned for apex seal lubrication. Adapter and
reservoir are ordered.

**Open (level alarm).** If the reservoir runs dry, nothing warns the driver and
the seals run unlubricated. Plan: a float switch in the reservoir wired to a
digital input on the ESP32 CAN node, raising a dash warning and a voice alert
over C³M. Sensor type, placement, wiring, and the C³M frame it reports on are
not chosen yet. The warning is informational only and must never gate engine
operation.

## 11. Parts data: verify against page images, not OCR alone
**Decided.** The parts catalog is scanned, and OCR gets only about 55% of rows
fully right. Part numbers are therefore never trusted from OCR alone:
- `data/verified_parts.json` holds rows I read from the page images. It is applied
  at DB build time and wins over OCR. 277 rows on 20 pages are verified so far.
- Unverified rows get a normalizer (Mazda part numbers never contain O or I;
  rare prefixes snap to a common one by one confusable character).
- Part numbers and DTC meanings are answered by code (`answer.deterministic`),
  not by the LLM. A part number not in the DB is refused, never invented.
- Rows without a verified flag are answered with a hedge ("closest rows").
Open: about 2,000 rows are still unverified. The verification sheet
(`data/derived/verify2/index.html`) lists pages most useful first.

## 12. Retrieval: FTS5 plus small dense embeddings
**Decided.** bm25 over SQLite FTS5 fused with bge-small-en-v1.5 embeddings
(384-d, about 2 MB) by reciprocal-rank fusion at weight 0.5. Weight 1.0 caused
over-refusals. Embeddings must be built on the PC; the runtime only embeds the
question. On the CM5 the query embedding runs through onnxruntime (no torch):
16 ms warm per question, 278 MB peak RAM, and the top-3 chunk ids match the PC's
sentence-transformers results exactly (`bench/bench_embed.py`,
`tools/embed_check.py`, 2026-11-23).

## 13. Model of record: run 1 LoRA, Q4_0
**Decided (2026-11-23).** Qwen2.5-0.5B-Instruct plus LoRA (behavior only),
merged and quantized with llama.cpp. Shipping file: Q4_0. Q4_K_M (398 MB) was
the first export, but its hidden size (896) does not divide into 256-wide
blocks, so 144 of 290 tensors fell back to slower formats. On the CM5 with a
real 700-token RAG prompt, Q4_K_M read the prompt at 90 tok/s (10.8 s total);
Q4_0 reads at 305 tok/s (4.7 s total), generation about 28 tok/s either way. The llama.cpp process peaked at
1,144 MB with its default 32k context window and 782 MB with -c 2048 (measured
with /usr/bin/time -v); the service must set -c 2048.
Eval on the three tuning sets: float 76, Q4_K_M 75, Q4_0 74 (no invented part
numbers); within run-to-run noise.
- Eval on three tuning sets (81 questions): float 76, Q4_K_M 75, no invented
  part numbers in either. The fresh set (36 questions, used once) scored 34.
- Later retrains (run 2 with 25 procedure examples, run 3 with 24 more refusal
  examples) scored 73-74 and were not adopted. The extra data did not help and
  the remaining misses are retrieval and table-extraction problems, not behavior.
- Known misses: invented transmission oil-level steps, apex seal height and
  backlash (tables flattened in the extracted text), fuel injector resistance
  retrieval.
Open: CM5 speed and memory with this model (see decision 7).

## 14. Spoken-answer style and an owner web console

Answers are written to be heard, not read. Source pages are left out unless
asked ("what page is that on?"), specs read imperial first with metric on
request ("what's that in metric?"), and anything not found says "I don't see
that listed in my database" (never "the manuals"). A verified part is offered
first ("Yep, I sure do. You ready for it?") and recited on a yes. Questions
too vague to search ("any bolts?") get a clarifying question instead of
reaching the model, which would otherwise invent an answer from stray context.
Model refusals are replaced in code with one of a few fixed lines, so the
model's system prompt stays byte-identical to its training data.

Hand edits (checked parts, added rows, custom prompt/reply table) are made in
a password-protected web console on the Pi and stored in `user.sqlite`, not in
`roxas.sqlite`. The database is rebuilt and redeployed from the manuals; the
edits are re-applied on top at startup, so a deploy never loses work. The
console's command box is an allow-list, not a shell. The custom reply table has
an `action` field reserved for CAN-bus commands; it is stored but not executed.

## Open questions

- Where the push-to-talk button goes.
- Whether the head unit is the Bose or single-CD variant.
- Whether the factory turn-signal circuit has bulb-out detection that LED loads
  would upset.
- Two DTCs (P0128, P0302) appear only in the manual's summary table and need
  manual handling.
- Reservoir float switch details for decision 10: switch type, mounting,
  wiring, and which C3M frame carries the low-oil state.
- Which 2-stroke oil to run (low-ash synthetic, JASO FD / ISO-L-EGD class, or
  whatever the adapter maker specifies).
- Headlamp bulb ambiguity: a "headlight bulb" question ranks the 21 W bulb
  first; ask which bulb, or tag rows by lamp position.
- Run RoXaS and the web console as boot-time services (also needed for the
  console's restart commands); wire in speech-to-text and Piper.
- Pull `export parts` from the Pi back into `data/verified_parts.json`.
- Eval sets are all burned for tuning; write a fifth set before the next
  model decision.
