#pragma once
// Pin map for the CAN tap node (ESP32-S3-DevKitC-1, N8).
// Verify against your board revision before wiring. See docs/can-tap.md.

// Mazda bus: built-in CAN controller (TWAI) + SN65HVD230
constexpr int PIN_TWAI_TX = 4;
constexpr int PIN_TWAI_RX = 5;

// Rs transmit gate
constexpr int PIN_GATE_EN  = 6;  // push-pull HIGH = firmware agrees to transmit
constexpr int PIN_RS_SENSE = 7;  // reads the Rs net (LOW only if the gate is really open)

// C3M bus: MCP2515 over SPI
constexpr int PIN_MCP_CS   = 10;
constexpr int PIN_MCP_MOSI = 11;
constexpr int PIN_MCP_SCK  = 12;
constexpr int PIN_MCP_MISO = 13;
constexpr int PIN_MCP_INT  = 14;
