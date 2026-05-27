# Dispersion-correction math

Filled in during phase 2. Stub now.

Planned contents:

- The IB-mode formula: from telescope `(elevation, rotator)` in degrees to target rotator angles `(target_A, target_B)` in degrees.
- The constant `1.665 = tan(59.01°)`: where it comes from (lens cone half-angle) and why we saturate `y` at 1.0.
- Why this is the only mode WINERED supports today, and where in the code modes 1/2 would slot in if needed.
- Reference: original derivation in `/Users/william/workspace/adc/src/ADC/ADC_Controller.m:774-809`.
