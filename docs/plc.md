# PLC layer

The PLC half of the stack has two views: the ADS surface seen by the Python server, and the TwinCAT project that exposes it. This page covers the Python-facing surface and the driver swap. The TwinCAT project layout, GVL files, and FBs are described once they land in phase 8.

## Driver interface

The controller depends on `adc_winered.plc.PlcDriver` (a `Protocol`). Two implementations:

| Implementation | Module | When to use |
|---|---|---|
| `PlcClient` | [`plc_client.py`](../src/adc_winered/plc_client.py) | Real Beckhoff CX9240 over Beckhoff ADS (`pyads`) |
| `PlcSim` | [`plc_sim.py`](../src/adc_winered/plc_sim.py) | In-process simulator; no TwinCAT runtime, no network |

Both expose the same coroutines:

| Method | Effect |
|---|---|
| `connect()` / `close()` | Lifecycle |
| `read() -> PlcSnapshot` | One-shot read of `GVL_State` |
| `move_axis(axis, target_deg)` | Write target + pulse `bGo`; non-blocking |
| `stop_axis(axis)` / `home_axis(axis)` / `reset_axis(axis)` | Edge-triggered commands |
| `set_slide(slide, deploy_in)` | Level-triggered solenoid drive |

`PlcSnapshot` carries `axis_a`, `axis_b` (each `AxisStatus(position_deg, busy, done, error, error_id)`), `slide_a`, `slide_b` (`SlideState` enum: IN / OUT / MOVING / ERROR), and a `heartbeat` bit.

## ADS symbol layout

The client expects exactly these symbols on the PLC. They must be declared in `GVL_State` (read-only) and `GVL_Cmd` (read/write) in the TwinCAT project.

### `GVL_State` (read by Python)

```
rAxisA_Position : LREAL          // degrees
bAxisA_Busy / bAxisA_Done / bAxisA_Error : BOOL
nAxisA_ErrorId : DINT
rAxisB_Position : LREAL
bAxisB_Busy / bAxisB_Done / bAxisB_Error : BOOL
nAxisB_ErrorId : DINT
eSlideA : E_SlideState           // 0=OUT, 1=IN, 2=MOVING, 3=ERROR
eSlideB : E_SlideState
bHeartbeat : BOOL                // toggled by the PLC each cycle
```

### `GVL_Cmd` (written by Python)

```
rAxisA_Target / rAxisB_Target : LREAL
bAxisA_Go / bAxisB_Go : BOOL     // rising edge -> MC_MoveAbsolute; PLC clears after consume
bAxisA_Stop / bAxisB_Stop : BOOL
bAxisA_Home / bAxisB_Home : BOOL
bAxisA_Reset / bAxisB_Reset : BOOL
bSlideA_Deploy / bSlideB_Deploy : BOOL   // level: TRUE = IN
```

If you change a symbol name, change both the `GVL_*` declaration and the `_AXIS_SYMBOLS` / `_SLIDE_SYMBOLS` tables in `plc_client.py`. Keep the two in lockstep.

## Simulator behaviour

`PlcSim` models the same physical effects as `FB_RotatorSim` / `FB_SlideSim` will on the PLC side:

- Rotators slew at a constant `rotator_velocity_deg_s` (default 30 °/s) toward the target; `busy`/`done` follow MC2 semantics.
- Slides transition through `MOVING` for `slide_settle_s` (default 0.5 s) before reporting `IN`/`OUT`.
- Time is read from an injectable clock — tests pass a fake clock to drive the simulation deterministically.
- `read()` advances the simulation, so tests that don't read don't tick.

The PLC's `FB_*Sim` variants must keep the same observable behaviour (same units, same state-machine transitions). If the two diverge, end-to-end tests against `PlcSim` won't catch bugs in the real PLC path.

## TwinCAT project

Filled in during phase 8. The placeholder remains so the file can be linked from the docs index from day one.
