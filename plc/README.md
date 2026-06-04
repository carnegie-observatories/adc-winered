# WINERED ADC — TwinCAT 3 project

Structured Text source for the PLC half of the stack. The `.st` files are the
authoritative source — but TwinCAT 3 stores its on-disk POUs as `.TcPOU`
(XML wrapping the ST), not as plain `.st`, so you can't import these directly
with "Add Existing Item". See [Bringing the code into XAE](#bringing-the-code-into-xae)
below for the workflow.

This directory is not a full `.sln`/`.tsproj` — the System Manager configuration
(EtherCAT topology, NC axis parameters, `TcLinkTo` link paths) lives in the
TwinCAT GUI and cannot be checked in cleanly as text. See
[`docs/bring-up.md`](../docs/bring-up.md) for the hardware reference and
step-by-step XAE setup.

## Bringing the code into XAE

These `.st` files map 1:1 to TwinCAT POUs and GVLs. To assemble them
into a TwinCAT solution:

1. In XAE, create the TwinCAT solution and a PLC project under it.
2. In the PLC project tree, right-click `POUs` → **Add** → pick the right
   POU type and **give it the same name** as the file (e.g.
   `FB_Rotator` from `POUs/FB_Rotator.st`):
   - `MAIN` → Program
   - `FB_AdcController`, `FB_Rotator`, `FB_RotatorSim`, `FB_Slide`,
     `FB_SlideSim` → Function Block
3. Open the new POU. Paste the *declaration* section (the `VAR_INPUT` /
   `VAR_OUTPUT` / `VAR` blocks) into the top pane, and the *implementation*
   section (the ST after the last `END_VAR`) into the bottom pane. XAE
   splits these automatically — the `.st` file just runs them together.
4. Repeat for each file under `GVLs/` (right-click `GVLs` → **Add** →
   **Global Variable List**) and `Types/` (right-click `DUTs` → **Add** →
   **DUT** → **Enumeration** for `E_SlideState`).
5. **Build** the project. Any compile errors mean a paste mismatch or a
   missing library reference (typically `Tc2_MC2`); add it via
   **References → Add library**.

### What the `.st` files map to

| File on disk | XAE artefact | Lives under |
|---|---|---|
| `POUs/MAIN.st` | `MAIN` (Program) | PLC project → `POUs` |
| `POUs/FB_AdcController.st` | `FB_AdcController` (Function Block) | PLC project → `POUs` |
| `POUs/FB_Rotator.st` etc. | Function Blocks | PLC project → `POUs` |
| `GVLs/GVL_IO.st` etc. | Global Variable Lists | PLC project → `GVLs` |
| `Types/E_SlideState.st` | DUT (Enumeration) | PLC project → `DUTs` |

The directory layout in this repo is deliberately a mirror of the XAE
tree, so the mapping is one-to-one with the same names. Keep the
filenames in sync when adding new POUs.

## File map

```
plc/
  README.md
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
