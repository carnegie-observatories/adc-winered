# WINERED ADC — TwinCAT 3 project

Full TwinCAT XAE solution for the PLC half of the stack. Open
[`adc.sln`](adc.sln) in XAE → the solution carries the System Manager
config (EtherCAT topology, NC axis parameters, `TcLinkTo` link paths)
plus the PLC project (POUs, GVLs, DUTs).

For the hardware reference and the bench bring-up procedure
(SDOs, NC axis parameters, homing) see
[`docs/bring-up.md`](../docs/bring-up.md).

## File map

```
plc/
  README.md
  adc.sln                          # Visual Studio solution
  adc/                             # TwinCAT solution
    adc.tsproj                     # System Manager config
    adc/                           # PLC project
      adc.plcproj
      DUTs/
        E_SlideState.TcDUT         # OUT(0) / IN(1) / MOVING(2) / ERROR(3)
      GVLs/
        GVL_IO.TcGVL               # variables linked to EL2002/EL1084 via TcLinkTo
        GVL_State.TcGVL            # ADS-readable telemetry
        GVL_Cmd.TcGVL              # ADS-writable command surface
        GVL_Cfg.TcGVL              # tunables + bSimulate toggle
      POUs/
        MAIN.TcPOU                 # one-cycle entry, calls FB_AdcController
        FB_AdcController.TcPOU     # composes the four FBs, exposes ADS surface
        FB_Rotator.TcPOU           # Tc2_MC2 wrapper: MC_Power/Move/Stop/Home/Reset
        FB_RotatorSim.TcPOU        # software-only rotator (constant-velocity slewer)
        FB_Slide.TcPOU             # solenoid drive + limit-switch state machine
        FB_SlideSim.TcPOU          # software-only slide (settle timer)
```

TwinCAT build artefacts (`_Boot/`, `_CompileInfo/`, `.vs/`,
`*.tsproj.bak`, `TrialLicense.tclrs`) are gitignored.

## Editing the PLC code

Open the solution in TwinCAT XAE; edit POUs / GVLs / DUTs in the IDE.
The `.TcPOU` / `.TcGVL` / `.TcDUT` files are XML-wrapped Structured
Text — they can be diffed/reviewed in a regular text editor, but XAE
is the supported editor.

## Required libraries

- **Tc2_MC2** — Motion Control library. Used by `FB_Rotator` for
  `MC_Power`, `MC_MoveAbsolute`, `MC_Stop`, `MC_Home` (with
  `bCalibrationCam` driven from PLC for Z-pulse-only homing — see
  [`docs/bring-up.md` § 4](../docs/bring-up.md#4-homing-configuration)),
  `MC_Reset`, `MC_ReadStatus`, and `MC_ReadActualPosition`. Backed by
  the **TF5000 NC PTP** runtime, which has to be apt-installed on the
  CX9240 (`tf5000-nc-ptp-xar`) — see
  [`docs/bring-up.md` § 0](../docs/bring-up.md#0-plc-runtime--install-the-nc-ptp-package).
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
