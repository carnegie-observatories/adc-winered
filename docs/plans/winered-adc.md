# WINERED ADC Implementation Plan

## Context

WINERED needs an Atmospheric Dispersion Corrector (ADC) control stack on new hardware. The reference implementation at `/Users/william/workspace/adc` is an Objective-C macOS app talking directly to Acromag I/O over Modbus and to a Magellan TCS over a custom TCP protocol. That stack is being retired for WINERED.

The replacement runs on a **Beckhoff CX9240** PLC (TwinCAT 3, Linux runtime, Structured Text) for low-level motion and I/O, and on a separate **Python server** for algorithms, telescope dialog, and the external WebSocket API consumed by `lco-instrument-web`. The split is the same house pattern already used by DCU and PFS.

The current working directory contains throw-away prototypes (FastAPI/REST server, NiceGUI dashboard, software-only ST sim). The user has decided to **start clean**; the prototypes are read-only references for working pyads, MagIO TCP, and TCS sim code that can be cherry-picked but not built upon directly.

**Goal of this change:** ship a PLC project + a uv-managed Python package that together (a) drive the WINERED ADC hardware, (b) compute prism positions for the default IB dispersion-correction mode, and (c) expose the canonical LCO WebSocket protocol so existing UI clients work unchanged.

## Hardware scope (from `/Users/william/Downloads/WINERED ADC electronics - Pinout Incr Encoder.csv`)

| Subsystem | Actuator | Feedback | Beckhoff slice |
|---|---|---|---|
| Rotator A (prism A) | Pololu 3046 DC motor | Incremental encoder A/B/Z (5V) | EL7342 ch.1 (motor + encoder), EL9505 |
| Rotator B (prism B) | Pololu 3046 DC motor | Incremental encoder A/B/Z (5V) | EL7342 ch.2 (motor + encoder), EL9505 |
| Slide A (Deploy A) | 24V solenoid (Clippard) | IN + OUT limit switches | EL2002 ch.2 out, EL1084 ch.3/4 in |
| Slide B (Deploy B) | 24V solenoid (Clippard) | IN + OUT limit switches | EL2002 ch.1 out, EL1084 ch.1/2 in |

CPU/IO budget: Us 1A, Up max 10A. PLC static IP per `docs/plc_configuration.md` (10.8.104.50/24).

## High-level architecture

```
[lco-instrument-web]  --WS:52403-->  [adc-winered Python server]  --ADS-->  [TwinCAT runtime on CX9240]  --EtherCAT-->  [EL7342/EL2002/EL1084]
                                              |
                                              +--TCP:5800-->  [Magellan TCS]  (or tcs_sim for dev)
```

The Python server is **headless**. All UI lives in `lco-instrument-web`. The PLC owns motion safety (limits, max velocity, e-stop) and exposes only sanitised commands/state over ADS. The Python server owns the correction algorithm, the tracking loop, the WS frame plumbing, and TCS dialog.

## PLC project (TwinCAT 3, Structured Text)

New TwinCAT solution at `plc/` in the repo (replacing the existing `plc_program/`). Layout:

```
plc/
  WineredADC.sln
  WineredADC/                 # TwinCAT project
    POUs/
      MAIN.TcPOU              # entry, dispatch
      FB_Rotator.TcPOU        # one axis controller (used twice)
      FB_Slide.TcPOU          # one deploy slide (used twice)
      FB_RotatorSim.TcPOU     # sim variant of FB_Rotator
      FB_SlideSim.TcPOU       # sim variant of FB_Slide
      FB_AdcController.TcPOU  # composes the four FBs, exposes ADS surface
    GVLs/
      GVL_IO.TcGVL            # hardware-linked vars (TcLinkTo attributes)
      GVL_Cmd.TcGVL           # ADS-writable command surface
      GVL_State.TcGVL         # ADS-readable telemetry surface
      GVL_Cfg.TcGVL           # tunables (vel, accel, tolerance, sim flag)
    Mappings/                 # NC axis -> EL7342 link, MC2 axis params
```

### Hardware linking (TcLinkTo)

Per the Beckhoff `TcLinkTo` pattern, every I/O variable in `GVL_IO` is declared with the attribute pointing at the EtherCAT path. Examples:

```
{attribute 'TcLinkTo' := '.PnpOut1 := TIID^Device 1 (EtherCAT)^Term 4 (EL2002)^Channel 2^Output'}
bSlideA_Deploy : BOOL;

{attribute 'TcLinkTo' := '.IN := TIID^Device 1 (EtherCAT)^Term 3 (EL1084)^Channel 4^Input'}
bSlideA_LimitIn : BOOL;

{attribute 'TcLinkTo' := '.IN := TIID^Device 1 (EtherCAT)^Term 3 (EL1084)^Channel 3^Input'}
bSlideA_LimitOut : BOOL;
```

(EL7342 channels are bound to NC axes — not GVL variables — via System Manager mapping.)

### Motion (Tc2_MC2 + NC tasks)

Two NC axes (`AxisA`, `AxisB`) configured under a single NC task. Each `FB_Rotator` instance wraps:

- `MC_Power` (enable)
- `MC_MoveAbsolute` (target angle, velocity from `GVL_Cfg.rRotatorVel`, accel from `rRotatorAcc`)
- `MC_Stop` (halt)
- `MC_Reset` (clear error)
- `MC_ReadStatus` / `MC_ReadActualPosition` (publish encoder angle + busy/done flags)
- `MC_Home` against the encoder Z-pulse (incremental encoders, so a homing routine is required; `MC_Home` with `HomingMode := MC_DefaultHoming` against the Z reference)

Encoder scaling and modulo-360 wrap are set in the axis parameters (System Manager), not in code. Soft limits are likewise configured at the axis, not gated in ST.

### Slide control (`FB_Slide`)

Pure I/O FB. On `bDeploy := TRUE`, asserts the solenoid output; reports a discrete state derived from limit switches:

```
state := SLIDE_OUT  when (bLimitOut AND NOT bLimitIn)
      := SLIDE_IN   when (bLimitIn  AND NOT bLimitOut)
      := SLIDE_MOVING otherwise (with a tStuck timeout -> SLIDE_ERROR)
```

### Simulator mode

Toggled by `GVL_Cfg.bSimulate : BOOL`. `FB_AdcController` instantiates `FB_RotatorSim`/`FB_SlideSim` when `bSimulate`, otherwise the real FBs. Behaviour of the sim FBs:

- `FB_RotatorSim` integrates position toward target at `rRotatorVel`, sets `bBusy`/`bDone` as MC2 would, ignores actual EL7342 vars.
- `FB_SlideSim` flips limit state after a configurable settle time (default 500 ms) when `bDeploy` changes.

The split keeps real hardware paths from drifting from sim paths — both expose the same outputs through identical FB interfaces. Tests and the Python server cannot tell the two apart by inspecting `GVL_State`.

### ADS surface (only these symbols are visible to the Python server)

```
GVL_State.rAxisA_Position : LREAL    (degrees, 0..360 modulo)
GVL_State.rAxisB_Position : LREAL
GVL_State.bAxisA_Busy / bAxisA_Done / bAxisA_Error / nAxisA_ErrorId
GVL_State.bAxisB_Busy / bAxisB_Done / bAxisB_Error / nAxisB_ErrorId
GVL_State.eSlideA : E_SlideState   (IN | OUT | MOVING | ERROR)
GVL_State.eSlideB : E_SlideState
GVL_State.bHeartbeat (toggles every cycle, used by Python for liveness)

GVL_Cmd.rAxisA_Target / rAxisB_Target : LREAL
GVL_Cmd.bAxisA_Go / bAxisB_Go : BOOL  (rising edge triggers MC_MoveAbsolute)
GVL_Cmd.bAxisA_Stop / bAxisB_Stop : BOOL
GVL_Cmd.bAxisA_Home / bAxisB_Home : BOOL
GVL_Cmd.bAxisA_Reset / bAxisB_Reset : BOOL
GVL_Cmd.bSlideA_Deploy / bSlideB_Deploy : BOOL  (level: TRUE = IN)
```

This is intentionally minimal — the Python server holds all higher-level logic.

## Python server (uv package)

New package at the repo root, replacing all top-level `*.py` prototypes.

```
pyproject.toml                 # uv-managed, entry: adc-winered = adc_winered.cli:main
src/adc_winered/
  __init__.py
  cli.py                       # `adc-winered serve` startup, arg/env parsing
  config.py                    # pydantic settings: PLC ip/route, TCS host/port, WS port, intervals
  plc_client.py                # pyads wrapper; reads/writes the GVL_State/Cmd symbols above
  plc_sim.py                   # in-process fake implementing the same protocol (no ADS)
  tcs_client.py                # Magellan TCP client (port of magio.py concept, async)
  tcs_sim.py                   # in-process fake of TCS (port of tcs_sim.py concept)
  correction.py                # pure function: (elevation, rotator) -> (target_a, target_b)
  controller.py                # state machine + tracking loop
  ws/
    server.py                  # websockets-lib server on :52403
    envelope.py                # frame types: hello / state / event / ack / subscribe / unsubscribe / cmd
    topics.py                  # registry: status, lens, telescope, logs
    commands.py                # dispatch table: setADCInsertion, setControlMode, moveLens, setAutoUpdate, setRunning
    logs.py                    # 500-entry ring buffer + live event broadcast
tests/
  test_correction.py
  test_plc_client.py           # uses plc_sim
  test_tcs_client.py           # uses tcs_sim
  test_ws_protocol.py          # hello/subscribe/cmd/ack contract round-trip
  test_controller.py           # state-machine transitions, tracking loop tick
```

### Key design choices

**Correction algorithm (`correction.py`).** Port the IB-mode formula from the reference (`/Users/william/workspace/adc/src/ADC/ADC_Controller.m:774-809`) verbatim, isolated as one pure function:

```python
def ib_targets(elevation_deg: float, rotator_deg: float) -> tuple[float, float]:
    z = 90.0 - elevation_deg
    y = min(1.0, math.tan(math.radians(z)) / 1.665)  # 1.665 = tan(59.01°)
    a = math.degrees(math.acos(y))                    # prism separation
    r = 90.0 - rotator_deg                            # parallactic transform
    return (r + 180.0 - a, r - 180.0 + a)             # (target_A, target_B), degrees
```

The constant 1.665 and the geometry stay in this file; if mode 1/2 are needed later, they slot in as siblings.

**PLC client (`plc_client.py`).** Thin async wrapper around `pyads`. Polls `GVL_State.*` at 5 Hz on a background task into an in-memory snapshot; commands write `GVL_Cmd.*` and pulse the `bGo` rising edge. Reuse the symbol names from the prototype `ads_plc.py` for familiarity but re-derive the layout from `GVL_State`/`GVL_Cmd` above (not the prototype's `GVL.*` flat namespace).

**PLC sim (`plc_sim.py`).** Implements the same interface as `plc_client.py`. The package selects between real and sim at startup via config (`ADC_PLC_MODE=sim|real`). This means the Python server can run end-to-end with no TwinCAT runtime present — useful for protocol-level tests and developing against the WS API.

**TCS client (`tcs_client.py`).** Re-implements the airmass/rotator query path used by `magio.py`. Async, with a `tcs_sim.py` analogue for offline testing. Polls elevation + rotator at 1 Hz, publishes into the `telescope` topic.

**Controller (`controller.py`).** Async state machine with explicit states: `INIT → IDLE → TRACKING ⇄ MOVING → IDLE`, plus `ERROR`. The tracking loop runs at `control_interval` (default 30 s, matching reference), recomputes targets from the latest TCS sample, and dispatches moves only if the delta exceeds the deadband (≈ reference `pulseRange`).

**WebSocket server (`ws/`).** Built on the `websockets` library (already in the Python ecosystem; no FastAPI). One asyncio task per connection. The server:

1. Sends `hello` on connect with `{protocol_version, app: "adc", topics: ["status","lens","telescope","logs"]}`.
2. Tracks subscriptions per connection. On `subscribe`, immediately replays the latest snapshot for each named topic; on subsequent topic change broadcasts only to subscribers.
3. Routes `cmd` frames through a dispatch table whose handlers return `(ok, result|error)`; the server wraps that into an `ack` keyed by the client-supplied `id`. Long-running moves return `{requested: true}` immediately and let `state`/`event` frames carry progress.
4. Funnels Python `logging` records into the `logs` topic (500-entry ring buffer + live `event` broadcast, ≤100 entries/sec cap).

Error codes constrained to the closed set from the spec: `busy`, `missing_argument`, `invalid_argument`, `hardware`, `plc_unreachable`. No auth/TLS in v1.

**Reusable from prototypes (read-only, then transcribe).** `magio.py` (TCS protocol bytes), `tcs_sim.py` (simulator response shapes), `ads_plc.py` (pyads idioms and the `GVL.*` symbol naming convention). Do not import from these files; copy what's correct into the new package and discard the rest.

## Repository conventions

### `AGENTS.md` (repo root)

A single-page brief for any future agent (or human) opening this repo cold. Lean — under one screen. Sections:

- **What this is** — one-paragraph mission: WINERED ADC control stack (PLC + Python server).
- **Layout** — point at `src/adc_winered/`, `plc/`, `docs/`, `tests/`.
- **Run it** — `uv run adc-winered serve` for headless server, `ADC_PLC_MODE=sim ADC_TCS_MODE=sim` env vars for fully offline mode, link to `docs/running.md` for the long form.
- **Test it** — `uv run pytest` (CI), `docs/testing.md` for bench/instrument steps.
- **Boundaries that matter** — PLC owns motion safety, Python owns algorithm + WS API, never invert. WS protocol is closed-set (see `docs/protocol.md`); do not add frame types or error codes unilaterally.
- **House rules** — git workflow: plan file committed first on a `plan/<slug>` branch, then one commit per phase on the same branch; no `Co-Authored-By` lines; no "Generated with Claude Code" attribution in commits or PRs.
- **Links** — to `/Users/william/workspace/lco-ansible/docs/ws-protocol.md`, to the reference impl at `/Users/william/workspace/adc`, to the canonical client at `/Users/william/workspace/lco-instrument-web`.

### `docs/` folder

Lean markdown, scan-friendly, one topic per file. No MkDocs, no site generator — files are read directly on GitHub.

```
docs/
  README.md          # index: short overview + links to the files below
  architecture.md    # the PLC/Python split, ADS surface, WS surface (1 diagram in ASCII)
  hardware.md        # the EL7342/EL2002/EL1084/EL9505 wiring (table from the CSV) + Pololu motor + Clippard valve refs
  plc.md             # how the TwinCAT project is organised: GVLs, FBs, sim mode, how to rebuild/deploy
  protocol.md        # WS frame shapes, topics, commands, error codes — copy from lco-ansible spec, scoped to ADC
  correction.md      # the IB-mode math (one-pager), derivation note, where to extend for new modes
  running.md         # how to start the server (real, sim, mixed), env vars, ports
  testing.md         # `uv run pytest` for CI; bench/instrument verification steps from §Verification
```

Keep each file under ~150 lines. Prefer tables and short bullets. If something belongs in code comments instead of docs, put it in code comments.

## Phased delivery (one commit per phase)

Per `feedback_commit_plan_before_execution.md` and `feedback_per_phase_commits.md`: commit the plan file on a new `plan/winered-adc` branch first, then land one commit per phase on the same branch, stopping for review between phases.

- **Phase 0 — Plan commit.** Mirror this plan into the repo (e.g., `docs/plans/winered-adc.md`), create branch `plan/winered-adc` off `main`, commit the plan, push.
- **Phase 1 — Scaffolding.** `pyproject.toml` (uv, entry point), `src/adc_winered/` package skeleton with empty modules, `tests/` skeleton, `docs/` skeleton (the eight files above as stubs), `AGENTS.md`, archive top-level `*.py` prototypes into `attic/` (kept for reference only, not imported).
- **Phase 2 — Correction algorithm.** `correction.py` + `test_correction.py`. Pure functions, no I/O. Update `docs/correction.md`.
- **Phase 3 — PLC layer.** `plc_client.py` (pyads), `plc_sim.py`, shared protocol interface, `test_plc_client.py` against the sim. Update `docs/plc.md` (Python side).
- **Phase 4 — TCS layer.** `tcs_client.py`, `tcs_sim.py`, `test_tcs_client.py`. Carry across the byte-level protocol from prototype `magio.py`.
- **Phase 5 — Controller.** `controller.py` state machine + tracking loop, `config.py`, `test_controller.py`. Wire to plc_sim + tcs_sim.
- **Phase 6 — WebSocket server.** `ws/envelope.py`, `ws/topics.py`, `ws/commands.py`, `ws/logs.py`, `ws/server.py`, `test_ws_protocol.py`. Update `docs/protocol.md`.
- **Phase 7 — CLI + integration.** `cli.py` entry point, end-to-end integration test (sim PLC + sim TCS + WS client), update `docs/running.md` and `docs/architecture.md`.
- **Phase 8 — TwinCAT project.** Complete `plc/WineredADC/` solution: GVL_IO with `TcLinkTo`, GVL_Cmd, GVL_State, GVL_Cfg, FB_Slide + FB_SlideSim, FB_Rotator + FB_RotatorSim, FB_AdcController, MAIN, NC axis setup. Update `docs/plc.md` (PLC side) and `docs/hardware.md`. Single phase because it's one coherent TwinCAT artifact.

After Phase 8, the bench/instrument steps in Verification become applicable.

## Verification

End-to-end, exercised in CI and locally:

1. **Algorithm unit tests** (`test_correction.py`) — compare `ib_targets` against numeric expected values for a handful of (elevation, rotator) inputs, including the boundary where `y` saturates at 1.0 (low altitude).
2. **WS protocol round-trip** (`test_ws_protocol.py`) — connect a test client to a server backed by `plc_sim` + `tcs_sim`; assert `hello` on connect, `state` on subscribe, `ack` shape on a `cmd`, error frame on invalid args.
3. **Controller transitions** (`test_controller.py`) — drive the state machine through INIT→TRACKING→MOVING with a faked plc_sim/tcs_sim; verify the tracking loop only re-targets when deltas exceed deadband.
4. **PLC sim parity** — `FB_RotatorSim`/`FB_SlideSim` exercised in TwinCAT XAR (or via the runtime on dev hardware). Smoke: deploy slide A in sim, observe `GVL_State.eSlideA` transition `OUT → MOVING → IN` via ADS read from a Python REPL.
5. **Live PLC bring-up** — point Python at the real CX9240, confirm encoder readout from EL7342 matches a manual rotation, confirm slide IN/OUT limit transitions on solenoid pulse, then run a 5-minute tracking session against `tcs_sim` and watch motor angles converge.
6. **Client compatibility** — point `lco-instrument-web` at `ws://<host>:52403` and exercise each of the seven UI commands; no schema warnings in the client console.

CI runs steps 1–3 (no TwinCAT or hardware required). Steps 4–6 are on-bench / on-instrument.
