# Testing

## CI (no hardware required)

```sh
uv run pytest
```

Runs against in-process simulators. This is the gate that every commit must pass.

## Bench (real PLC, no instrument)

1. Power the CX9240, confirm `arp` resolves the static IP (10.8.104.50).
2. Confirm ADS connection: `ADC_PLC_MODE=real ADC_PLC_AMS_NET_ID=<...> uv run python -m adc_winered.plc_client --probe`.
3. With `GVL_Cfg.bSimulate := TRUE` on the PLC, command Slide A `IN` and verify `GVL_State.eSlideA` cycles `OUT → MOVING → IN` in a Python REPL.
4. Switch to `bSimulate := FALSE`. Pulse Deploy A briefly and confirm the real limit switches transition.
5. Move Rotator A by ±30° via the WS API; confirm encoder position converges to within deadband.

## On-instrument

1. Run a 5-minute tracking session against `tcs_sim`; watch motor angles converge as elevation/rotator drift.
2. Switch to real TCS. Verify elevation + rotator readback against the TCS console.
3. Point `lco-instrument-web` at `ws://<host>:52403` and exercise every UI command (insertion, control mode, manual lens move, auto-update, run/stop). No schema warnings in the client console.
