// Real rotator. Wraps Tc2_MC2 against an NC axis. The Go/Stop/Home/Reset
// inputs are edge-triggered to mirror the ADS command semantics.
FUNCTION_BLOCK FB_Rotator
VAR_IN_OUT
    Axis : AXIS_REF;
END_VAR
VAR_INPUT
    bGo       : BOOL;
    rTarget   : LREAL;
    rVelocity : LREAL;
    rAccel    : LREAL;
    rDecel    : LREAL;
    rJerk     : LREAL;
    bStop     : BOOL;
    bHome     : BOOL;
    bReset    : BOOL;
END_VAR
VAR_OUTPUT
    rPosition : LREAL;
    bBusy     : BOOL;
    bDone     : BOOL;
    bError    : BOOL;
    nErrorId  : UDINT;
END_VAR
VAR
    fbPower    : MC_Power;
    fbMove     : MC_MoveAbsolute;
    fbStop     : MC_Stop;
    fbHome     : MC_Home;
    fbReset    : MC_Reset;
    fbReadPos  : MC_ReadActualPosition;
    fbStatus   : MC_ReadStatus;
    rfGo       : R_TRIG;
    rfStop     : R_TRIG;
    rfHome     : R_TRIG;
    rfReset    : R_TRIG;
END_VAR

// Always enabled. Override per-axis safety in the NC config, not here.
fbPower(
    Axis := Axis,
    Enable := TRUE,
    Enable_Positive := TRUE,
    Enable_Negative := TRUE,
    Override := 100.0
);

// Edge detection on the commands.
rfGo(CLK := bGo);
rfStop(CLK := bStop);
rfHome(CLK := bHome);
rfReset(CLK := bReset);

// Reset clears latched errors first so the next Go can run.
fbReset(Axis := Axis, Execute := rfReset.Q);

// Stop wins over Move/Home — handled by Tc2_MC2 internally; just trigger it.
fbStop(Axis := Axis, Execute := rfStop.Q, Deceleration := rDecel);

fbHome(
    Axis := Axis,
    Execute := rfHome.Q,
    Position := 0.0,
    HomingMode := MC_DefaultHoming,
    BufferMode := MC_Aborting
);

fbMove(
    Axis := Axis,
    Execute := rfGo.Q,
    Position := rTarget,
    Velocity := rVelocity,
    Acceleration := rAccel,
    Deceleration := rDecel,
    Jerk := rJerk,
    BufferMode := MC_Aborting
);

// Live readback.
fbReadPos(Axis := Axis, Enable := TRUE);
fbStatus(Axis := Axis, Enable := TRUE);

rPosition := fbReadPos.Position;
bBusy     := fbStatus.Moving OR fbMove.Busy OR fbHome.Busy OR fbStop.Busy;
bDone     := fbMove.Done AND NOT bBusy;
// Bubble up the first error we find.
IF fbMove.Error THEN
    bError := TRUE; nErrorId := fbMove.ErrorID;
ELSIF fbHome.Error THEN
    bError := TRUE; nErrorId := fbHome.ErrorID;
ELSIF fbStop.Error THEN
    bError := TRUE; nErrorId := fbStop.ErrorID;
ELSIF fbReset.Error THEN
    bError := TRUE; nErrorId := fbReset.ErrorID;
ELSIF fbPower.Error THEN
    bError := TRUE; nErrorId := fbPower.ErrorID;
ELSE
    bError := FALSE; nErrorId := 0;
END_IF
