# Tail lamp modules and the rules that apply

> This is research notes, not legal advice. The SAE figures below come from
> older editions of the standards that I found online, so check the current
> versions before relying on any number. The car is a show car that is not
> driven on public roads, but these rules set the target if it ever is.

## Architecture

One module per lamp (LTLCM and RTLCM), identical hardware and firmware with a
left/right strap pin.

- **Why per lamp:** LED data lines stay centimeters long (single-wire addressable
  data degrades over long runs), only power and the CAN pair travel to the
  trunk, a failure costs one lamp, and spares are interchangeable.
- **Controller:** classic ESP32 (8 RMT output channels) for 3 to 5 arrays per
  side. The S3 has 4 and would need a parallel-output driver.
- **CAN carries commands, not pixels.** About 200 LEDs per side at 30 fps is
  roughly 24 kB/s, and a 500 kbps bus tops out near 36 kB/s at 100% load.
  Messages: mode and animation ID, brightness, speed, color; a time-sync tick
  about every 100 ms; a heartbeat; status replies (faults, current, temperature).
- **Legal functions run locally** from hardwired factory brake, tail, turn,
  hazard, and reverse inputs, conditioned through optocouplers or
  divider-and-clamp inputs. They do not need CAN.
- **Watchdog:** if the heartbeat stops, drop to plain functions with animations off.
- **Show-mode interlock:** animation modes require a physical switch and a
  parked state.
- **Separate arrays** for legal functions and animation. If stop and turn share
  an array, stop must drop out while the turn flashes.
- **Open risk:** high-impedance LED loads can cause hyperflash or bulb-out
  warnings. Check the factory flasher circuit in the electrical manual.

## Federal rules (FMVSS 108, 49 CFR 571.108)

- **Area, vehicles under 80 in wide:** a single-compartment stop lamp or rear
  turn signal needs at least 50 cm2. With multiple compartments, each needs at
  least 22 cm2 and the combined area at least 50 cm2.
- **Visibility area:** stop lamps need 1250 mm2 of unobstructed area viewable
  from 45 degrees inboard to 45 degrees outboard, and taillamps 2 in2.
- **Brightness (SAE J586 / J585 texts I found):** stop lamp minimum 80 cd and
  maximum 300 cd; tail lamp maximum 18 cd. When a tail lamp is optically
  combined with a stop or turn lamp, the signal lamp must be at least 3x the
  tail lamp at every test point and 5x at the central test points. I did not
  pull turn-signal minimums.
- **Turn signal flashing:** 60 to 120 flashes per minute. Multiple lamps may
  flash together or sequentially in the direction of the turn.
- **Combined stop/turn:** if optically combined, the stop signal must not turn on
  while the turn signal is flashing.
- **The "impair" clause (S5.1.3):** no additional lamp may impair the
  effectiveness of required lighting. NHTSA has applied this to separate lamps
  that flash right after the stop lamps and to add-on lamps with flashing or
  sequential behavior near required signals. This is the limit on brake-light
  animations.

## Arkansas

Ark. Code section 27-36-215: tail lamps must be red and visible from 500 ft;
at least two, mounted 20 to 72 in off the ground; the plate lamp must be white,
and no other color of light may be displayed around the license plate. The
stop-lamp and turn-signal sections in the same chapter were not reviewed.

## Sources

- eCFR, 49 CFR 571.108: https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-571/subpart-B/section-571.108
- NHTSA interpretation on stop-lamp-adjacent flashing lamps: https://www.nhtsa.gov/interpretations/20856ztv
- NHTSA interpretation on turn-signal flashing arrangements: https://www.nhtsa.gov/node/130606
- NHTSA interpretation on add-on lamps near required signals: https://www.nhtsa.gov/interpretations/86-250
- Ark. Code section 27-36-215: https://us.vlex.com/vid/tail-lamps-and-reflectors-937125638
- SAE J585 and J586 archived texts: https://archive.org/stream/gov.law.sae.j585.1977/sae.j585.1977_djvu.txt and https://archive.org/stream/gov.law.sae.j586.1984/sae.j586.1984_djvu.txt
