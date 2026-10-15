# PLC guidelines for Magellan instruments

How to build the TwinCAT 3 half of a new Magellan instrument that, like the
WINERED ADC, runs its mechanisms on a Beckhoff PLC behind a Python server. The
ADC in this repo is the worked example and the links point into it. Where the
ADC itself falls short of a rule, [§ 8](#8-where-the-adc-falls-short) says so:
copy the rule, not the gap.

## 1. Who owns what

```
lco-instrument-web ──WS──► Python server ──ADS──► TwinCAT PLC ──EtherCAT──► terminals ──► mechanism
```

| Layer | Owns | Never |
|---|---|---|
| Hardware | E-stop, hard limit switches cutting drive enable, fail-safe wiring | — |
| PLC | NC axes and their limits, homing, I/O decoding (switches → states), interlocks, fault detection, safe output states | Astronomy, telescope dialog, WS, user-facing text |
| Python | Algorithms, multi-device sequences, tracking loops, TCS, WS protocol, logs, error text | Real-time loops, interlocks |

- **The PLC is safe on its own**, with no client connected and under any
  sequence of ADS writes. A command that would harm the hardware (say, an
  absolute move on a bounded axis that isn't homed) is refused by the PLC with
  a reason code, not filtered by the client.
- **Software limits are the second line.** Beckhoff's NC manual says its
  monitoring functions "are not safety functions in the sense of safety
  technology". Whatever protects people or optics is wired.
- **No observing in the PLC.** Device FBs know rotators, slides and shutters,
  never elevation, parallactic angle or observing modes. That is what makes
  them reusable across instruments.
- **Recoverable from the UI.** Reset, re-home and re-enable are commands in the
  contract. Nothing at night should need XAE or a walk to the instrument.

## 2. Project layout

Copy the shape of [`plc/`](../plc/):

| Object | Holds | Rule |
|---|---|---|
| `GVL_IO` | Hardware-linked variables and `AXIS_REF`s | Declarations and link attributes only (§ 5) |
| `GVL_Cmd`, `GVL_State` | The ADS contract (§ 3) | Nothing else is public |
| `GVL_Cfg` | Constants and tunables | |
| `FB_<Device>`, `FB_<Device>Sim` | One FB per mechanism type | I/O arrives as inputs/outputs and the axis as `VAR_IN_OUT AXIS_REF`; never touches a GVL |
| `FB_<Instrument>Controller` | Composition root | The only POU that touches `GVL_Cmd`, `GVL_State`, `GVL_IO` |
| `MAIN` | One controller instance | |

- **Names** follow Beckhoff's
  [type](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/12073945483.html)
  and [variable](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/12073947403.html)
  prefixes: `FB_`, `F_`, `ST_`, `E_`, `I_`, `GVL_`, no prefix on programs; `b`,
  `n`, `f` (REAL/LREAL; the ADC's `r` is non-standard), `s`, `t`, `e`, `st`,
  `fb`, `a`, `ref`, `ip`. TE1200 Static Analysis can enforce them.
- **Attributes:** `{attribute 'qualified_only'}` on every GVL; `qualified_only`
  and `strict` on every enum, with an explicit base type (`) INT;`), because
  enums cross the wire.
- **Device FBs never see hardware directly.** Inputs in, outputs out: the same
  FB then runs against real I/O, a simulator or a unit test.
- **Share FBs as a library.** When a second instrument needs a device FB, move
  it into a versioned TwinCAT library instead of copying it. ESO's ELT
  framework ships each standard device that way, with its simulator
  ([FCF PLC libraries](https://www.eso.org/projects/elt/develop/ifw/ifw-fcf/sphinx/html/docs/plc.html)).

## 3. The ADS contract

`GVL_Cmd` and `GVL_State` are a protocol between two programs. Change them only
together with the Python driver and its simulator, in one commit.

- **One request per poll.** "If the PLC is processing one ADS request, it will
  completely work on this single ADS request BEFORE starting next PLC cycle"
  ([ADS](https://infosys.beckhoff.com/content/1033/tc3_adsdll2/124835083.html)),
  so one read returns one cycle's state. Group state per device in structs
  and read it all at once, with a sum read (pyads `read_list_by_name`) or
  `read_structure_by_name`. pyads documents that mixed-type structs need
  `{attribute 'pack_mode' := '1'}`.
- **Commands carry a sequence number.** The client writes the parameters and an
  incremented `nSeq` in one write. The PLC acts when `nSeq` changes, then
  echoes it as `nSeqAck` with a result code. The client can then tell accepted
  from rejected, and every variable has a single writer. (The ADC's "client
  sets a bit, PLC clears it" has two writers and no acknowledgement. RPC
  methods, `TcRpcEnable`, would avoid the handshake, but pyads has no support
  for calling them.) Desired states (slide in, shutter closed) stay plain
  levels, which the client may rewrite after a reconnect.
- **Publish levels, never pulses.** A 5 Hz poller misses a 10 ms pulse 19
  times in 20. Latch `Done` and errors until the next command or a reset.
- **Measured vs commanded.** Publish both, and raise a fault when they still
  disagree after the travel timeout. Where there is no sensor, say in the
  declaration comment that the state only echoes the command (ADC:
  `bShutter_Closed`).
- **Physical names, one inversion.** Commands name the physical result
  (`bShutter_Closed`), and wiring polarity is undone once, in the controller FB.
- **Liveness is a counter.** Publish `_TaskInfo[GETCURTASKINDEXEX()].CycleCount`
  ([task info](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/714821259.html)).
  A bit flipped every 10 ms and sampled every 200 ms aliases. If a mechanism
  must stop when the server dies, the client writes a counter too, and the PLC
  goes safe when it stalls.
- **Self-describing.** Publish `nInterfaceVersion`, `bSimulate` and I/O health
  (§ 5). At connect, the driver checks the version and that every expected
  symbol exists, and refuses to run otherwise.

```st
{attribute 'pack_mode' := '1'}
TYPE ST_AxisState :              // in GVL_State, written only by the PLC
STRUCT
    nSeqAck   : UDINT;           // nSeq of the last command handled
    eResult   : E_CmdResult;     // ACCEPTED, REJECTED_NOT_HOMED, ...
    fPosition : LREAL;           // deg
    bHomed    : BOOL;            // Axis.Status.Homed
    bBusy     : BOOL;
    bError    : BOOL;            // latched until RESET
    nErrorId  : UDINT;           // NC error code
END_STRUCT
END_TYPE

{attribute 'pack_mode' := '1'}
TYPE ST_AxisCmd :                // in GVL_Cmd, written only by the client
STRUCT
    nSeq    : UDINT;             // increment to issue eCmd
    eCmd    : E_AxisCmd;         // MOVE, HOME, HALT, RESET
    fTarget : LREAL;             // deg
END_STRUCT
END_TYPE
```

Translate error codes to text in Python, from Beckhoff's
[NC error codes](https://download.beckhoff.com/download/document/automation/twincat3/TwinCAT_NC_Error_Codes_EN.pdf).

## 4. Motion: NC axes and Tc2_MC2

- **Every motor is an NC PTP axis driven through
  [Tc2_MC2](https://download.beckhoff.com/download/Document/automation/twincat3/TwinCAT_3_PLC_Lib_Tc2_MC2_EN.pdf)**,
  Beckhoff's PLCopen motion library. No position loops or trajectory code in
  ST.
- **Limits live in the NC axis**: scaling, modulo, maximum velocity, soft
  limits, position-lag monitoring, homing mode and velocities. The NC rejects a
  velocity above Maximum Velocity, but acceleration, deceleration and jerk "are
  not checked"
  ([maximum dynamics](https://infosys.beckhoff.com/content/1033/tf50x0_tc3_nc_ptp/3263989131.html)),
  so clamp those in the wrapper. Record every NC value in the bring-up doc, as
  the ADC does ([§ 3–4](bring-up.md#3-nc-task-and-axes)).
- **One wrapper FB per axis kind**
  ([`FB_Rotator`](../plc/adc/adc/POUs/FB_Rotator.TcPOU)): one `MC_Power` per
  axis, plus `MC_Reset`, `MC_Home`, `MC_MoveAbsolute` or `MC_MoveModulo`,
  `MC_Halt` and `MC_Stop`.
- **Outputs follow `Execute`.** MC FBs start on the rising edge of `Execute`
  and hold `Done` / `Error` / `CommandAborted` while it stays high. If it has
  already fallen, "one of the outputs is set at the end of the command for a
  PLC cycle", and only for that cycle
  ([general rules](https://infosys.beckhoff.com/content/1033/tcplclib_tc2_mc2/70043531.html)).
  Hold `Execute` until one of them is set, or latch the outcome in that cycle,
  and call the FB every cycle while `Busy`. A busy instance ignores a new
  edge: to retarget a moving axis, trigger a second instance with
  `BufferMode := MC_Aborting`.
- **Read state from the axis, not from the action FBs.** Call
  `Axis.ReadStatus()` first thing each cycle (`Axis.Status` isn't refreshed
  otherwise), then publish `Status.Homed`, `.Error`, `.ErrorId`, `.ErrorStop`
  and `.NotMoving`. `Homed` is the NC's own "axis calibrated" flag, so no PLC
  latch is needed.
- **`MC_Halt` for normal stops, `MC_Stop` to abort.** `MC_Stop` locks the axis
  until its `Execute` falls. Beckhoff: "MC_Halt is preferable for normal
  movement sequences".
- **Continuous rotators.** On a modulo axis, `MC_MoveAbsolute` reads the target
  as an absolute position "in an infinite absolute coordinate system". From
  359°, a target of 1° therefore travels −358°. Use `MC_MoveModulo` with the
  target normalised to [0, 360) and `Direction := MC_Shortest_Way`, and set
  the encoder's *Tolerance Window for Modulo Start*
  ([modulo notes](https://infosys.beckhoff.com/content/1033/tcplclib_tc2_mc2/70100875.html)).
  If cables limit travel, make it a linear axis with soft limits instead.
- **Homing.** With an incremental encoder, "after starting the control, homing
  is required": the axis boots un-homed, homes only on command and, if it has
  end stops, refuses absolute moves until homed. `FB_Rotator` shows cam-less
  Z-pulse homing via `MC_Home.bCalibrationCam`. Where losing the reference at
  night is costly, specify absolute encoders.

## 5. Linking I/O and axes

- **Links live in source.** Declare every hardware variable in `GVL_IO` with
  [`TcLinkTo`](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/3107974923.html)
  and `AT %I*` / `AT %Q*`. The I/O map is then reviewed in diffs and rebuilt
  by a build, instead of being hand-clicked into the `.tsproj`. XAE marks
  attribute links with a blue icon and manual ones with a white icon. Copy the
  path from the channel's properties in XAE.
- **Name boxes, then link by name.** Rename each box after the scan
  (`Term 8 (EL2002)` → `DO_Slides`) and address it as `TIIB[name]`, which
  doesn't depend on scan order or couplers. Rename before linking: renaming a
  box later doesn't update attribute strings.
- **Axes link by name too.** `{attribute 'TcNcAxis' := '<axis>'}` above an
  `AXIS_REF`
  ([TcNcAxis](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/3107990667.html))
  replaces the manual *Change Link* step.
- **A wrong path fails silently.** A `TcLinkTo` path that matches nothing is
  not a build error, and TwinCAT drops links it can't restore
  ([source-control manual](https://download.beckhoff.com/download/document/automation/twincat3/tc3_sourcecontrol_en.pdf)).
  After any change to `GVL_IO` or the I/O tree, check *I/O → Mappings*, or
  have a script diff the `TcLinkTo` variables against the `.tsproj` `<Link>`
  entries.
- **Link terminal health.** For each box, link `WcState^WcState` (0 = valid
  data) and `InfoData^State` (8 = OP). Beckhoff strongly recommends evaluating
  both ([slave diagnosis](https://infosys.beckhoff.com/content/1033/el1382/1037004555.html)).
  An unlinked `State` reads 0, so it also catches a wrong path; an unlinked
  `WcState` reads 0, which means "valid", so it doesn't. Inputs from an
  unhealthy box are a fault, not an open switch.
- **De-energized is benign.** Wire so that every output off (PLC stopped, sim
  mode, bus down, power cut) leaves the instrument safe. Say next to each
  output in `GVL_IO` what "off" does (ADC: shutter closed, diffuser in the
  beam).
- **Terminal settings live in the project.** Put every CoE (SDO) change in the
  terminal's *Startup* list. Values written only through *CoE Online* stay in
  that one terminal, and a replacement comes up with factory defaults
  ([CoE interface](https://infosys.beckhoff.com/content/1033/el40xx/1036982411.html)).

```st
{attribute 'qualified_only'}
VAR_GLOBAL
    {attribute 'TcLinkTo' := 'TIIB[DO_Slides]^Channel 2^Output'}
    bSlideA_DeployOut AT %Q* : BOOL;    // off = slide OUT
    {attribute 'TcLinkTo' := 'TIIB[DO_Slides]^InfoData^State'}
    nDO_Slides_State AT %I* : UINT;     // 8 = OP
    {attribute 'TcNcAxis' := 'Axis 1'}
    AxisA : AXIS_REF;
END_VAR
```

## 6. Simulation

| Simulator | Exercises | Needs |
|---|---|---|
| Python ([`plc_sim.py`](../src/adc_winered/plc_sim.py)) | Controller, WS protocol, UI; the CI gate | Nothing |
| PLC in sim mode | PLC logic, Tc2_MC2 sequencing, NC parameters, the ADS contract | A TwinCAT runtime |
| Hardware | Everything else | The instrument |

- **Simulate NC axes in the NC.** From TwinCAT 3.1.4026 an axis has a
  *Simulation* checkbox (axis → Settings): "the link to the I/O is ignored and
  a simulation drive and encoder are used"
  ([InfoSys](https://infosys.beckhoff.com/content/1033/tc3_system/10663188107.html)).
  The real wrapper FB, NC parameters and limits all run; only the drive is
  fake. A simulated encoder gives hardware-latch homing nothing to latch, so
  in sim home with `MC_Direct` or `MC_ForceCalibration`, in one small branch.
  The ADC plan weighs this approach
  ([*Collapse `FB_RotatorSim`…*](plans/winered-adc.md#collapse-fb_rotatorsim-into-nc-simulated-axes));
  a new instrument should start with it.
- **Other devices: a sim FB behind an interface.** `FB_Slide` and
  `FB_SlideSim` both `IMPLEMENTS I_Slide`. The controller picks one at startup
  and calls it through the interface. The compiler then enforces parity, and
  there is one call site instead of an `IF bSimulate` per device
  ([dependency inversion in ST](https://stefanhenneken.net/2022/02/09/iec-61131-3-solid-the-dependency-inversion-principle/)).
- **Sim is visible and never drives outputs.** Real outputs stay de-energized
  while simulating, as in
  [`FB_AdcController`](../plc/adc/adc/POUs/FB_AdcController.TcPOU).
  `bSimulate` is published and the UI shows it. Keep the flag non-persistent
  with default `FALSE`, as the ADC does, so a restart always comes back real.
  For a permanently simulated bench PLC, consider a
  [project variant](https://download.beckhoff.com/download/Document/automation/twincat3/Variant_Management_EN.pdf)
  rather than hand edits.
- **Parity is behavioural.** The same inputs give the same state at the ADS
  surface. That includes handshake timing (busy before done, latched errors),
  not just kinematics. Make faults injectable (stuck slide, lag error, dead
  terminal) so error paths get exercised.
- **The Python sim follows the PLC.** Change `plc_sim.py` in the commit that
  changes the contract. Run one scenario against both: `PlcSim` in CI, and the
  PLC in sim mode over ADS on the bench.
- **Unit-test device FBs** with [TcUnit](https://github.com/tcunit/TcUnit)
  (MIT, writes xUnit XML from the PLC).
- **No bench CX?** The
  [Usermode Runtime](https://download.beckhoff.com/download/Document/automation/twincat3/TC170x_TC3_Usermode_Runtime_EN.pdf)
  (4026+, free engineering edition) runs the same PLC code on Windows x64. It
  has no EtherCAT and no real time, needs an x64 build alongside the CX9240's
  Arm one, and NC PTP support should be checked for your build.
  [TE1111](https://infosys.beckhoff.com/content/1033/te1111_ethercat_simulation/576831115.html)
  EtherCAT hardware-in-the-loop is usually more than an instrument needs.

## 7. Build, deploy, version control

- **Runtime.** On a CX9240 (Beckhoff RT Linux), install NC PTP before the first
  activation (`sudo apt install tf5000-nc-ptp-xar`), or activation fails on AMS
  port 500 ([bring-up § 0](bring-up.md#0-plc-runtime--install-the-nc-ptp-package)).
- **Pin versions.** Pin the XAE build (*SYSTEM → General → Pin Version*) to the
  runtime's, and fix every library with *Set to Effective Version*, because the
  default placeholder is `*`, always newest
  ([libraries](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/12049843211.html)).
- **Source control.** Commit the XAE project and ignore what XAE regenerates
  ([TwinCAT3.gitignore](https://github.com/github/gitignore/blob/main/TwinCAT3.gitignore)).
  Per Beckhoff's
  [source-control manual](https://download.beckhoff.com/download/document/automation/twincat3/tc3_sourcecontrol_en.pdf):
  store NC axes, boxes and the PLC instance as independent project files
  (`.xti`) so a change touches one small file; turn off *Write product version
  in files* (PLC project → Advanced) so another XAE build doesn't rewrite every
  file; merge with TcProjectCompare.
- **Tasks.** One PLC task (10 ms) runs everything that touches an axis; NC SAF
  stays at its default 2 ms. Read the cycle time from
  `_TaskInfo[GETCURTASKINDEXEX()].CycleTime` (100 ns units) rather than a
  constant kept in sync by hand.
- **Persistence.** Decide early what must survive a power cut (tunables, last
  commanded positions). `PERSISTENT` data is written only on an orderly
  shutdown, so use the CX9240's 1-second UPS (`FB_S_UPS_BAPI` in the fastest
  task), or `FB_WritePersistentData` when values change
  ([CX9240 manual](https://download.beckhoff.com/download/document/ipc/embedded-pc/embedded-pc-cx/cx9240_en.pdf)).
  Never persist "homed" for an incremental encoder.
- **Network.** The AMS Net ID is not the IP address (the ADC's CX answers to
  `5.171.247.155.1.1`). pyads speaks plain ADS only: it needs a route on the
  PLC with *Secure ADS* off, and RT Linux's firewall doesn't open TCP 48898 by
  default. At LCO, plain ADS doesn't cross VLANs anyway, so tunnel over SSH
  ([running.md](running.md#reaching-the-plc-over-ssh)).

## 8. Where the ADC falls short

| ADC today | Rule |
|---|---|
| `GVL_IO` links the slide I/O to `Term 2 (EL2002)` / `Term 3 (EL1084)`, but the committed `adc.tsproj` names them `Term 8` / `Term 9`, so none of the six slide variables is linked | § 5 name boxes, check mappings |
| Move, home, stop and reset fire one-cycle `Execute` pulses, so `bAxis*_Done` and move/home errors last one 10 ms cycle and the 5 Hz poller rarely sees them; both simulators hold `done` | § 3 levels, § 4 Execute |
| `bReady` and `bAxis*_Error` come from action-FB outputs; `MC_ReadStatus` runs but nothing reads it | § 4 read the axis |
| `FB_Slide` reports `OUT` with no error while commanded `IN` (e.g. no air), and the slide command isn't echoed | § 3 measured vs commanded |
| `plc_client.read()` makes 17 separate `read_by_name` calls, not one snapshot | § 3 one request |
| Heartbeat is a toggled bit; `GVL_State` has no interface version, `bSimulate` or I/O health | § 3 |
| Rotator targets reach `MC_MoveAbsolute` un-normalised on a modulo axis, so a move can go the long way round | § 4 continuous rotators |
| EL7342 motor SDOs are set through *CoE Online*; the startup list in `adc.tsproj` has none of them | § 5 terminal settings |
| `AXIS_REF`s linked by hand; libraries on `*`; *Write product version* on; one monolithic `.tsproj`; hand-synced `rCycleSeconds` | § 5, § 7 |
| `FB_RotatorSim` bypasses Tc2_MC2 | § 6 (already a plan follow-up) |

## Prior art

- **ESO ELT**,
  [Fieldbus Control Framework](https://www.eso.org/projects/elt/develop/ifw/ifw-fcf/sphinx/html/docs/plc.html).
  The closest astronomy precedent: TwinCAT device libraries with a simulator
  FB per device, including an ADC built from two motors.
- **SLAC LCLS**,
  [lcls-twincat-motion](https://github.com/pcdshub/lcls-twincat-motion). One
  motion library shared by many PLCs, whose projects link boxes as
  `TIIB[name]`.
- **Stefan Henneken**, [IEC 61131-3 series](https://stefanhenneken.net/):
  interfaces, `FB_init` injection and SOLID in Structured Text.
- **Beckhoff**,
  [programming conventions](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/12049233675.html).
