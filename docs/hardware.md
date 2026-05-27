# Hardware

WINERED ADC is controlled by a Beckhoff CX9240 PLC stack. Two motorised prism rotators with incremental encoders, two pneumatic deployment slides with limit switches.

## Beckhoff stack

| # | Module | Role | Power |
|---|---|---|---|
| 1 | CX9240-0215 | PLC CPU, EtherCAT master, ADS endpoint | 4 A |
| 2 | EL2002 | 2-ch 24 V DO — deploy solenoids | 100 mA |
| 3 | EL1084 | 4-ch 24 V DI — slide limit switches | 100 mA + load |
| 4 | EL7342 | 2-ch DC drive + incremental encoder — both rotators | 150 mA |
| 5 | EL9505 | 5 V supply for encoders | 90 mA + 0.5 A |

Us fuse: 1 A. Up fuse: max 10 A. PLC static IP: 10.8.104.50/24 (see [references/plc_configuration.md](references/plc_configuration.md)).

## DB25 pinout (instrument-side connector)

From [references/](references/) — full CSV at `/Users/william/Downloads/WINERED ADC electronics - Pinout Incr Encoder.csv`.

| Pin | Module:Ch | Signal |
|---|---|---|
| 1 | EL2002:3 | Deploy common |
| 2 | EL2002:1 (O1) | Deploy B |
| 3 | EL2002:7 | Sense GND (Blue) |
| 4 | EL1084:1 (I1) | Sense B: OUT (Black) |
| 5 | EL1084:4 (I3) | Sense A: OUT (Black) |
| 6 | EL7342:1' (A1) | Motor A + |
| 7 | EL7342:2' (B1) | Motor B + |
| 8 | EL9505:3 | Enc A: −5 V |
| 9 | EL9505:7 | Enc B: −5 V |
| 10 | EL7342:1 (A) | Enc A: A (gray) |
| 11 | EL7342:2 (A) | Enc B: A (gray) |
| 13 | EL2002:5 (O2) | Deploy A |
| 14 | EL1084:2 (+24 V) | Sense 24 V (brown) |
| 15 | EL1084:5 (I2) | Sense B: IN (Black) |
| 16 | EL1084:8 (I4) | Sense A: IN (Black) |
| 17 | EL7342:5' (A2) | Motor A − |
| 18 | EL7342:6' (B2) | Motor B − |
| 19 | EL9505:2 (5 V) | Enc A: +5 V |
| 20 | EL9505:6 (5 V) | Enc B: +5 V |
| 21 | EL7342:4 (I1) | Enc A: Z (white) |
| 22 | EL7342:8 (I2) | Enc B: Z (white) |
| 23 | EL7342:5 (B) | Enc A: B (green) |
| 24 | EL7342:6 (B) | Enc B: B (green) |

Pins 12, 25 → PE (not connected).

## Mechanical / electrical references

| Component | Datasheet |
|---|---|
| Motors (rotators) | Pololu 3046 — [references/pololu-micro-metal-gearmotors-rev-6-2.pdf](references/pololu-micro-metal-gearmotors-rev-6-2.pdf) |
| Pneumatic valves (slides) | Clippard Maximatic 4-way — [references/Clippard Maximatic 4-Way Valves.pdf](references/Clippard%20Maximatic%204-Way%20Valves.pdf) |
| Limit switches (slides) | Bimba — [references/Switches.pdf](references/Switches.pdf), [references/bimba_switch.png](references/bimba_switch.png) |
| IO module reference | Phoenix Contact 2909906 — [references/phoenix-contact-2909906-en.pdf](references/phoenix-contact-2909906-en.pdf) |

## Component naming convention

Throughout the codebase:

- **Rotator A / Rotator B** — the two motorised prism axes.
- **Slide A / Slide B** — the two pneumatic deployment mechanisms.

The mapping from "A / B" to the physical prism/mirror role is fixed by the harness wiring above; do not relabel in code.
