# WebSocket protocol (ADC scope)

Authoritative protocol spec: `/Users/william/workspace/lco-ansible/docs/ws-protocol.md`. This file scopes the spec to ADC.

## Endpoint

`ws://<host>:52403`. No TLS, no auth (v1). Configure via `ADC_WS_HOST` / `ADC_WS_PORT`.

The server announces itself as `app: "ADC"` in the `hello` frame — uppercase, matching the canonical `APP_REGISTRY` key in `lco-instrument-web/diagnostic.js`.

## Frame types

Seven JSON envelopes; full schema in the spec. Server emits `hello`, `state`, `event`, `ack`. Client emits `subscribe`, `unsubscribe`, `cmd`.

Hello (one-shot on connect):

```json
{ "type": "hello", "protocol_version": 1, "app": "adc",
  "topics": ["status", "lens", "telescope", "logs"] }
```

State frame (snapshot on subscribe + on-change):

```json
{ "type": "state", "topic": "telescope", "data": {...} }
```

Ack (one per `cmd`, keyed by `id`):

```json
{ "type": "ack", "id": "c42", "ok": true,  "result": {...} }
{ "type": "ack", "id": "c42", "ok": false, "error": { "code": "...", "message": "..." } }
```

## Topics

| Topic | Shape | Source |
|---|---|---|
| `status` | `{adc, other, shutter, milky_flat, control, update, running}` | controller + plc snapshot |
| `lens` | `{lens_a:{encoder,target,moving}, lens_b:{...}}` | plc snapshot + computed targets |
| `telescope` | `{elevation, rotator}` | tcs sample |
| `logs` | `{entries: [...]}` on snapshot; `event` frames per live entry | log ring buffer |

The exact projector code is in [`src/adc_winered/ws/topics.py`](../src/adc_winered/ws/topics.py); the log buffer is in [`src/adc_winered/ws/logs.py`](../src/adc_winered/ws/logs.py).

## Commands

Implemented in [`src/adc_winered/ws/commands.py`](../src/adc_winered/ws/commands.py).

Names and argument shapes follow the canonical client's APP_REGISTRY (snake_case throughout):

| Command | Args | Effect |
|---|---|---|
| `version` | `{}` | Returns `{version, protocol_version, app}` |
| `set_adc_insertion` | `{pos: "in"\|"out"}` | Drive Slide A |
| `set_other_insertion` | `{pos: "in"\|"out"}` | Drive Slide B |
| `set_shutter` | `{pos: "open"\|"closed"}` | Drive the shutter (EL2084 ch.1) |
| `set_milky_flat` | `{pos: "in"\|"out"}` | Drive the milky-flat diffuser (EL2084 ch.2) |
| `set_control_mode` | `{mode: "auto"\|"off"}` | Enter / leave tracking |
| `move_lens` | `{lens: "A"\|"B", angle: float}` | Manual axis move (bypasses tracking) |
| `set_auto_update` | `{enabled: bool}` | Alias of `set_control_mode` (UI naming) |
| `trigger_manual_update` | `{}` | One-shot recompute + dispatch |
| `set_running` | `{running: bool}` | Master halt; aliases `set_control_mode` for v1 |

All commands return `{"requested": true}` immediately for long-running effects; observe completion via `state`/`event` frames. Unknown commands ack with `invalid_argument`.

## Error codes

Closed set in v1:

- `busy` — subsystem in incompatible state.
- `missing_argument` — required arg absent.
- `invalid_argument` — out-of-range or wrong type.
- `hardware` — underlying hardware error (motion fault, etc.).
- `plc_unreachable` — ADS link to the PLC is down.

Adding a new code is a protocol change — propose in the spec repo first.

## Test coverage

[`tests/test_ws_protocol.py`](../tests/test_ws_protocol.py) covers hello-on-connect, subscribe + state snapshot, ack-ok / ack-error for cmds, on-change publishing, and unsubscribe. Runs against a live `WsServer` backed by `PlcSim` + `TcsSim`.
