# CAN tap node

> Everything here is a design, not a tested build. Pin numbers must be checked
> against your board revision.

## Hardware

ESP32-S3-DevKitC-1 (N8, no octal PSRAM) with an SN65HVD230 transceiver on the
Mazda bus and an MCP2515 + 3.3 V transceiver on the C3M bus.

| Function | GPIO |
|---|---|
| TWAI TX / RX (Mazda) | 4 / 5 |
| Gate enable / Rs sense | 6 / 7 |
| MCP2515 CS / MOSI / SCK / MISO | 10 / 11 / 12 / 13 |
| MCP2515 INT | 14 |

These avoid the strapping, USB, and flash pins on the S3. The common blue
MCP2515 modules with a 5 V transceiver are not suitable on 3.3 V logic without
level shifting.

## The Rs transmit gate

With Rs held high the SN65HVD230 sits in a listen-only standby (driver off,
receiver on). Pulling Rs low enables the driver.

```
3V3 --R1(10k)--+-- Rs pin
               |
               +-- Q1 (N-FET, gate = KEY wire) --- Q2 (N-FET, gate = GPIO6) --- GND

3V3 --R3(1k)-- keyswitch -- KEY wire -- Q1 gate -- R4(47k) -- GND
GPIO6 -- Q2 gate -- R5(100k) -- GND
Rs net --R8(1k)-- GPIO7 (firmware reads back the real Rs state)
Rs net --R6(10k)-- base of Q3 (PNP: emitter 3V3, collector -- R7(330) -- LED -- GND)
D (TXD) pin --R2(10k)-- 3V3  (keeps TX recessive while the MCU boots)
```

Rs goes low only when Q1 and Q2 both conduct, so the keyswitch and firmware
must both agree. A cut or grounded KEY wire, a floating or crashed GPIO, or a
shorted feed wire all leave the driver off. The LED is driven from the Rs net,
so it shows the real hardware state, not what the firmware believes. Check the
datasheet's Rs current and standby-to-normal timing before fixing R1 and the
settle delay.

## Transmit whitelist

Firmware has one function that calls the CAN driver's transmit, and it only
accepts:

- OBD-II functional requests to 0x7DF with service 0x01, 0x03, 0x07, or 0x0A
- ISO-TP flow-control frames (first byte 0x30) to the physical ECU address 0x7E0

Nothing else can leave the node.

## Bring-up procedure

1. Power the node with the gate closed (keyswitch off). It cannot transmit.
2. Listen. Confirm 500 kbps by checking frames arrive cleanly and the CAN
   controller's error counters do not climb.
3. Log frame 0x420 from key-off to key-on. The byte that changes and changes
   back is the check-engine flag (see decision 5).
4. Only after that, close the loop: open the gate and request stored codes.
