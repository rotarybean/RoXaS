// CAN tap node: STUB. Not yet built or tested on hardware.
//
// Planned, in order:
//   1. Listen-only logger on the Mazda bus with the gate closed (find the
//      check-engine flag, confirm 500 kbps).
//   2. Gate control: open only when the keyswitch AND this firmware agree,
//      verified by reading back the Rs net.
//   3. Whitelisted OBD-II requests (Mode 01/03/07/0A) and ISO-TP handling.
//   4. Bridge events to the C3M bus.
//
// See docs/can-tap.md.

#include <Arduino.h>
#include "pins.h"

void setup() {
  Serial.begin(115200);
  // Keep the gate closed at boot: GATE_EN low means Q2 is off.
  pinMode(PIN_GATE_EN, OUTPUT);
  digitalWrite(PIN_GATE_EN, LOW);
  pinMode(PIN_RS_SENSE, INPUT);
  Serial.println("can_tap stub: gate closed, logger not implemented yet");
}

void loop() {
  delay(1000);
}
