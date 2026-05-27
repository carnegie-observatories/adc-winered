# WebSocket protocol (ADC scope)

Filled in during phase 6. Stub now.

The authoritative protocol spec lives at `/Users/william/workspace/lco-ansible/docs/ws-protocol.md`. This file will only describe the **ADC-specific** subset:

- Port: `52403` (= 50001 + 2·100 + 3).
- Topics: `status`, `lens`, `telescope`, `logs`.
- Commands: `setADCInsertion`, `setControlMode`, `moveLens`, `setAutoUpdate`, `setRunning`, plus any others the canonical client expects (audited per `/Users/william/workspace/lco-ansible/docs/plans/ws-migration-step0-adc.md`).
- Error codes: `busy`, `missing_argument`, `invalid_argument`, `hardware`, `plc_unreachable`.

Frame envelope and lifecycle are unchanged from the LCO spec — do not duplicate that document here.
