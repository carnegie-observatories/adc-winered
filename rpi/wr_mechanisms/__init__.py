"""WINERED shutter + milky-flat WebSocket server for the Raspberry Pi.

A standalone, PLC-free stand-in for the two WINERED-only mechanisms. It speaks
the same LCO WebSocket protocol as `adc_winered` but advertises exactly one
topic — `mechanisms` — and the two commands that drive it, so the existing
browser panel (`web/mechanisms.html`) works against it unchanged.

Deliberately independent of the `adc_winered` package: this runs on a Pi with
nothing but `websockets` and `gpiozero` installed, and shares no imports with
the ADC server. The protocol shapes in `protocol.py` are the coupling point;
keep them in step with `src/adc_winered/ws/envelope.py`.
"""

from __future__ import annotations

__version__ = "0.1.0"
