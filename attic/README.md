# attic/

Frozen prototypes from the pre-clean-rebuild prototype phase. Kept as a reference for working code patterns (pyads idioms, MagIO TCS protocol byte layout, TCS simulator response shapes) but **not imported, not built, not tested**.

When porting an idea from here into `src/adc_winered/` or `plc/`, transcribe it — do not depend on this directory at runtime.

## What's here

- `adc_gui.py` — NiceGUI dashboard (replaced by the `lco-instrument-web` client over the WS API)
- `adc_server.py` — FastAPI/REST server (replaced by `src/adc_winered/ws/`)
- `ads_plc.py` — pyads wrapper (replaced by `src/adc_winered/plc_client.py`)
- `magio.py` — Magellan TCS TCP client (replaced by `src/adc_winered/tcs_client.py`)
- `plc.py` — abstract PLC interface (folded into the new client/sim split)
- `tcs_sim.py` — TCS simulator (replaced by `src/adc_winered/tcs_sim.py`)
- `test_ads_plc.py`, `test_magio.py` — protocol tests (folded into `tests/`)
- `main.py` — stub entry point (replaced by `cli.py`)
- `plc_program/` — pure-ST simulator without MC2/NC integration (replaced by `plc/WineredADC/`)
- `pyproject.toml`, `uv.lock` — old dependency pins (NiceGUI etc.)
- `ssh-forward.sh`, `adc.code-workspace` — dev convenience files

This directory may be deleted entirely once the production stack is on-instrument.
