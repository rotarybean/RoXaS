# Safety and scope

This is a hobby project for a **show car that is not driven on public roads**.
It is provided as-is, with no warranty (see LICENSE).

## What this project does not touch

- It does not modify or replace the factory PCM, BCM, ABS, airbag, or steering
  modules.
- It does not write to vehicle systems. The only frames the CAN tap node can
  ever transmit are a short whitelist of **read-only** OBD-II diagnostic
  requests (see `docs/can-tap.md`).
- The voice/LLM software never has raw access to the CAN bus.

## Design rules

1. **Transmit is gated in hardware.** The CAN transceiver's Rs pin defaults to
   listen-only standby. Transmission needs a dash keyswitch *and* a firmware
   signal. Any single fault leaves it silent.
2. **Fail to plain.** Lighting modules fall back to plain stop/turn/reverse
   function if the C3M link or the CM5 goes away.
3. **Show-mode lockout.** Animation modes are enabled only by a physical
   switch while parked.

## If you build something similar

Automotive lighting and electrical work have legal and safety consequences.
Read `docs/lighting.md` for the federal and state rules I found, and verify
them yourself against current sources. Nothing here is legal or engineering
advice.
