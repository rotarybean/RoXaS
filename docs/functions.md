# Function list

Every function the C3M project plans, where it runs, how it is gated, and how
far along it is. This is a living list: new functions get a row here before any
firmware or wiring is built.

> Nothing here has run on the car yet. Anything marked **Hypothesis** or **Idea**
> is unverified. The car is a show car that is not driven on public roads; the
> function classes below exist so each function can still be judged on its own
> if that ever changes.

## How to read this list

**Status:** Built, Designed (documented, not built), Idea (discussed, not
designed), Open (a decision is missing), Deferred.

**Class** (decides how the show-mode toggle works; see "Show-mode framework"):

| Class | Meaning | Gate to run in show mode |
|---|---|---|
| **C** Cosmetic | Appearance or comfort only. No legal lamp function. | WebUI toggle |
| **L** Legal-critical | Touches a lamp or signal the law regulates (stop, turn, tail, reverse, center high-mount stop lamp). | WebUI "allowed" **and** physical show-mode switch **and** parked |
| **H** Hardware-gated | Can send on a vehicle bus or affect braking. | Its own hardware interlock. **Not** controllable from the WebUI |
| **V** Voice/info | Software only, on the hub. | Not applicable |

## Nodes

| Node | Hardware | Bus |
|---|---|---|
| Hub | Raspberry Pi CM5 (4 GB) | C3M CAN via USB-CAN adapter |
| Bridge | ESP32 near the OBD-II port, SN65HVD230 on the Mazda bus | Mazda HS-CAN and C3M CAN |
| Lighting nodes (8) | ESP32, one each (see section 3) | C3M CAN |
| ABS valve controller | Its own controller, separate system | None to the Mazda bus; status only to the hub |
| Fallback compute | Full PC with RTX 2070, to be installed in the car if the CM5 is too slow | Ethernet and C3M CAN |

The Mazda bus and the C3M bus never touch electrically. The bridge is the only
crossing point.

## 1. Hub (CM5)

| ID | Function | Class | Status | Notes |
|---|---|---|---|---|
| F-101 | Push-to-talk voice Q&A (whisper.cpp, Qwen2.5-0.5B + LoRA, Piper) | V | Parts benchmarked, not wired | Button likely in the steering wheel, decided at integration |
| F-102 | Parts and DTC answers from SQLite, by code, never generated | V | Built (database, eval 25/25) | Invented part numbers are refused |
| F-103 | This car's own figures (`vehicle_specs`) | V | Built | VIN kept in the private table only |
| F-104 | Music fade and duck around voice prompts | V | Designed | All audio via head-unit aux; see `voice-audio.md` |
| F-105 | Spoken DTC announcements | V | Designed | Needs the bridge and F-201 to F-203 |
| F-106 | Spoken C3M health alerts (module offline, heartbeat lost, bus errors) | V | Idea | Same alert path as F-105 |
| F-107 | Voice commands with spoken confirmation, from a **named command registry** | V | Idea | The model only picks a command name. It never builds a CAN frame. Code validates and sends |
| F-108 | Owner WebUI (parts, replies, console) | V | Built on PC, not yet on the Pi | Password protected. Hosts the show-mode registry (F-108a) |
| F-108a | Show-mode registry and toggles | V | Designed here | See "Show-mode framework" |
| F-109 | Boot-time services for console and voice | V | Deferred | Needs `systemd --user` |
| F-110 | HUD data feed | V | Idea | See section 4 |
| F-111 | Passenger terminal (screen and keyboard) | V | Idea | Passenger airbag module is being removed, so the dash panel can carry it. Terminal gets a shell on the hub but no path around the Mazda-bus gate |
| F-112 | Key fob subsystem for lock, unlock, trunk | C | Idea | A fob integrated into the hub or a private-bus subsystem. No unlock or immobilizer frames ever go to the Mazda bus. The factory immobilizer is left alone |
| F-113 | Door-ajar audio (selectable, loopable, replaces the factory chime) | C | Idea | Pi or equivalent. Door-ajar input source TBD (hardwired switch or private bus) |
| F-114 | Windows, trunk and lock control by voice or WebUI | C | Idea | Likely relay modules on the private bus if the factory circuits are hardwired. Check the electrical manual before committing |
| F-115 | Model upgrade path: move the LLM and conversation to the in-car RTX 2070 PC, repurpose the CM5 | V | Deferred | Cross that bridge only if the CM5 proves too slow |

## 2. Bridge (ESP32 near the OBD-II port)

Rule: it listens to the Mazda bus and reports relevant data to the hub. It sends
on the Mazda bus **only** when the dash lockout switch is on **and** the ESP32
pin agrees. The dash indicator light shows the real transceiver state.

| ID | Function | Class | Status | Notes |
|---|---|---|---|---|
| F-201 | Listen-only logging and forwarding to the hub | H | Stub firmware | Gate closed, nothing can transmit |
| F-202 | Check-engine light detection (frame 0x420 flag) | H | **Hypothesis** | Byte, bit and polarity unverified for this car. Capture key-off to key-on |
| F-203 | MIL-lag polling (Mode 01 PID 01 for the stored-code count) | H | Designed | Pending codes show before the light |
| F-204 | Gated read-only diagnostic requests (0x7DF, services 01, 03, 07, 0A; ISO-TP flow control to 0x7E0) | H | Designed | Transmit whitelist in `can-tap.md` |
| F-205 | Bi-directional pass-through for future ECM programming | H | Deferred | Separate "programming mode", off the voice and LLM path. The hub acts as the tool. Needs its own whitelist and gate rules before any work starts |
| F-206 | Oil reservoir low-level alarm (float switch on the 2-stroke reservoir) | H | Open | Informational only. Must never gate engine operation. Switch type, mounting, wiring and C3M frame not chosen |

### Signals the bridge needs to forward (all unverified)

| Signal | Used by | Status |
|---|---|---|
| Engine RPM | Underhood animation, HUD | Hypothesis |
| Vehicle or wheel speed | Side-vent images, HUD | Hypothesis |
| Warning-light state (MIL) | F-105 | Hypothesis (0x420) |
| Coolant temperature, other HUD values | HUD | Not started |

Each signal needs its frame ID, byte layout, scaling and update rate confirmed
from a real capture before any module depends on it.

## 3. Lighting nodes (C3M CAN, one ESP32 each)

Principles: CAN carries commands and sync ticks, not pixels. Each node renders
locally, checks its own show-mode permission, and defaults to plain or off on
boot or when the hub heartbeat stops. No light source is visible: LEDs are
hidden behind prints, diffusers or housings.

| ID | Node | Function | Class | Status | Notes |
|---|---|---|---|---|---|
| F-301 | Left side vent | Image and text display in the fender vent insert | C | Idea | See "Side-vent display" |
| F-302 | Right side vent | Same, mirrored | C | Idea | One firmware, left/right strap pin |
| F-303 | Underglow | Underglow plus wheel-well lighting, individually addressable | C | Idea | One node for the whole system |
| F-304 | Left brake lamp | Animated stop, turn and tail with legal functions on separate arrays | **L** | Designed | See `lighting.md`. Plain function runs from the factory signals, with no CAN needed |
| F-305 | Right brake lamp | Same | **L** | Designed | Same |
| F-306 | Center dot-matrix lamp | Red dot-matrix replacing the center high-mount stop lamp | **L** | Idea | Steady red whenever the brake is applied. Text and animation only in show mode, parked |
| F-307 | Underhood | Hidden addressable LEDs, later synced to RPM to suggest rotor motion | C | Idea | Light shows through hood seams and onto the ground. It represents RPM, not true rotor position |
| F-308 | Gauge cluster | Addressable RGB backlight inside the factory cluster | C | Idea | Factory warning indicators keep their stock colors |

### Side-vent display (F-301, F-302)

Printed ABS fender-vent inserts with LEDs behind a white or light print. A viewer
fixed on one point sees text or imagery as the car passes, like a spinning LED
bar. Design points:

- Advance image columns by **distance travelled**, not time, so the image keeps
  its width at any speed. This needs a steady speed feed to both vent nodes.
- Use clocked LEDs (APA102 or SK9822 type) for clean high-rate updates.
- A hidden source behind a plain print blurs the columns. Expect to need a thin
  slit mask and a diffuser.
- Image width is columns times pitch per distance, so check legibility against
  the vent size before printing.

### Heat and wiring (all lighting)

- Underhood and exhaust-area parts need silicone-encased or high-temp strips.
- Exhaust tip rings probably need light pipes or fiber with the LEDs kept away
  from the tip.
- Each branch off the trunk rail gets its own fuse. Build a power budget table:
  addressable LEDs draw up to about 60 mA each at full white.

## 4. Interior, trunk and other hardware

| ID | Function | Class | Status | Notes |
|---|---|---|---|---|
| F-401 | Interior lamps replaced with red LEDs (overhead console lamps excluded) | C | Idea | Plain swap, no node |
| F-402 | HUD insert in the center console (car has no navigation screen) | V | Idea | Shows data the cluster lacks or shows vaguely, plus custom data: weather, C3M module health, more over time. Content list is open |
| F-403 | Passenger-side screen and keyboard in the dash panel | V | Idea | See F-111. Passenger airbag module removed |
| F-404 | Passenger airbag module removal | n/a | Planned | The SRS unit will flag the missing module. Use the factory-specified dummy load from the 12 Safety section of the service manual |
| F-405 | Trunk power distribution: isolated rail with step-up and step-down supplies | n/a | Idea | Fused feed from the battery. Per-branch fuses. Keep LED return currents away from CAN nodes |
| F-406 | Exhaust tip rings, RGB plus IR | C | Idea | IR is for later object tracking by external systems. Deferred. Needs heat isolation |

## 5. ABS valve system (separate from CAN)

Not controlled by the hub, the WebUI or voice. It sends status only, to the hub,
for audible and visual feedback.

| ID | Function | Class | Status | Notes |
|---|---|---|---|---|
| F-501 | Solenoid valves in the individual brake lines between the ABS module and the calipers; selectable 3-, 2- or 1-wheel braking from four cab buttons | **H** | Far future | Heavily tested and fail-safed before install. Valves normally open so a power or controller failure leaves stock braking. Own controller, own interlock (for example parked or low speed only). Bench-test how the ABS/DSC module reacts to the changed caliper-side pressure |
| F-502 | Valve system status to the hub: armed, fault, valve states | V | Idea | One-way, hub speaks and displays it |

## 6. Future separate compute

| ID | Function | Status | Notes |
|---|---|---|---|
| F-601 | LIDAR | Idea | CAN cannot carry sensor data. Needs its own node on Ethernet, sending events ("object at rear, 1.2 m") to the hub over the private CAN |
| F-602 | Starlight cameras | Idea | Same. IR rings (F-406) are for this |
| F-603 | In-car PC with RTX 2070 | Deferred | See F-115 |

## Show-mode framework

Applies to every function with class **C** or **L**.

- **Registry:** each function has a row in the console database with ID, node,
  class, and an on/off setting. Default for every function is off, which means
  plain factory behavior.
- **Class C:** the WebUI toggle is the only gate.
- **Class L:** the WebUI toggle only means "allowed in show mode". The function
  runs only with the physical show-mode switch on **and** the car parked.
- **Class H:** not in the registry. The WebUI cannot arm or enable it.
- **Enforcement is on each node.** The node stores its setting, checks it
  locally, and falls back to plain or off on boot, heartbeat loss or console
  failure. A crashed web page can never leave a node in show mode.
- **Visibility:** the HUD lists which show-mode functions are active.
- **Classification:** the owner decides per function which class it is in and
  whether it is street-legal or show-only. Re-check against `lighting.md` and
  current state and federal rules whenever a function is added.

## Open questions

- Frame IDs, byte layouts and update rates for RPM, speed, MIL and HUD values.
- Push-to-talk button location.
- Whether locks, trunk and windows need any CAN at all, or just relay modules.
- Door-ajar input source for F-113.
- Reservoir float switch details (F-206) and which 2-stroke oil to run.
- Whether the head unit is the Bose or single-CD variant.
- Bulb-out detection on the factory turn-signal circuit versus LED loads.
- Content list for the HUD and the dot-matrix lamp.
- What the CM5's IO board exposes for displays (HDMI and DSI) for F-402 and F-403.
- Power budget across all lighting nodes.
- Per-function class assignment for everything marked C or L here.
