# adc-winered

Atmospheric Dispersion Corrector control stack for the WINERED instrument.

Two components:

- **PLC project** under `plc/` — TwinCAT 3 Structured Text on a Beckhoff CX9240. Owns motion (Tc2_MC2 + NC axes) and digital I/O for the two prism rotators and two deployment slides.
- **Python server** under `src/adc_winered/` — headless service exposing the LCO WebSocket protocol on port `52403`. Runs the dispersion-correction algorithm, the tracking loop, talks to the PLC over ADS, and to the Magellan TCS over TCP.

## Quickstart

```sh
uv sync
ADC_PLC_MODE=sim ADC_TCS_MODE=sim uv run adc-winered serve
```

See [`AGENTS.md`](AGENTS.md) for a one-page orientation, [`docs/`](docs/) for everything else.
