# Dispersion-correction math

The Python server implements one prism-orientation mode: **IB** (the dispersion-correcting default from the legacy ADC). Modes 1 and 2 from the reference are not ported — see "Extending" below.

## The formula

Given telescope state `(elevation_deg, rotator_deg)`:

```
z = 90° − elevation
y = min(1, tan(z) / tan(59.01°))
a = arccos(y)                          # prism separation angle, degrees
r = 90° − rotator                       # parallactic transform
target_A = r + 180 − a
target_B = r − 180 + a
```

Both targets are absolute rotator angles, in degrees. The caller decides whether to move (encoder vs. target deadband, currently-busy guards, etc.).

Code: [`src/adc_winered/correction.py`](../src/adc_winered/correction.py).

## The lens cone half-angle (59.01°)

`tan(59.01°)` is baked into the original ADC optical design — it's the half-angle of the lens cone. Below this elevation, the optical correction can't get any larger, so `y` saturates at `1`, `a` collapses to `0`, and both prisms align at `r ± 180`. This is intentional, not a bug: the instrument has run out of correction range, so it parks at the wide-open configuration until the target rises.

## Reference

The formula is taken verbatim from the legacy Objective-C implementation at `/Users/william/workspace/adc/src/ADC/ADC_Controller.m:774-809` (function `-updateLensTarget:`). The legacy file contains all three modes (0 = IB, 1, 2); only mode 0 is needed for WINERED.

## Extending

To add another mode without disturbing IB:

1. Add a new pure function alongside `ib_targets` in `correction.py` (same `(elevation_deg, rotator_deg) -> RotatorTargets` shape).
2. Pick the function in `controller.py` based on a `prism_mode` config field.
3. Test it like `ib_targets` — pure math, no I/O.

Do not branch inside `ib_targets`; keep each mode in its own function.
