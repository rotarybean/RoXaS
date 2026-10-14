# lamp_module firmware (planned)

One module per tail lamp (LTLCM / RTLCM), classic ESP32. See
[`../../docs/lighting.md`](../../docs/lighting.md) for the architecture:
legal functions from hardwired factory inputs, commands and a time-sync tick
over CAN, watchdog fallback to plain lamp function, and a physical show-mode
interlock.
