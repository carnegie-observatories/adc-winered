# PLC layer

The PLC half of the stack has two views: the ADS surface seen by the Python server, and the TwinCAT project that exposes it.

## Driver interface (Python side)

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

The client expects exactly these symbols on the PLC. They are declared in `plc/GVLs/GVL_State.st` (read-only) and `plc/GVLs/GVL_Cmd.st` (read/write).

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

If you change a symbol name, change both the `.st` declaration and the `_AXIS_SYMBOLS` / `_SLIDE_SYMBOLS` tables in `plc_client.py`. Keep the two in lockstep.

## TwinCAT project layout

All ST source lives in [`plc/`](../plc/). The System Manager configuration (EtherCAT topology, NC axis parameters, `TcLinkTo` link paths) is established once in XAE per [`plc/SYSTEM_MANAGER.md`](../plc/SYSTEM_MANAGER.md).

```
plc/
  Types/E_SlideState.st         # enum on the wire
  GVLs/
    GVL_IO.st                   # variables linked via TcLinkTo to EL2002/EL1084
    GVL_State.st                # ADS read surface
    GVL_Cmd.st                  # ADS write surface
    GVL_Cfg.st                  # tunables + bSimulate
  POUs/
    FB_Slide.st                 # real solenoid driver + limit-switch decoder
    FB_SlideSim.st              # software-only slide (settle timer)
    FB_Rotator.st               # Tc2_MC2 wrapper around an NC axis
    FB_RotatorSim.st            # software-only rotator (integrates position)
    FB_AdcController.st         # composition root, dispatches by bSimulate
    MAIN.st                     # entry; one FB_AdcController instance
```

`FB_AdcController` is the **only** place that reads/writes `GVL_State` and `GVL_Cmd`. Other POUs accept their inputs as `VAR_INPUT` and return outputs via `VAR_OUTPUT`. This keeps the ADS-visible state machine concentrated and reviewable.

## Sim parity

`FB_RotatorSim` integrates position at `rRotatorVelocity * rCycleSeconds` per cycle and toggles `bBusy`/`bDone` like `MC_MoveAbsolute`. `FB_SlideSim` reports `MOVING` for `tSimSlideSettle`, then settles to `IN` / `OUT`. The Python-side `PlcSim` mirrors the same physics — so end-to-end tests against `PlcSim` exercise the same observable behaviour the PLC will produce.

When you change one sim, change the other. The contract is "same observable state for the same inputs", measured at `GVL_State` / `PlcSnapshot`.

## Library dependencies

- **Tc2_MC2** — motion control. `MC_Power`, `MC_MoveAbsolute`, `MC_Stop`, `MC_Home`, `MC_Reset`, `MC_ReadStatus`, `MC_ReadActualPosition`. Spec: https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_mc2/70049419.html
- **Tc2_Standard** — `R_TRIG`, `TON`.

## Bring-up checklist

1. Import the `.st` files into a TwinCAT 3 XAE solution.
2. Follow [`plc/SYSTEM_MANAGER.md`](../plc/SYSTEM_MANAGER.md) for EtherCAT scan, NC axis setup, and link wiring.
3. Set `GVL_Cfg.bSimulate := TRUE` for a first dry run; activate the config and confirm `GVL_State.bHeartbeat` toggles.
4. Set `bSimulate := FALSE`, deploy each slide individually, watch limit-switch transitions.
5. Run an `MC_Home` on each axis to find the encoder Z-pulse and set the home offset.
6. Start the Python server (`ADC_PLC_MODE=real`) and exercise the full WS API.
