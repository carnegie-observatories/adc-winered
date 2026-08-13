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
| `set_shutter(closed)` | Level-triggered; `closed=True` closes the shutter |
| `set_milky_flat(deploy_in)` | Level-triggered; `deploy_in=True` puts the diffuser in the beam |

`PlcSnapshot` carries `axis_a`, `axis_b` (each `AxisStatus(position_deg, busy, done, error, error_id)`), `slide_a`, `slide_b` (`SlideState` enum: IN / OUT / MOVING / ERROR), `shutter_closed` and `milky_flat_deployed` bools, and a `heartbeat` bit.

## ADS symbol layout

The client expects exactly these symbols on the PLC. They are declared in `plc/adc/adc/GVLs/GVL_State.TcGVL` (read-only) and `plc/adc/adc/GVLs/GVL_Cmd.TcGVL` (read/write).

### `GVL_State` (read by Python)

```
rAxisA_Position : LREAL          // degrees
bAxisA_Busy / bAxisA_Done / bAxisA_Error : BOOL
nAxisA_ErrorId : UDINT           // matches MC_*.ErrorID
bAxisA_Ready  : BOOL             // homed AND not in error
rAxisB_Position : LREAL
bAxisB_Busy / bAxisB_Done / bAxisB_Error : BOOL
nAxisB_ErrorId : UDINT
bAxisB_Ready  : BOOL
eSlideA : E_SlideState           // 0=OUT, 1=IN, 2=MOVING, 3=ERROR
eSlideB : E_SlideState
bShutter_Closed : BOOL           // echoes the command — no feedback sensor
bMilkyFlat_Deployed : BOOL       // echoes the command — no feedback sensor
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
bShutter_Closed : BOOL                   // level: TRUE = shutter closed
bMilkyFlat_Deploy : BOOL                 // level: TRUE = diffuser in beam
```

The shutter and milky-flat commands name the *physical* condition. Both EL2084
channels are wired inverted, so `FB_AdcController` de-energizes the output to
reach the named state — meaning a de-energized rack (PLC stopped, sim mode,
power loss) leaves the shutter closed and the diffuser in the beam.

If you change a symbol name, change both the `.TcGVL` declaration and the `_AXIS_SYMBOLS` / `_SLIDE_SYMBOLS` tables in `plc_client.py`. Keep the two in lockstep.

## TwinCAT project layout

The full TwinCAT XAE solution lives in [`plc/`](../plc/) — open
[`plc/adc.sln`](../plc/adc.sln) in XAE. The System Manager configuration
(EtherCAT topology, NC axis parameters, `TcLinkTo` link paths) is
established once per [`docs/bring-up.md`](bring-up.md).

```
plc/
  adc.sln                            # Visual Studio solution
  adc/
    adc.tsproj                       # System Manager config
    adc/
      adc.plcproj                    # PLC project
      DUTs/E_SlideState.TcDUT        # enum on the wire
      GVLs/
        GVL_IO.TcGVL                 # variables linked via TcLinkTo to EL2002/EL1084
        GVL_State.TcGVL              # ADS read surface
        GVL_Cmd.TcGVL                # ADS write surface
        GVL_Cfg.TcGVL                # tunables + bSimulate
      POUs/
        FB_Slide.TcPOU               # real solenoid driver + limit-switch decoder
        FB_SlideSim.TcPOU            # software-only slide (settle timer)
        FB_Rotator.TcPOU             # Tc2_MC2 wrapper around an NC axis
        FB_RotatorSim.TcPOU          # software-only rotator (integrates position)
        FB_AdcController.TcPOU       # composition root, dispatches by bSimulate
        MAIN.TcPOU                   # entry; one FB_AdcController instance
```

`FB_AdcController` is the **only** place that reads/writes `GVL_State` and `GVL_Cmd`. Other POUs accept their inputs as `VAR_INPUT` and return outputs via `VAR_OUTPUT`. This keeps the ADS-visible state machine concentrated and reviewable.

## Sim parity

`FB_RotatorSim` integrates position at `rRotatorVelocity * rCycleSeconds` per cycle and toggles `bBusy`/`bDone` like `MC_MoveAbsolute`. `FB_SlideSim` reports `MOVING` for `tSimSlideSettle`, then settles to `IN` / `OUT`. The Python-side `PlcSim` mirrors the same physics — so end-to-end tests against `PlcSim` exercise the same observable behaviour the PLC will produce.

When you change one sim, change the other. The contract is "same observable state for the same inputs", measured at `GVL_State` / `PlcSnapshot`.

## Library dependencies

- **Tc2_MC2** — motion control. `MC_Power`, `MC_MoveAbsolute`, `MC_Stop`, `MC_Home`, `MC_Reset`, `MC_ReadStatus`, `MC_ReadActualPosition`. Spec: https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_mc2/70049419.html
- **Tc2_Standard** — `R_TRIG`, `TON`.

## Bring-up checklist

1. Open [`plc/adc.sln`](../plc/adc.sln) in TwinCAT XAE.
2. Follow [`docs/bring-up.md`](bring-up.md) for EtherCAT scan, NC axis setup, and link wiring.
3. Set `GVL_Cfg.bSimulate := TRUE` for a first dry run; activate the config and confirm `GVL_State.bHeartbeat` toggles.
4. Set `bSimulate := FALSE`, deploy each slide individually, watch limit-switch transitions.
5. Run an `MC_Home` on each axis to find the encoder Z-pulse and set the home offset.
6. Start the Python server (`ADC_PLC_MODE=real`) and exercise the full WS API.
