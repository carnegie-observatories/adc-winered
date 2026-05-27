# PLC project (TwinCAT 3)

Filled in during phase 8. Stub now; this is the place for the GVL/FB documentation.

Planned contents:

- Solution layout (`plc/WineredADC.sln`) and POU/GVL file map.
- GVL_IO `TcLinkTo` table (variable → EtherCAT channel).
- ADS surface: full symbol list under `GVL_State` and `GVL_Cmd`.
- FB interfaces: `FB_Rotator`, `FB_Slide`, and their `*Sim` variants.
- NC axis parameters for `AxisA` / `AxisB` (encoder scaling, modulo wrap, soft limits, homing mode).
- Sim mode toggle (`GVL_Cfg.bSimulate`).
- Rebuild + deploy steps on the CX9240.
