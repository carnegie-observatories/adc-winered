# WINERED ADC — TwinCAT 3 project

Structured Text source for the PLC half of the stack. The `.st` files are the
authoritative source; assemble them into a TwinCAT 3 solution by importing each
one into the corresponding POU / GVL in XAE.

This directory is not a full `.sln`/`.tsproj` — the System Manager configuration
(EtherCAT topology, NC axis parameters, `TcLinkTo` link paths) lives in the
TwinCAT GUI and cannot be checked in cleanly as text. See [SYSTEM_MANAGER.md](SYSTEM_MANAGER.md)
for the steps to wire everything up.

## File map

```
plc/
  README.md
  SYSTEM_MANAGER.md      # one-time XAE setup (EtherCAT topology, NC axes, TcLinkTo)
  Types/
    E_SlideState.st      # OUT(0) / IN(1) / MOVING(2) / ERROR(3)
  GVLs/
    GVL_IO.st            # variables linked to EL2002/EL1084 via TcLinkTo
    GVL_State.st         # ADS-readable telemetry
    GVL_Cmd.st           # ADS-writable command surface
    GVL_Cfg.st           # tunables + bSimulate toggle
  POUs/
    FB_Slide.st          # solenoid drive + limit-switch state machine
    FB_SlideSim.st       # software-only slide (settle timer)
    FB_Rotator.st        # Tc2_MC2 wrapper: MC_Power/Move/Stop/Home/Reset
    FB_RotatorSim.st     # software-only rotator (constant-velocity slewer)
    FB_AdcController.st  # composes the four FBs, exposes ADS surface
    MAIN.st              # one-cycle entry, calls FB_AdcController
```

## Required libraries

- **Tc2_MC2** — Motion Control library. Used by `FB_Rotator` for `MC_Power`,
  `MC_MoveAbsolute`, `MC_Stop`, `MC_Home`, `MC_Reset`, `MC_ReadStatus`,
  `MC_ReadActualPosition`.
- **Tc2_Standard** — `R_TRIG` (rising-edge detection on the per-axis Go bits).
- **Tc2_System** — `F_GetCurDosTm` for the heartbeat (or any monotonic source).

## Cycle time

The PLC task runs at 10 ms (configure in XAE → SYSTEM → Tasks). The NC task
runs at the default 2 ms. Tighter cycles are fine; the FBs are stateless
across cycles apart from the edge triggers.

## ADS surface

Only `GVL_State` (read) and `GVL_Cmd` (read/write) are stable. The Python
server's `plc_client.py` mirrors these symbol names — change in lockstep.
Full list in [`docs/plc.md`](../docs/plc.md).

## Sim mode

Set `GVL_Cfg.bSimulate := TRUE` to run without real hardware. `FB_AdcController`
will skip the `Tc2_MC2` axis FBs and call `FB_RotatorSim` / `FB_SlideSim`
instead — same `GVL_State` output, no EtherCAT traffic required.
