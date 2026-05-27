# Running the server

## Install

```sh
uv sync
```

## Run

```sh
uv run adc-winered serve
```

The process binds the WebSocket port and blocks. SIGINT / SIGTERM shut it down cleanly.

## Environment variables

All settings live in [`config.py`](../src/adc_winered/config.py); env var name is the field with the `ADC_` prefix, upper-cased.

### Backend selection

| Var | Default | Meaning |
|---|---|---|
| `ADC_PLC_MODE` | `sim` | `real` → use the Beckhoff PLC over ADS; `sim` → in-process simulator |
| `ADC_TCS_MODE` | `sim` | `real` → connect to Magellan TCS; `sim` → in-process simulator |

### Real PLC

| Var | Default | Meaning |
|---|---|---|
| `ADC_PLC_AMS_NET_ID` | `""` | Required if `ADC_PLC_MODE=real`, e.g. `10.8.104.50.1.1` |
| `ADC_PLC_AMS_PORT` | `851` | TwinCAT PLC runtime port |
| `ADC_PLC_IP` | `""` | Optional local AMS address override (passed to `pyads.set_local_address`) |

### Real TCS

| Var | Default |
|---|---|
| `ADC_TCS_HOST` | `127.0.0.1` |
| `ADC_TCS_PORT` | `5800` |

### External API

| Var | Default |
|---|---|
| `ADC_WS_HOST` | `0.0.0.0` |
| `ADC_WS_PORT` | `52403` |

### Tuning

| Var | Default | Meaning |
|---|---|---|
| `ADC_CONTROL_INTERVAL_S` | `30.0` | Tracking-step period |
| `ADC_DEADBAND_DEG` | `0.7` | Don't dispatch a move smaller than this |
| `ADC_ROTATOR_VELOCITY_DEG_S` | `30.0` | Sim only |
| `ADC_SLIDE_SETTLE_S` | `0.5` | Sim only |
| `ADC_TCS_SIM_DRIFT` | `false` | Sim only: emit slow oscillation for the TCS |

## Canonical modes

```sh
# Fully offline (default) — develop the WS API without any hardware.
uv run adc-winered serve

# Bench — real PLC, simulated TCS.
ADC_PLC_MODE=real ADC_PLC_AMS_NET_ID=10.8.104.50.1.1 \
  uv run adc-winered serve

# Production — both real.
ADC_PLC_MODE=real ADC_PLC_AMS_NET_ID=10.8.104.50.1.1 \
ADC_TCS_MODE=real ADC_TCS_HOST=mag2tcs \
  uv run adc-winered serve
```

## Logs

Logs go to stderr and to the in-memory ring buffer (broadcast on the `logs` topic). To pipe them to a file, redirect stderr.
