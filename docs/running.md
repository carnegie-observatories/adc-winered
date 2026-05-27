# Running the server

Filled out across phases 5–7. Stub now.

Planned contents:

- `uv sync` to install.
- `uv run adc-winered serve` to start.
- Env vars: `ADC_PLC_MODE` (`real`|`sim`), `ADC_TCS_MODE` (`real`|`sim`), `ADC_PLC_AMS_NET_ID`, `ADC_PLC_IP`, `ADC_TCS_HOST`, `ADC_TCS_PORT`, `ADC_WS_PORT` (default 52403), `ADC_CONTROL_INTERVAL_S` (default 30).
- Three canonical modes: fully offline (both sims), bench (real PLC + sim TCS), production (both real).
- Where logs go and how to tail them.
