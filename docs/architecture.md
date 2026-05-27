# Architecture

```
+----------------------+   WS:52403   +--------------------------+   ADS    +--------------------------+   EtherCAT   +-------------------+
|  lco-instrument-web  | <----------> |  adc-winered (Python)    | <------> |  TwinCAT 3 / CX9240      | <----------> | EL7342, EL2002,   |
|  (canonical UI)      |  JSON frames |  - correction algorithm  |  pyads   |  - NC axes (Tc2_MC2)     |              | EL1084, EL9505    |
+----------------------+              |  - tracking loop         |          |  - FB_Slide / FB_Rotator |              +-------------------+
                                      |  - controller FSM        |          |  - GVL_State / GVL_Cmd   |
                                      +-----------+--------------+          +--------------------------+
                                                  | TCP:5800
                                                  v
                                        +--------------------+
                                        |  Magellan TCS      |
                                        |  (or tcs_sim)      |
                                        +--------------------+
```

## Responsibilities

| Layer | Owns |
|---|---|
| PLC (TwinCAT) | Motion safety (soft limits, max velocity, e-stop), encoder homing, slide limit-switch interpretation, sim variants of the FBs |
| Python server | Atmospheric correction math, tracking-loop scheduling, controller state machine, TCS dialog, WS protocol marshaling, log ring-buffer |
| WS client | All user-facing UI |

## ADS surface (what Python sees on the PLC)

Only the symbols under `GVL_State` (read) and `GVL_Cmd` (write) are stable contracts. Anything else in the PLC project is internal. See [plc.md](plc.md) for the full symbol list.

## WS surface (what the UI sees on the Python server)

Frame types: `hello`, `state`, `event`, `ack`, `subscribe`, `unsubscribe`, `cmd`. Topics: `status`, `lens`, `telescope`, `logs`. See [protocol.md](protocol.md) for the field-level shape.

## Simulator boundary

Both halves can be run with no real hardware:

- `ADC_PLC_MODE=sim` swaps `plc_client` for `plc_sim` in the Python server.
- The PLC project's `GVL_Cfg.bSimulate := TRUE` swaps `FB_Rotator`/`FB_Slide` for their `*Sim` variants inside `FB_AdcController`.

These two sim toggles are independent — set just the Python one to develop the WS API; set just the PLC one to develop ST without instrument hardware; set both to develop end-to-end without anything plugged in.
