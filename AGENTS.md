# Agent guide — adc-winered

One-page brief for anyone (human or agent) opening this repo cold.

## What this is

WINERED ADC control stack. Two halves: a TwinCAT 3 PLC project for low-level motion + I/O on a Beckhoff CX9240, and a uv-managed Python server for the dispersion-correction algorithm, the tracking loop, telescope dialog, and the external LCO WebSocket API. The reference implementation (different hardware, Objective-C) lives at `/Users/william/workspace/adc`.

## Layout

| Path | Contents |
|---|---|
| `src/adc_winered/` | Python server — config, correction algorithm, PLC/TCS clients (and their sims), controller state machine, `ws/` server |
| `plc/` | TwinCAT 3 solution (`adc.sln`) — GVLs, FBs, NC axis setup |
| `tests/` | pytest suite — runs against in-process PLC + TCS sims, no hardware needed |
| `docs/` | Lean markdown docs, one topic per file. Start at [`docs/README.md`](docs/README.md) |
| `docs/plans/` | Approved implementation plans, committed before execution |
| `docs/references/` | Hardware datasheets (PDFs), pinout files, vendor docs |
| `attic/` | Frozen prototypes — read-only reference, not built or imported |

## Run it

```sh
uv sync
# Fully offline (no PLC, no TCS):
ADC_PLC_MODE=sim ADC_TCS_MODE=sim uv run adc-winered serve
# Real PLC, sim TCS (bench):
ADC_PLC_MODE=real ADC_TCS_MODE=sim uv run adc-winered serve
# Production:
ADC_PLC_MODE=real ADC_TCS_MODE=real uv run adc-winered serve
```

Long form: [`docs/running.md`](docs/running.md).

## Test it

```sh
uv run pytest
```

Bench/instrument steps: [`docs/testing.md`](docs/testing.md).

## Boundaries that matter

- **PLC owns motion safety.** Soft limits, max velocity, e-stop, encoder homing — all configured at the NC axis or inside ST. The Python server only sends targets and reads status.
- **Python owns the algorithm and the WS protocol.** The PLC never knows about elevation, parallactic angle, or atmospheric models. Keep these layers separate.
- **WS protocol is a closed contract.** Frame types and error codes are defined in [`/Users/william/workspace/lco-ansible/docs/ws-protocol.md`](../lco-ansible/docs/ws-protocol.md). Do not add new types or codes here unilaterally — propose them in the spec repo first.
- **Sim and real paths share an interface.** `plc_client.py` and `plc_sim.py` expose the same methods; same for `tcs_client.py` and `tcs_sim.py`. Same applies on the PLC side (`FB_Rotator`/`FB_RotatorSim`, `FB_Slide`/`FB_SlideSim`). If you change one, change the other.

## House rules

- **Plan-first.** Non-trivial work starts with a plan committed to `docs/plans/` on a `plan/<slug>` branch off `main`. The plan commit is dedicated — no implementation in the same commit.
- **One commit per phase.** Each plan phase lands as a single commit on the plan branch. Stop for review between phases.
- **No co-author / no AI-attribution lines.** Commit messages and PR bodies do **not** include `Co-Authored-By: Claude …` or `🤖 Generated with Claude Code`.
- **Don't import from `attic/`.** Transcribe ideas, don't depend.

## External references

- WebSocket protocol spec: `/Users/william/workspace/lco-ansible/docs/ws-protocol.md`
- Canonical UI client: `/Users/william/workspace/lco-instrument-web`
- Reference ADC implementation (Objective-C): `/Users/william/workspace/adc`
- Sibling instruments using the same pattern: `/Users/william/workspace/dcu`, `/Users/william/workspace/pfs`
