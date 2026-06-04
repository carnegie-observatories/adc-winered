// Real rotator. Wraps Tc2_MC2 against an NC axis. The Go/Stop/Home/Reset
// inputs are edge-triggered to mirror the ADS command semantics.
//
// Homing uses MC_Home with bCalibrationCam driven from the PLC — Beckhoff's
// documented pattern for axes with only an encoder sync pulse (no physical
// reference cam). NC's two-phase homing model is preserved; the PLC simulates
// a permanently-occupied cam during Phase 1 (search), and NC's configured
// Reference Mode (e.g. Hardware Latch 1) captures the precise position in
// Phase 2 via the EL7342 external latch on I1 / I2.
//
// Reference: Tc2_MC2 MC_Home documentation —
//   https://infosys.beckhoff.com/content/1033/tcplclib_tc2_mc2/70117515.html
//   "If an axis is to be referenced without referencing cam, i.e. only based
//    on the sync pulse of the encoder, the referencing cam can be simulated
//    via the PLC program. The 'bCalibrationCam' signal is initially activated
//    and then canceled, if Axis.NcToPlc.HomingState is equal or greater 4."
//
// NC bench-time configuration (System Manager → NC → Axis → Encoder):
//   Reference Mode (Sync condition) = Hardware Latch 1 (pos. edge)
//   Invert Direction for Sync Impulse Search = TRUE  (Z inverted by level shifter)
//   Reference Velocity (Fast) / (Slow) — bench-tuned values
//   Home Position (Calibration Value) — final position written after sync

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
    // Ready = axis has been homed at least once since boot AND is not in error.
    // The intended use is gating: any caller that needs absolute position
    // should refuse to dispatch a move when bReady = FALSE.
    bReady    : BOOL;
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
    bCamWanted : BOOL;     // PLC-simulated cam for MC_Home.bCalibrationCam
    bHomed     : BOOL;     // latched TRUE once a homing run completes successfully
END_VAR

// Always enabled. Override per-axis safety in the NC config, not here.
fbPower(
    Axis            := Axis,
    Enable          := TRUE,
    Enable_Positive := TRUE,
    Enable_Negative := TRUE,
    Override        := 100.0
);

// Edge detection on the commands.
rfGo(CLK := bGo);
rfStop(CLK := bStop);
rfHome(CLK := bHome);
rfReset(CLK := bReset);

// Reset clears latched errors first so the next Go can run.
fbReset(Axis := Axis, Execute := rfReset.Q);

// Stop aborts everything, including a running homing sequence.
fbStop(Axis := Axis, Execute := rfStop.Q, Deceleration := rDecel);

// Homing — Beckhoff's documented cam-less pattern for axes with only an
// encoder Z (no physical reference cam): drive MC_Home.bCalibrationCam from
// the PLC to simulate a permanently-occupied cam through Phase 1, then let
// NC's configured Reference Mode (Hardware Latch 1, neg. edge for the
// level-shifted Z on I1) capture the precise position in Phase 2.
//
// Reference Mode polarity matters: the level shifter inverts the Z pulse so
// on I1 the leading edge of Z is a *falling* edge. NC must be configured
// for `Hardware Latch 1 (neg. edge)` — `pos. edge` will hunt forever in
// Phase 2 and fire error 16979 at state 3 with no useful diagnostic.
fbHome(
    Axis            := Axis,
    Execute         := rfHome.Q,
    Position        := 0.0,
    HomingMode      := MC_DefaultHoming,
    BufferMode      := MC_Aborting,
    bCalibrationCam := bCamWanted
);

IF Axis.NcToPlc.HomingState < 4 THEN
    bCamWanted := TRUE;
ELSE
    bCamWanted := FALSE;
END_IF

fbMove(
    Axis         := Axis,
    Execute      := rfGo.Q,
    Position     := rTarget,
    Velocity     := rVelocity,
    Acceleration := rAccel,
    Deceleration := rDecel,
    Jerk         := rJerk,
    BufferMode   := MC_Aborting
);

// Live readback.
fbReadPos(Axis := Axis, Enable := TRUE);
fbStatus(Axis := Axis, Enable := TRUE);

rPosition := fbReadPos.Position;
// MC_ReadStatus has no .Moving flag; the action-FB Busy bits cover all motion.
bBusy     := fbMove.Busy OR fbHome.Busy OR fbStop.Busy;
bDone     := (fbMove.Done OR fbHome.Done) AND NOT bBusy;

// Latch bHomed. NC clears HomingState back to 0 once MC_Home finishes, so we
// can't infer "homed" from HomingState directly. Instead we set the latch on
// fbHome.Done and clear it on the next rfHome rising edge (axis is no longer
// calibrated while a new homing run is in progress). A reset doesn't clear
// bHomed — the mechanical calibration survives an error/reset cycle.
IF rfHome.Q THEN
    bHomed := FALSE;
END_IF
IF fbHome.Done AND NOT fbHome.Error THEN
    bHomed := TRUE;
END_IF

bReady := bHomed AND NOT bError;

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
