// Software-only rotator. Same interface as FB_Rotator (minus the AXIS_REF),
// integrates position toward target at rVelocity. No real motion is asserted.
FUNCTION_BLOCK FB_RotatorSim
VAR_INPUT
    bGo           : BOOL;
    rTarget       : LREAL;
    rVelocity     : LREAL;
    bStop         : BOOL;
    bHome         : BOOL;
    bReset        : BOOL;
    rCycleSeconds : LREAL;   // task cycle in seconds (e.g. 0.010)
END_VAR
VAR_OUTPUT
    rPosition : LREAL;
    bBusy     : BOOL;
    bDone     : BOOL;
    bError    : BOOL;
    nErrorId  : UDINT;
    bReady    : BOOL;       // homed AND not in error (sim mirrors FB_Rotator)
END_VAR
VAR
    rActiveTarget : LREAL;
    rDelta        : LREAL;
    rMaxStep      : LREAL;
    rfGo          : R_TRIG;
    rfStop        : R_TRIG;
    rfHome        : R_TRIG;
    rfReset       : R_TRIG;
    bSimHomed     : BOOL := FALSE;   // latched on first bHome rising edge
END_VAR

rfGo(CLK := bGo);
rfStop(CLK := bStop);
rfHome(CLK := bHome);
rfReset(CLK := bReset);

IF rfReset.Q THEN
    bError := FALSE;
    nErrorId := 0;
END_IF

IF rfHome.Q THEN
    // Home is the absolute zero in sim. The real axis uses the NC Reference
    // Position parameter set in System Manager — bench-time configuration.
    rPosition := 0.0;
    rActiveTarget := 0.0;
    bBusy := FALSE;
    bDone := TRUE;
    bSimHomed := TRUE;
END_IF

bReady := bSimHomed AND NOT bError;

IF rfStop.Q THEN
    rActiveTarget := rPosition;
    bBusy := FALSE;
    bDone := TRUE;
END_IF

IF rfGo.Q THEN
    rActiveTarget := rTarget;
    bBusy := TRUE;
    bDone := FALSE;
END_IF

// Advance toward the active target at rVelocity * dt per cycle.
IF bBusy THEN
    rDelta := rActiveTarget - rPosition;
    rMaxStep := rVelocity * rCycleSeconds;
    IF ABS(rDelta) <= rMaxStep THEN
        rPosition := rActiveTarget;
        bBusy := FALSE;
        bDone := TRUE;
    ELSIF rDelta > 0.0 THEN
        rPosition := rPosition + rMaxStep;
    ELSE
        rPosition := rPosition - rMaxStep;
    END_IF
END_IF
