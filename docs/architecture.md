# Architecture

## Nodes

| Node | Hardware | Role |
|---|---|---|
| Tap node | ESP32-S3-DevKitC-1 (N8) | Listens to the Mazda CAN bus, sends whitelisted read-only OBD-II requests behind a hardware gate, bridges events to the C3M bus |
| Hub | Raspberry Pi CM5 | STT, retrieval and LLM, TTS, audio mixing, DTC and parts lookup |
| LTLCM / RTLCM | Classic ESP32, one per tail lamp | Drive addressable LED arrays, run legal lamp functions locally |

## Buses

- **Mazda HS-CAN**: OBD-II pins 6 (CAN-H) and 14 (CAN-L), 500 kbps. Accessed
  through one SN65HVD230 on the ESP32's built-in CAN controller (TWAI). No extra
  termination is added because the tap sits mid-bus on a short stub.
- **C3M CAN**: a separate private bus. The tap node reaches it through an
  MCP2515 over SPI. The CM5 reaches it through a USB-CAN adapter (SocketCAN).
  120 ohm termination at the two physical ends only.

The two buses are never electrically connected. The only crossing point is
firmware in the tap node, which forwards events and read-only replies.

## Data flow for a DTC announcement

1. The tap node sees the check-engine flag change on the Mazda bus (see the
   hypothesis in `can-tap.md`) or sees the stored-code count change.
2. With the gate open, it requests the stored and pending codes over OBD-II.
3. It sends the code list to the hub over the C3M bus.
4. The hub looks each code up in the DTC table and speaks a templated line.

## Why tables, not model memory

A 0.5B model will happily produce a plausible but wrong part number. Part
numbers and DTC data are stored verbatim in SQLite. The model's job is to
understand the question, call a lookup, and phrase the answer.
