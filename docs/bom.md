# Bill of materials: tap node

Part numbers are class examples, not confirmed availability. Check ratings and
stock before ordering.

| Qty | Part | Notes |
|---|---|---|
| 1 | ESP32-S3-DevKitC-1, N8 | Avoid R8 (octal PSRAM) variants |
| 1 | SN65HVD230 module, 3.3 V | Mazda side. Rs pin must be reachable (many boards tie it to ground). Remove or disable the 120 ohm terminator |
| 1 | MCP2515 + SN65HVD230 board, 3.3 V logic | C3M side. Avoid 5 V TJA1050 boards without level shifting |
| 2 | BSS138 N-FET (Q1, Q2) | 2N7002 is marginal at a 3.3 V gate |
| 1 | BC857 or 2N3906 PNP (Q3) | LED driver |
| 8 | Resistors: R1 10k, R2 10k, R3 1k, R4 47k, R5 100k, R6 10k, R7 330, R8 1k | 0.25 W |
| 1 | Panel-mount SPST keyswitch | Dash; carries ~3 mA of logic signal |
| 1 | Panel-mount LED, red/amber/green | Low forward voltage; blue/white will not light well at 3.3 V |
| 2 | CAN ESD protection array | One per CAN port |
| 2 | CAN common-mode choke (optional) | One per CAN port |
| 1 | 12 V to 5 V buck, 36 V or higher input, 1 A or more | Automotive transient tolerant |
| 1 | Inline fuse and holder, 2 A | Ignition-switched branch |
| 1 | Schottky diode + SMBJ-class TVS | Reverse polarity and transients |
| 1 | 100 uF 35 V and 0.1 uF capacitors | 5 V rail |
| 1 | OBD-II Y-splitter or J1962 pigtail | Pins 6, 14, and a ground |
| ~10 m | 24 AWG shielded twisted pair | Mazda stub under ~30 cm. Shield grounded at one end |
| 2 | 120 ohm resistors | C3M bus end terminations if not on the modules |
| 1 | USB-to-CAN adapter (gs_usb type), isolated preferred | CM5 side, appears as can0 |
