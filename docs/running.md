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
| `ADC_PLC_AMS_NET_ID` | `""` | Required if `ADC_PLC_MODE=real`. The PLC's AMS Net ID — **not** necessarily its IP; the WINERED CX answers to `5.171.247.155.1.1` |
| `ADC_PLC_AMS_PORT` | `851` | TwinCAT PLC runtime port |
| `ADC_PLC_HOST` | `""` | Where to open the TCP connection. Defaults to the Net ID's first four octets (pyads' rule), which is wrong when they differ or when tunnelling — set `127.0.0.1` for an SSH tunnel |
| `ADC_PLC_LOCAL_AMS_NET_ID` | `""` | Our own AMS Net ID. The PLC accepts the session only if it has a matching route |

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
ADC_PLC_MODE=real ADC_PLC_AMS_NET_ID=5.171.247.155.1.1 ADC_PLC_HOST=10.7.45.150 \
  uv run adc-winered serve

# Bench over an SSH tunnel (see below).
ssh -N -L 48898:127.0.0.1:48898 adc-plc &
ADC_PLC_MODE=real ADC_PLC_AMS_NET_ID=5.171.247.155.1.1 \
ADC_PLC_HOST=127.0.0.1 ADC_PLC_LOCAL_AMS_NET_ID=127.0.0.1.1.1 \
  uv run adc-winered serve

# Production — both real.
ADC_PLC_MODE=real ADC_PLC_AMS_NET_ID=5.171.247.155.1.1 ADC_PLC_HOST=10.7.45.150 \
ADC_TCS_MODE=real ADC_TCS_HOST=mag2tcs \
  uv run adc-winered serve
```

## Reaching the PLC over SSH

ADS is not reachable from a workstation subnet: the inter-VLAN ACL permits
only 22/443, and the PLC's own `nftables` allows 8016 (Secure ADS) and UDP
48899 but not 48898 (plain ADS). Tunnel instead — it lands on the PLC's
loopback, which `nftables` already accepts, so no firewall rule changes and
no port is exposed to the network. SSH supplies the encryption that Secure
ADS would have, and pyads has no TLS support anyway.

```sh
ssh -N -L 48898:127.0.0.1:48898 adc-plc
```

48898 must be the *local* port too — the AMS/TCP destination port is fixed
inside the ADS library. The PLC also needs a static route whose Net ID matches
`ADC_PLC_LOCAL_AMS_NET_ID`; through the tunnel the peer appears as `127.0.0.1`,
so use `127.0.0.1.1.1`.

## Logs

Logs go to stderr and to the in-memory ring buffer (broadcast on the `logs` topic). To pipe them to a file, redirect stderr.
