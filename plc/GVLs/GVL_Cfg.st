// Tunables. Persisted in the PLC project, not visible over ADS.
{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    // Default velocity for rotator slews (deg/s). Override per axis if needed.
    rRotatorVelocity  : LREAL := 30.0;
    // Default acceleration / deceleration (deg/s²). Tc2_MC2 takes the same units
    // as the encoder scaling (deg here).
    rRotatorAccel     : LREAL := 60.0;
    rRotatorDecel     : LREAL := 60.0;
    // Jerk (deg/s³). Set to zero to use the NC axis default.
    rRotatorJerk      : LREAL := 0.0;
    // Slide settle timeout — if MOVING persists past this, transition to ERROR.
    tSlideStuckTime   : TIME  := T#5S;
    // Sim-only: how long the simulated slide reports MOVING before settling.
    tSimSlideSettle   : TIME  := T#500MS;
END_VAR

VAR_GLOBAL
    // Sim toggle. TRUE -> FB_AdcController calls FB_*Sim instead of the real FBs.
    // Persist via XAE → "Initialize via retain" or set in the boot project.
    bSimulate : BOOL := FALSE;
END_VAR
