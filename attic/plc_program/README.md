# ADC PLC Simulation Program

Structured Text (IEC 61131-3) program for TwinCAT 3 that simulates the ADC hardware.

## Files

- `GVL.st` - Global Variable List with all I/O variables
- `MAIN.st` - Main program with simulation logic

## Variables

### Status Variables (Read by Python)

| Variable | Type | Description |
|----------|------|-------------|
| `GVL.bAdcSlideInserted` | BOOL | ADC slide fully inserted |
| `GVL.bAdcSlideRetracted` | BOOL | ADC slide fully retracted |
| `GVL.lrPrismAPosition` | LREAL | Prism A position (degrees) |
| `GVL.bPrismAMoving` | BOOL | Prism A is moving |
| `GVL.bPrismAAtTarget` | BOOL | Prism A at target position |
| `GVL.lrPrismBPosition` | LREAL | Prism B position (degrees) |
| `GVL.bPrismBMoving` | BOOL | Prism B is moving |
| `GVL.bPrismBAtTarget` | BOOL | Prism B at target position |
| `GVL.bMirrorInserted` | BOOL | Mirror fully inserted |
| `GVL.bMirrorRetracted` | BOOL | Mirror fully retracted |

### Command Variables (Written by Python)

| Variable | Type | Description |
|----------|------|-------------|
| `GVL.lrPrismATarget` | LREAL | Prism A target position (degrees) |
| `GVL.lrPrismBTarget` | LREAL | Prism B target position (degrees) |
| `GVL.bAdcSlideInsert` | BOOL | TRUE=insert, FALSE=retract |
| `GVL.bMirrorInsert` | BOOL | TRUE=insert, FALSE=retract |

### Simulation Parameters

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GVL.lrMoveSpeed` | LREAL | 5.0 | Prism movement speed (deg/s) |
| `GVL.lrPositionThreshold` | LREAL | 0.1 | At-target threshold (deg) |

## Importing into TwinCAT 3

1. Create a new TwinCAT XAE project
2. Add a PLC project (TwinCAT PLC Control)
3. Right-click on GVLs → Add → Global Variable List → name it `GVL`
4. Copy contents of `GVL.st` into the GVL editor
5. Right-click on POUs → Add → POU → name it `MAIN` (Program)
6. Copy contents of `MAIN.st` into the MAIN editor
7. Build the project (F6)
8. Activate configuration and start PLC

## Task Configuration

Configure MAIN to run in a cyclic task:
- Cycle time: 10ms (matches `tCycleTime` in MAIN)
- Priority: 20 (typical for motion control)

## Simulation Behavior

- **Prisms**: Move toward target at `lrMoveSpeed` degrees/second
- **ADC Slide**: Instantly switches based on command (simulates pneumatic)
- **Mirror**: Instantly switches based on command (simulates pneumatic)
- **Encoder noise**: Optional (uncomment in MAIN.st for realistic encoder jitter)
