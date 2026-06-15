# WINERED ADC — hardware reference and bench bring-up

Everything you need to wire the WINERED ADC's PLC stack and configure it in
TwinCAT XAE — from the EtherCAT slice list and DB25 pinout down to the SDOs,
NC axis parameters, and homing config that actually make it work.

Two halves:

- [Part 1 — Hardware reference](#part-1--hardware-reference) — the
  physical and electrical facts (modules, pinouts, motor / encoder
  specs, mechanical coupling).
- [Part 2 — Bench bring-up procedure](#part-2--bench-bring-up-procedure) —
  step-by-step XAE configuration: NC PTP install, EtherCAT scan, EL7342
  SDOs, NC axes, homing, GVL_IO linking, ADS routing, activate.

---

# Part 1 — Hardware reference

## Beckhoff stack

| # | Module | Role | Power |
|---|---|---|---|
| 1 | CX9240-0215 | PLC CPU, EtherCAT master, ADS endpoint | 4 A |
| 2 | EL2002 | 2-ch 24 V DO — deploy solenoids | 100 mA |
| 3 | EL1084 | 4-ch 24 V DI — slide limit switches | 100 mA + load |
| 4 | EL7342 | 2-ch DC drive + incremental encoder — both rotators | 150 mA |
| 5 | EL9505 | 5 V supply for encoders | 90 mA + 0.5 A |

Us fuse: 1 A. Up fuse: max 10 A. PLC static IP: 10.8.104.50/24 (see
[references/plc_configuration.md](references/plc_configuration.md)).

## DB25 pinout (instrument-side connector)

From [references/](references/) — full CSV at
`/Users/william/Downloads/WINERED ADC electronics - Pinout Incr Encoder.csv`.

| Pin | Module:Ch | Signal |
|---|---|---|
| 1 | EL2002:3 | Deploy common |
| 2 | EL2002:1 (O1) | Deploy B |
| 3 | EL2002:7 | Sense GND (Blue) |
| 4 | EL1084:1 (I1) | Sense B: OUT (Black) |
| 5 | EL1084:4 (I3) | Sense A: OUT (Black) |
| 6 | EL7342:1' (A1) | Motor A + |
| 7 | EL7342:2' (B1) | Motor B + |
| 8 | EL9505:3 | Enc A: −5 V |
| 9 | EL9505:7 | Enc B: −5 V |
| 10 | EL7342:1 (A) | Enc A: A (gray) |
| 11 | EL7342:2 (A) | Enc B: A (gray) |
| 13 | EL2002:5 (O2) | Deploy A |
| 14 | EL1084:2 (+24 V) | Sense 24 V (brown) |
| 15 | EL1084:5 (I2) | Sense B: IN (Black) |
| 16 | EL1084:8 (I4) | Sense A: IN (Black) |
| 17 | EL7342:5' (A2) | Motor A − |
| 18 | EL7342:6' (B2) | Motor B − |
| 19 | EL9505:2 (5 V) | Enc A: +5 V |
| 20 | EL9505:6 (5 V) | Enc B: +5 V |
| 21 | EL7342:4 (I1) | Enc A: Z (white) |
| 22 | EL7342:8 (I2) | Enc B: Z (white) |
| 23 | EL7342:5 (B) | Enc A: B (green) |
| 24 | EL7342:6 (B) | Enc B: B (green) |

Pins 12, 25 → PE (not connected).

## Mechanical / electrical references

| Component | Datasheet |
|---|---|
| Motors (rotators) | Pololu 3046 — [references/pololu-micro-metal-gearmotors-rev-6-2.pdf](references/pololu-micro-metal-gearmotors-rev-6-2.pdf) |
| Encoders (rotators) | RLS **RM08ID0011B02L2G00** — incremental, single-ended 5 V, 2048 cpr, 0.2 m leads, cylindrical body, IP68 |
| Pneumatic valves (slides) | Clippard Maximatic 4-way — [references/Clippard Maximatic 4-Way Valves.pdf](references/Clippard%20Maximatic%204-Way%20Valves.pdf) |
| Limit switches (slides) | Bimba — [references/Switches.pdf](references/Switches.pdf), [references/bimba_switch.png](references/bimba_switch.png) |
| IO module reference | Phoenix Contact 2909906 — [references/phoenix-contact-2909906-en.pdf](references/phoenix-contact-2909906-en.pdf) |

## Pololu 3046 motor (rotators A and B)

The Pololu **3046** is the *1000:1 Micro Metal Gearmotor HPCB 12V*
(High-Power Carbon Brush, 12 V nominal, 986.41:1 brass-plate gearbox).
Product page: https://www.pololu.com/product/3046.

The EL7342 is fed from the **24 V Up rail** and PWM-derates to deliver
the 12 V motor nominal — that's the whole point of `0x80x0:03` Nominal
voltage in the SDO config below.

| Quantity | Value | Source |
|---|---|---|
| Gear ratio | 986.41 : 1 | Pololu product page |
| Motor nameplate voltage | 12 V | Pololu product page |
| **Up supply rail to EL7342** | **24 V** | site wiring — drive current-limits, motor sees ~12 V average |
| No-load output speed | 35 RPM at 12 V | Pololu product page |
| No-load current | 80 mA at 12 V | Pololu product page |
| Max-efficiency current | 0.19 A | datasheet PDF |
| Max-efficiency torque | 21 kg·mm | datasheet PDF |
| Max-efficiency speed | 27 RPM | datasheet PDF |
| Stall torque (extrapolated) | 10 kg·cm = 100 kg·mm at 12 V | Pololu product page |
| Stall current (extrapolated) | 0.75 A at 12 V | Pololu product page |
| Recommended max instantaneous torque | 2.5 kg·cm = 25 kg·mm | Pololu product page (≤25 % of stall torque rule) |
| Implied winding resistance (extrapolated) | 16 Ω | `R = V_nom / I_stall = 12 V / 0.75 A` |
| **Measured winding resistance** | **14 Ω** | Multimeter across motor leads, minimum stable reading while rotating shaft — what `:04` should use |

Pololu's general continuous-operation guidance is "≤ 25 % of stall current",
which lands at 190 mA — the same figure as the max-efficiency point.

## Rotator drivetrain

The Pololu 3046 motor + gearbox drives the prism directly; the RLS RM08ID
encoder is mounted on the gearbox **output shaft**, so:

```
1 motor turn × gearbox ratio = 1 gearbox output turn = 1 encoder turn = 1 prism turn (360°)
```

This 1:1 coupling between encoder and prism is what makes the NC scaling
math simple — see [§ 3 NC task and axes](#3-nc-task-and-axes) below for
the resulting `360 / 2048` scale.

## Encoder Z signal direct to EL7342 I1 / I2

The RM08ID encoder outputs a **5 V** Z (reference / index) pulse. Per the
EL73x2 manual, the EL7342's `Input 1` / `Input 2` accept the 5 V signal
directly when used as digital latch inputs for motor A / B (their normal
24 V digital-input rating is for non-latch use). Bench-verified: the
encoder Z wires straight into I1 (axis A) / I2 (axis B) on the EL7342 —
no level shifter, no signal conditioning. Active-high, rising-edge for
the latch.

The encoder Z does **double duty** in this setup: the WINERED axes have
**no separate limit switch**, so I1 (originally the EL7342's limit
switch input) carries the Z pulse for both the homing cam role *and*
the precise sync role — see [§ 4 Homing configuration](#4-homing-configuration)
for how that works end-to-end.

## Component naming convention

Throughout the codebase:

- **Rotator A / Rotator B** — the two motorised prism axes.
- **Slide A / Slide B** — the two pneumatic deployment mechanisms.

The mapping from "A / B" to the physical prism/mirror role is fixed by the
harness wiring above; do not relabel in code.

---

# Part 2 — Bench bring-up procedure

The ST source in [`plc/`](../plc/) carries the logic. The System Manager
config (EtherCAT topology, NC axes, `TcLinkTo` paths) has to be created in
XAE. Steps in order:

## 0. PLC runtime — install the NC PTP package

The CX9240 ships with TwinCAT/BSD (or Linux) but **not** the NC PTP runtime
that `Tc2_MC2` needs. Install it on the PLC before doing anything else:

1. Add the Beckhoff apt repository **with authentication** to
   `/etc/apt/sources.list.d/`, per
   https://infosys.beckhoff.com/english.php?content=../content/1033/beckhoff_rt_linux/17350409995.html&id=
   (the page walks through fetching the Beckhoff apt key and the credentialed
   sources line).
2. On the PLC, install the motion runtime:
   ```sh
   sudo apt update
   sudo apt install tf5000-nc-ptp-xar
   ```
3. Restart the TwinCAT runtime so it picks up the new XAR component.

Without this package, the project will compile in XAE but activation will
fail with `port 500` (the NC task's AMS port) not present:

```
Sending ams command >> Init4\IO: Download Task Attrib: NC: new startup >>
AdsError: 6 (0x6, GLOBAL: target port not found [port 500]) << failed!
```

That's the symptom — install the package, restart the runtime, re-activate.

## 1. EtherCAT master

`I/O → Devices → Add New Item → EtherCAT → EtherCAT Master`. Scan for boxes.
Expected topology (from [Beckhoff stack](#beckhoff-stack) above):

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

## 2. EL7342 SDO configuration (per-channel motor + encoder)

The EL7342 ships with conservative defaults that won't drive a small DC
gearmotor correctly. Before configuring the NC axes, set the per-channel
CoE SDOs in XAE → `Term 4 (EL7342)` → **CoE Online** tab.

### Sources of truth

Prefer the local Beckhoff sources over the infosys web pages (the latter
are frames-based and don't decode cleanly):

- ESI: `/Users/william/Downloads/Beckhoff_EtherCAT_XML/Beckhoff EL73xx.xml`
  — canonical CoE object dictionary per device revision. Search for
  `<Index>#x8020</Index>` to see the full motor-settings layout.
- Manual: `/Users/william/Documents/EtherCAT/el73x2_en.pdf`
  — § "EL7342 — Object description and parameterization". The motor
  settings table starts at "Index 8020 DCM Motor Settings Ch.1".

### Per-channel object map

| Index | Object | Notes |
|---|---|---|
| `0x8000` | ENC Settings Ch.1 | encoder input config |
| `0x8010` | ENC Settings Ch.2 | encoder input config (channel offset = `0x10`) |
| `0x8020` | DCM Motor Settings Ch.1 | electrical limits + encoder hint |
| `0x8021` | DCM Controller Settings Ch.1 | current-loop `Kp`/`Ki`, windows, filter |
| `0x8022` | DCM Features Ch.1 | operation mode (auto / vel / pos), invert, etc. |
| `0x8023` | DCM Outputs Ch.1 | |
| `0x8030` | DCM Motor Settings Ch.2 | mirror of `0x8020` |
| `0x8031` | DCM Controller Settings Ch.2 | mirror of `0x8021` |
| `0x8032` | DCM Features Ch.2 | mirror of `0x8022` |
| `0x8033` | DCM Outputs Ch.2 | mirror of `0x8023` |

### DCM Motor Settings — `0x8020` (ch.1) / `0x8030` (ch.2)

Both channels take the same values (the rotators are identical). Indexes,
names, units, and defaults below are verbatim from the manual; the
"Ch.1 / Ch.2" column is what to write at bring-up.

| Sub | Name | Unit | Default | Ch.1 (`0x8020`) / Ch.2 (`0x8030`) | Derivation |
|---|---|---|---|---|---|
| `:01` | Maximal current | 1 mA | 5000 | **`750`** | Pololu stall at 12 V |
| `:02` | Nominal current | 1 mA | 3500 | **`190`** | ≤25 % of stall (Pololu's continuous rule); = max-efficiency current |
| `:03` | Nominal voltage | 1 mV | 50000 | **`24000`** | Expected **supply** voltage on Up — *not* the motor nameplate. EL7342 trips `0xA020:05 Over voltage` if actual Up exceeds this by >10 %. Set to match Up rail (24 V here). Motor protection happens via `:01` current limit, not this field. |
| `:04` | Motor coil resistance | 0.01 Ω | 100 | **`1400`** | Measured DC resistance across the motor leads = `14 Ω`. The V_stall/I_stall extrapolation gives `16 Ω`, but bench-measured is the truth — brush voltage drop accounts for the difference. Measure with a multimeter, rotate the shaft, take the minimum stable reading. |
| `:05` | Reduced current (positive) | 1 mA | 2000 | **`2000`** (default) | Direction-specific torque cap (manual's "Reduced" name is misleading — this is *not* an idle-current setting). `:01 Maximum current = 750 mA` does the real limiting; leave at default. Setting `0` here causes `0xA020:03 Torque overload` because the drive can't produce torque in that direction. |
| `:06` | Reduced current (negative) | 1 mA | 2000 | **`2000`** (default) | Same — leave at default. |
| `:07` | Encoder increments (4-fold) | counts | 0 | **`8192`** | Encoder counts per **encoder** revolution after 4-fold quadrature decoding: `2048 cpr × 4 = 8192`. Setting `0` here stops the drive from computing velocity feedback at all (motor won't move). The gearbox is invisible to this field — the encoder is the velocity source. |
| `:08` | Maximal motor velocity | 1 rpm | 0 | _leave 0_ | NC handles velocity limits; only set if a tighter EL7342-side cap is needed |
| `:0C` | Time for switch-off at overload | 1 ms | 200 | _default_ | Tune only if false overload trips |
| `:0D` | Time for current lowering at overload | 1 ms | 2000 | _default_ | Tune only if false overload trips |
| `:0E` / `:0F` | Torque auto-reduction threshold | 1 % | 0 | _default_ | Off by default; not used for our continuous-rotation prisms |

### DCM Features — `0x8022` (ch.1) / `0x8032` (ch.2)

| Sub | Name | Value | Why |
|---|---|---|---|
| `:01` | Operation mode | **`1` (Velocity direct)** | Leaves the EL7342 as an open-loop torque amplifier and lets NC PTP close the position loop alone. The default `0 (Automatic)` makes the EL7342 close an inner velocity loop in parallel with NC's outer position loop — they fight and produce large-amplitude oscillation (≥ 30°) on a constant-velocity command. |

`0x8021` (current loop gains) and `0x8023` (velocity loop gains) become
irrelevant once Operation mode = `1` — leave them at defaults. If NC
tracking later needs fine-tuning, adjust NC's `Kv` position-controller
factor, not the EL7342 SDOs.

### Bench-learned caveats

- **`:03 Nominal voltage` is the supply-side expectation, not the
  motor's nameplate.** The drive triggers `0xA020:05 Over voltage` when
  the actual Up rail exceeds `:03` by more than 10 %. With Up = 24 V,
  set `:03 = 24000` regardless of what the motor's plate says — motor
  protection is the job of `:01 Maximum current`, not `:03`.
- **`:07 Encoder increments (4-fold)` is per *encoder* revolution, not
  per motor revolution.** Set to `cpr × 4 = 8192` for the RM08ID 11B.
  The gearbox is invisible to this field — the EL7342 closes its
  velocity loop on encoder feedback regardless of what's between the
  encoder and the motor. Setting `0` disables velocity computation
  entirely and the motor won't move at all.
- **`:05` / `:06` are direction-specific torque caps, not idle holding
  current.** Leave at the `2000 mA` default. Setting `0` trips
  `0xA020:03 Torque overload` because the drive is asked for torque it's
  not allowed to produce. (The self-locking 986:1 gearbox handles
  holding torque mechanically — we don't need a holding-current SDO.)

After changing any SDO, click **Activate Configuration** in XAE and
re-power-cycle the terminal if XAE warns the change is "Online only"
(otherwise it reverts on next boot).

## 3. NC task and axes

`Motion → Add New Item → NC/PTP NCI Configuration`. Inside it:

| Axis name | Type | Encoder | Drive |
|---|---|---|---|
| `AxisA` | Continuous (rotary) | Incremental, EL7342 ch.1 | EL7342 ch.1 |
| `AxisB` | Continuous (rotary) | Incremental, EL7342 ch.2 | EL7342 ch.2 |

### Encoder scaling

| NC axis parameter | Value | Meaning |
|---|---|---|
| Unit | `°` (degrees) | Switch from the default mm — set in the axis "Unit" combo |
| Scaling Factor Numerator | `360.0` | degrees per encoder turn |
| Scaling Factor Denominator | `2048` | counts the EL7342 reports per encoder turn |
| → Position resolution | ≈ 0.1758° / count | `360 / 2048` |
| Modulo Factor | `360.0` | continuous rotation |

The denominator is the empirical count the EL7342 reports per rev, not
the encoder's nameplate cpr × 4. RLS's "2048 cpr" for the 11B code
already maps 1:1 onto what the EL7342 sees in its default mode — no
further multiplication needed. If you ever swap the encoder or the IO
slice, sanity-check by jogging the axis exactly one revolution by hand
and reading the count delta back in the NC online view before trusting
the formula.

### Velocity / acceleration parameters (motor-dependent)

Derived from the Pololu 3046 specs in [Part 1](#pololu-3046-motor-rotators-a-and-b):
no-load output speed at 12 V = 35 RPM = `210 °/s`; max-efficiency speed
= 27 RPM = `162 °/s`. Convert to °/s by multiplying RPM × 6.

| NC axis parameter | Value | Derivation |
|---|---|---|
| Reference Velocity | `210 °/s` | No-load output speed at 12 V — what 100 % drive output achieves; used for feed-forward |
| Maximum Velocity | `162 °/s` | Max-efficiency point — keeps the motor in its safe operating band even at peak commanded speed |
| Maximum Acceleration | `1000 °/s²` | Plenty of headroom above the PLC-side `GVL_Cfg.rRotatorAccel = 60 °/s²` request; prism inertia is small |
| Maximum Deceleration | `1000 °/s²` | Same |
| Jerk | `0` (disabled) | Low-inertia axis, no need for jerk shaping |

Manual jog velocities for bench testing live on the axis's **Functions**
subpage (not Parameter); set them when you actually need to jog from
XAE — `30 °/s` fast, `5 °/s` slow are sensible starting points.

The PLC-side defaults in [`plc/GVLs/GVL_Cfg.st`](../plc/GVLs/GVL_Cfg.st)
request `rRotatorVelocity = 30 °/s` and
`rRotatorAccel = rRotatorDecel = 60 °/s²` — these are what `FB_Rotator`
passes to `MC_MoveAbsolute`. They're well under the NC ceilings above,
so the NC axis won't clip a tracking dispatch. Bump them only if
tracking moves start arriving slower than the `ADC_CONTROL_INTERVAL_S`
tracking-loop period (default 30 s).

### Limits and monitoring

- **Position Lag Monitoring** — enable with a max position lag of
  `5 °`. Typical tracking moves are well under 10°, so a 5° lag means
  the axis is fighting something (mechanical jam, wrong scaling,
  encoder lost). The default 1 mm = ~6 counts is too tight for a low-bandwidth
  closed loop on a small DC motor; raise it to `5 °` to avoid false trips.
- **Soft limits** — disabled (continuous rotation; the prisms can
  rotate freely past 360°). The modulo factor handles wrap.
- **Drive error reaction** — default (stop and report).
- **Parameter → Limit Switches**: enable software end-stops if the optic
  housing demands it; the prisms are continuous so usually leave disabled.

Link each NC axis's "Drive" and "Encoder" to the EL7342 channel via
right-click → Link To.

### Link the PLC's `AXIS_REF` instances to the NC axes (manual)

The PLC's `MAIN.st` declares `Axis_A_ref : AXIS_REF` and
`Axis_B_ref : AXIS_REF`. These must be linked **by hand** in System
Manager to the NC axes you just created — the PLC project carries the
ST source but can't know which NC axis to bind to. Without these links
`FB_Rotator` runs against a placeholder and nothing moves.

In XAE:

1. **MOTION → NC-Task → Axis 1 → PLC**: right-click → **Change Link…** →
   select **MAIN.Axis_A_ref** (under `<project name>` → MAIN).
2. **MOTION → NC-Task → Axis 2 → PLC**: same, link to **MAIN.Axis_B_ref**.
3. Activate the configuration.

Verify in the PLC online view: `MAIN.Axis_A_ref.NcToPlc.ActPos` should
read live values once the configuration is active. If it stays at 0
regardless of axis state, the link wasn't established.

## 4. Homing configuration

The encoder is incremental, so absolute position is lost on power cycle.
The WINERED drivetrain has **no separate limit switch** — only the
encoder's Z (index) pulse, wired directly into the EL7342's I1 (axis A)
/ I2 (axis B) input (the EL7342 accepts 5 V on its latch inputs; no
level shifter needed — see [§ Encoder Z signal direct to EL7342](#encoder-z-signal-direct-to-el7342-i1--i2)).

That means the Z pulse serves **two roles** in NC's two-phase homing:

- **Phase 1 (cam):** there's nothing to detect; we simulate a
  permanently-occupied cam in PLC via `MC_Home.bCalibrationCam`, per
  Beckhoff's documented pattern:
  > "If an axis is to be referenced without referencing cam, i.e. only
  > based on the sync pulse of the encoder, the referencing cam can be
  > simulated via the PLC program. The 'bCalibrationCam' signal is
  > initially activated and then canceled, if `Axis.NcToPlc.HomingState`
  > is equal or greater 4."
  > — [Tc2_MC2 / MC_Home](https://infosys.beckhoff.com/content/1033/tcplclib_tc2_mc2/70117515.html)
- **Phase 2 (sync):** NC's `Hardware Latch 1` reference mode arms the
  EL7342's external latch (`0x7000:02` for ch.1, `0x7010:02` for ch.2)
  and captures the encoder count on the **rising** edge of I1 — the
  leading edge of the Z pulse. Active-high, `(pos. edge)`.

[`plc/POUs/FB_Rotator.st`](../plc/POUs/FB_Rotator.st) drives
`bCalibrationCam` from `(Axis.NcToPlc.HomingState < 4)`. `MC_Home`
auto-links this input to `Axis.PlcToNc.ControlDWord.7`, which NC reads
as the cam status — no manual control-word writes are needed.

### NC config — Axis Encoder → Parameter, Homing group

| Field | Value | Notes |
|---|---|---|
| Reference Mode (Sync condition) | **`Hardware Latch 1 (pos. edge)`** for Axis A; **`Hardware Latch 2 (pos. edge)`** for Axis B | NC latches the encoder count on I1's / I2's rising edge — the leading edge of the active-high Z pulse. Drives `0x7000:02` / `0x7010:02` Enable latch extern. |
| Homing Sensor Source | **`Default: PLC Cam (MC_Home)`** | Routes NC to read the cam from `bCalibrationCam` (= `Axis.PlcToNc.ControlDWord.7`), not from a hardware digital input |
| Invert Direction for Sync Impulse Search | `FALSE` | Axis search direction during Phase 2 — positive is correct for our setup |
| Invert Direction for Homing Sensor Search | `FALSE` | Phase 1 cam is software-driven; direction is irrelevant |
| Home Position (Calibration Value) | bench-tuned (e.g. `0.0`) | Position the axis is set to after Phase 2 sync. NC parameter, *not* a runtime tunable. |
| Reference Velocity (Fast) | bench-tuned (e.g. `30 °/s`) | Phase 1 search speed |
| Reference Velocity (Slow) | bench-tuned (e.g. `5 °/s`) | Phase 2 approach speed |

The four bench-tuned values above live in System Manager and are
established once during commissioning; they're not `GVL_Cfg` constants
because they're not runtime properties.

### EL7342 config — no SDO changes for homing

- `0x8022:30` / `0x8032:30 Invert digital input 1` — leave at factory
  default `FALSE`. Z is active-high on I1 / I2; the Reference Mode
  `(pos. edge)` matches directly.
- `0x8022:32` / `0x8032:32 Function for input 1` — leave at `0 Normal
  input`. The external-latch role on I1 / I2 is implicit; NC's
  `Hardware Latch 1 (pos. edge)` reference mode drives the
  `0x7000:02` / `0x7010:02` PDO directly.

### Trigger the homing

```st
GVL_Cmd.bAxisA_Home := TRUE;
```

(Or from Python: `await ctrl.plc.home_axis(Axis.A)`.) The rising edge runs
`MC_Home(HomingMode := MC_DefaultHoming, bCalibrationCam := …)`; on
completion `GVL_State.bAxisA_Done` pulses and `GVL_State.rAxisA_Position`
reads the configured Home Position.

### Verify

Before the first real homing attempt, confirm the Z latch path is healthy:

1. EL7342 → Process Data → DCM Inputs Ch.1 → watch `0x6000:0D Status of extern latch` (or the I1 status bit in the online view).
2. With the drive disabled, rotate the gearbox output by hand through a full revolution.
3. The bit should flicker HIGH once per revolution. If it never flickers → encoder Z wiring or 5 V supply problem; no NC config will save it.

After homing completes:

- `GVL_State.rAxisA_Position` ≈ NC's `Home Position` (typically `0.0`) within one count.
- Watching `Axis.NcToPlc.HomingState`: should transition `0 → … → 5` (= `HOMINGSTATE_DONE`) over the course of the run.
- Rotate the gearbox output 360° by hand. The position should return to its starting value within a count or two; ~1° drift per rev means the NC scaling is off (re-verify `360 / 2048`).

## 5. Linking GVL_IO

Each variable in [`plc/GVLs/GVL_IO.st`](../plc/GVLs/GVL_IO.st) carries a
`TcLinkTo` attribute that points at an EtherCAT input/output channel.
After importing the GVL into XAE, click "Reload All Mappings" to
materialise the links. Verify in `I/O → Mappings → PLC` that every
variable resolves.

If the topology in [§ 1 EtherCAT master](#1-ethercat-master) differs,
update the `TcLinkTo` strings in `GVL_IO.st` to match (XAE → right-click
variable → Properties → look at "Path"); the Beckhoff online docs cover
the attribute syntax in detail
(https://infosys.beckhoff.com/content/1033/tc3_plc_intro/3107974923.html).

## 6. ADS routing

The Python server talks to the PLC over ADS. Two things must be true:

- The CX9240 is reachable on the local network (10.8.104.50/24 by default;
  see [references/plc_configuration.md](references/plc_configuration.md)).
- A route exists from the developer/server machine to the CX9240
  (`pyads.add_route_to_plc(...)` or via TwinCAT Static Routes).

The Python server reads `ADC_PLC_AMS_NET_ID` from env — set it to the
CX9240's AMS net ID (typically `<plc_ip>.1.1`).

## 7. Activate + run

XAE → "Activate Configuration" → "Restart TwinCAT system in Run Mode".
Confirm the heartbeat (`GVL_State.bHeartbeat`) toggles in the online view,
then start the Python server.
