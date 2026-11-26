# Safety and scope

This is a hobby project for a **show car that is not driven on public roads**.
It is provided as-is, with no warranty (see LICENSE). The function classes
below exist so each custom function can still be judged on its own if that ever
changes. The full function list is in `docs/functions.md`.

## What this project does not touch

- It does not modify the software, wiring or configuration of the factory PCM,
  BCM, ABS module, or steering modules.
- The LLM and voice software never have raw access to either CAN bus. They only
  pick a name from a **command registry**. Code validates the name and sends a
  fixed, pre-approved message on the private C3M bus.
- Locks, trunk and windows are driven by the fob subsystem or private-bus relay
  modules. No unlock or immobilizer frames are sent to the Mazda bus.

## Stated exceptions

- **Passenger airbag module:** removed by the owner. The service manual gives
  removal steps and the expected resistance of each passenger inflator circuit
  (about 1.4 to 2.9 ohms; confirm on the page), but no procedure for running
  without the module. Any substitute load for the SRS unit must be worked out
  and verified on the bench with a diagnostic tool, not assumed. Follow the
  manual's battery-disconnect wait and handle the live module face away from
  the body.
- **Brake-line valves:** solenoid valves are added in the individual brake lines
  between the ABS module and the calipers. This is a separate hydraulic system
  with its own controller. It does not connect to CAN and is not controlled by
  the hub, the WebUI or voice (see rule 6).
- **ECM work:** bi-directional access to the Mazda bus is kept for future ECM
  programming. It is deferred and has its own rules (see rule 2).

## Design rules

1. **Transmit on the Mazda bus is gated in hardware.** The CAN transceiver's Rs
   pin defaults to listen-only standby. Transmission needs a dash lockout switch
   *and* a firmware signal from the bridge ESP32. Any single fault leaves it
   silent. A dash indicator shows the real transceiver state.
2. **The bridge works in tiers.**
   - Gate closed: listen only.
   - Gate open: only the whitelisted read-only diagnostic requests listed in
     `docs/can-tap.md`.
   - Programming mode (future ECM work): separate, off the voice and LLM path,
     with its own whitelist and entry rules written before any work starts.
3. **Fail to plain.** Lighting modules fall back to plain stop, turn and reverse
   function if the C3M link or the hub goes away, or the web console is down.
4. **Show mode is a per-function setting, enforced on each node.**
   - Class **C** (cosmetic): the WebUI toggle is the only gate.
   - Class **L** (legal-critical: stop, turn, tail, reverse, center high-mount
     stop lamp): the WebUI toggle only means "allowed". It runs only with the
     physical show-mode switch on and the car parked.
   - Every function defaults to off. The owner decides each function's class.
5. **The center stop lamp is always a steady red stop lamp when the brake is
   applied.** Text and animation appear only in show mode while parked.
6. **ABS valves are Class H and stay out of the WebUI.** They use their own
   hardware interlock and are normally open, so a power loss, crashed
   controller or cut wire leaves stock braking. They send status only to the
   hub, for audible and visual feedback. They are bench-tested and fail-safed
   before installation, including how the ABS/DSC module reacts to changed
   caliper-side pressure.
7. **Power and heat.** Every branch off the trunk power rail has its own fuse.
   Underhood and exhaust-area lighting uses high-temperature parts, with LEDs
   kept away from exhaust tips.
8. **The oil reservoir level alarm is informational only.** It must never gate
   engine operation.

## If you build something similar

Automotive lighting and electrical work have legal and safety consequences.
Read `docs/lighting.md` for the federal and state rules I found, and verify
them yourself against current sources. Nothing here is legal or engineering
advice.
