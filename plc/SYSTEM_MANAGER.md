# XAE / System Manager one-time setup

The ST files in this directory carry the logic. The System Manager config
(EtherCAT topology, NC axes, `TcLinkTo` paths) has to be created in XAE. Steps:

## 1. EtherCAT master

`I/O → Devices → Add New Item → EtherCAT → EtherCAT Master`. Scan for boxes.
Expected topology (from [`../docs/hardware.md`](../docs/hardware.md)):

```
Device 1 (EtherCAT)
└── Box 1: CX9240-0215 (this is the CPU; auto-detected)
    ├── Term 2 (EL2002)   — 2-ch DO 24V
    ├── Term 3 (EL1084)   — 4-ch DI 24V
    ├── Term 4 (EL7342)   — 2-ch DC drive + encoder
    └── Term 5 (EL9505)   — 5V power supply
```

Module numbering may differ on your bench. Whatever it is, update the
`TcLinkTo` paths in `GVLs/GVL_IO.st` to match.

## 2. NC task and axes

`Motion → Add New Item → NC/PTP NCI Configuration`. Inside it:

| Axis name | Type | Encoder | Drive |
|---|---|---|---|
| `AxisA` | Continuous (rotary) | Incremental, EL7342 ch.1 | EL7342 ch.1 |
| `AxisB` | Continuous (rotary) | Incremental, EL7342 ch.2 | EL7342 ch.2 |

Configure each axis:

- **Encoder → Scaling Factor Numerator / Denominator**: derive from the
  Pololu 3046 gearbox ratio × encoder counts per motor rev.
- **Encoder → Modulo Factor**: `360.0` (continuous rotation).
- **Parameter → Velocities**: set Max Velocity, Reference Velocity, Manual
  Velocity (Fast / Slow) to safe bench values.
- **Parameter → Limit Switches**: enable software end-stops if the optic
  housing demands it; the prisms are continuous so usually leave disabled.
- **Homing**: incremental encoders require a homing routine. Configure
  `MC_Home` with `HomingMode := MC_DefaultHoming` to find the Z-pulse, then
  set the home position offset.

Link each NC axis's "Drive" and "Encoder" to the EL7342 channel via
right-click → Link To.

## 3. Linking GVL_IO

Each variable in `GVL_IO.st` carries a `TcLinkTo` attribute that points at
an EtherCAT input/output channel. After importing the GVL into XAE, click
"Reload All Mappings" to materialise the links. Verify in
`I/O → Mappings → PLC` that every variable resolves.

If the topology in step 1 differs, update the `TcLinkTo` strings in
`GVL_IO.st` to match (XAE → right-click variable → Properties → look at
"Path"); the Beckhoff online docs cover the attribute syntax in detail
(https://infosys.beckhoff.com/content/1033/tc3_plc_intro/3107974923.html).

## 4. ADS routing

The Python server talks to the PLC over ADS. Two things must be true:

- The CX9240 is reachable on the local network (10.8.104.50/24 by default;
  see `docs/references/plc_configuration.md`).
- A route exists from the developer/server machine to the CX9240
  (`pyads.add_route_to_plc(...)` or via TwinCAT Static Routes).

The Python server reads `ADC_PLC_AMS_NET_ID` from env — set it to the
CX9240's AMS net ID (typically `<plc_ip>.1.1`).

## 5. Activate + run

XAE → "Activate Configuration" → "Restart TwinCAT system in Run Mode".
Confirm the heartbeat (`GVL_State.bHeartbeat`) toggles in the online view,
then start the Python server.
