# Architecture

```
+----------------------+   WS:52403   +--------------------------+   ADS    +--------------------------+   EtherCAT   +-------------------+
|  lco-instrument-web  | <----------> |  adc-winered (Python)    | <------> |  TwinCAT 3 / CX9240      | <----------> | EL7342, EL2002,   |
|  (canonical UI)      |  JSON frames |  - ws/ (server)          |  pyads   |  - NC axes (Tc2_MC2)     |              | EL1084, EL9505    |
+----------------------+              |  - controller (FSM)      |          |  - FB_Slide / FB_Rotator |              +-------------------+
                                      |  - correction (math)     |          |  - GVL_State / GVL_Cmd   |
                                      |  - plc_client / plc_sim  |          +--------------------------+
                                      |  - tcs_client / tcs_sim  |
                                      +-----------+--------------+
                                                  | TCP:5800
                                                  v
                                        +--------------------+
                                        |  Magellan TCS      |
                                        |  (or tcs_sim)      |
                                        +--------------------+
```

## Module map

| Module | Role |
|---|---|
| [`correction.py`](../src/adc_winered/correction.py) | Pure IB-mode math, no I/O. See [correction.md](correction.md). |
| [`plc.py`](../src/adc_winered/plc.py) | `PlcDriver` Protocol, `Axis`/`Slide`/`SlideState` enums, `AxisStatus`/`PlcSnapshot`. |
| [`plc_client.py`](../src/adc_winered/plc_client.py) | pyads-based real driver. |
| [`plc_sim.py`](../src/adc_winered/plc_sim.py) | In-process simulator with the same interface. |
| [`tcs.py`](../src/adc_winered/tcs.py) | `TcsDriver` Protocol, `TcsSample`. |
| [`tcs_client.py`](../src/adc_winered/tcs_client.py) | Async TCP client for the Magellan line protocol. |
| [`tcs_sim.py`](../src/adc_winered/tcs_sim.py) | In-process sim; can also expose a TCP server. |
| [`controller.py`](../src/adc_winered/controller.py) | State machine, tracking loop, snapshot subscription. |
| [`config.py`](../src/adc_winered/config.py) | pydantic-settings; env-var-driven Settings. |
| [`cli.py`](../src/adc_winered/cli.py) | `adc-winered serve` entry point. |
| [`ws/`](../src/adc_winered/ws/) | LCO WebSocket protocol — envelope, topics, commands, logs, server. |

## Responsibilities

| Layer | Owns |
|---|---|
| PLC (TwinCAT) | Motion safety (soft limits, max velocity, e-stop), encoder homing, slide limit-switch interpretation, sim variants of the FBs. |
| Python server | Atmospheric correction math, tracking-loop scheduling, controller state machine, TCS dialog, WS protocol marshaling, log ring-buffer. |
| WS client | All user-facing UI. |

## ADS surface

The Python server reads `GVL_State.*` and writes `GVL_Cmd.*`. Symbols listed in [plc.md](plc.md). Nothing else in the PLC project is part of the stable contract.

## WS surface

Frame types: `hello`, `state`, `event`, `ack`, `subscribe`, `unsubscribe`, `cmd`. Topics: `status`, `lens`, `telescope`, `logs`. Field shapes in [protocol.md](protocol.md).

## Simulator boundary

Both halves run without hardware:

- `ADC_PLC_MODE=sim` swaps `plc_client` for `plc_sim` in the Python server.
- The PLC project's `GVL_Cfg.bSimulate := TRUE` swaps `FB_Rotator`/`FB_Slide` for their `*Sim` variants inside `FB_AdcController`.

These two toggles are independent. End-to-end without hardware: set both.

## Lifecycle

1. `cli.main()` parses args, builds `Settings`, instantiates `PlcDriver` and `TcsDriver` (real or sim per env).
2. `Controller.start()` opens both drivers, transitions INIT → IDLE, starts three background tasks (PLC poll, TCS poll, tracking loop).
3. `WsServer.start()` binds the port and starts the publisher loop.
4. SIGINT/SIGTERM sets a stop event; the server stops, the controller stops (cancels tasks, closes drivers), the process exits.
