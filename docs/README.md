# adc-winered docs

Lean reference for the WINERED ADC control stack. One topic per file.

| File | What's in it |
|---|---|
| [architecture.md](architecture.md) | PLC/Python split, ADS surface, WS surface, one ASCII diagram |
| [hardware.md](hardware.md) | Beckhoff slice list, DB25 pinout, motor + valve + switch references |
| [plc.md](plc.md) | TwinCAT project layout, GVLs, FBs, sim mode, rebuild/deploy |
| [protocol.md](protocol.md) | WS frame shapes, ADC topics, commands, error codes |
| [correction.md](correction.md) | The IB dispersion-correction math, one page |
| [running.md](running.md) | How to start the server: real / sim / mixed, env vars, ports |
| [testing.md](testing.md) | `uv run pytest`, plus bench and on-instrument steps |

Plans (committed before execution) live under [`plans/`](plans/). Vendor datasheets live under [`references/`](references/).
