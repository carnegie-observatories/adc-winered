// Composition root. Owns both rotator instances (real + sim) and both slide
// instances (real + sim) per axis. Each cycle, dispatches to the appropriate
// variant based on GVL_Cfg.bSimulate.
//
// All GVL_State / GVL_Cmd reads and writes happen here — no other POU should
// touch them. This keeps the ADS-visible state machine concentrated in one
// place.
//
// The real rotators take AXIS_REFs from the NC config. Wire them in MAIN.

FUNCTION_BLOCK FB_AdcController
VAR_IN_OUT
    AxisA : AXIS_REF;
    AxisB : AXIS_REF;
END_VAR
VAR_INPUT
    rCycleSeconds : LREAL;
END_VAR
VAR
    fbRotatorA     : FB_Rotator;
    fbRotatorB     : FB_Rotator;
    fbRotatorSimA  : FB_RotatorSim;
    fbRotatorSimB  : FB_RotatorSim;
    fbSlideA       : FB_Slide;
    fbSlideB       : FB_Slide;
    fbSlideSimA    : FB_SlideSim;
    fbSlideSimB    : FB_SlideSim;
END_VAR

// --- Rotator A ---------------------------------------------------------
IF GVL_Cfg.bSimulate THEN
    fbRotatorSimA(
        bGo := GVL_Cmd.bAxisA_Go,
        rTarget := GVL_Cmd.rAxisA_Target,
        rVelocity := GVL_Cfg.rRotatorVelocity,
        bStop := GVL_Cmd.bAxisA_Stop,
        bHome := GVL_Cmd.bAxisA_Home,
        bReset := GVL_Cmd.bAxisA_Reset,
        rCycleSeconds := rCycleSeconds
    );
    GVL_State.rAxisA_Position := fbRotatorSimA.rPosition;
    GVL_State.bAxisA_Busy     := fbRotatorSimA.bBusy;
    GVL_State.bAxisA_Done     := fbRotatorSimA.bDone;
    GVL_State.bAxisA_Error    := fbRotatorSimA.bError;
    GVL_State.nAxisA_ErrorId  := fbRotatorSimA.nErrorId;
ELSE
    fbRotatorA(
        Axis := AxisA,
        bGo := GVL_Cmd.bAxisA_Go,
        rTarget := GVL_Cmd.rAxisA_Target,
        rVelocity := GVL_Cfg.rRotatorVelocity,
        rAccel := GVL_Cfg.rRotatorAccel,
        rDecel := GVL_Cfg.rRotatorDecel,
        rJerk := GVL_Cfg.rRotatorJerk,
        bStop := GVL_Cmd.bAxisA_Stop,
        bHome := GVL_Cmd.bAxisA_Home,
        bReset := GVL_Cmd.bAxisA_Reset
    );
    GVL_State.rAxisA_Position := fbRotatorA.rPosition;
    GVL_State.bAxisA_Busy     := fbRotatorA.bBusy;
    GVL_State.bAxisA_Done     := fbRotatorA.bDone;
    GVL_State.bAxisA_Error    := fbRotatorA.bError;
    GVL_State.nAxisA_ErrorId  := fbRotatorA.nErrorId;
END_IF

// The PLC clears the Go bit after one cycle so the next rising edge can fire.
GVL_Cmd.bAxisA_Go    := FALSE;
GVL_Cmd.bAxisA_Stop  := FALSE;
GVL_Cmd.bAxisA_Home  := FALSE;
GVL_Cmd.bAxisA_Reset := FALSE;

// --- Rotator B ---------------------------------------------------------
IF GVL_Cfg.bSimulate THEN
    fbRotatorSimB(
        bGo := GVL_Cmd.bAxisB_Go,
        rTarget := GVL_Cmd.rAxisB_Target,
        rVelocity := GVL_Cfg.rRotatorVelocity,
        bStop := GVL_Cmd.bAxisB_Stop,
        bHome := GVL_Cmd.bAxisB_Home,
        bReset := GVL_Cmd.bAxisB_Reset,
        rCycleSeconds := rCycleSeconds
    );
    GVL_State.rAxisB_Position := fbRotatorSimB.rPosition;
    GVL_State.bAxisB_Busy     := fbRotatorSimB.bBusy;
    GVL_State.bAxisB_Done     := fbRotatorSimB.bDone;
    GVL_State.bAxisB_Error    := fbRotatorSimB.bError;
    GVL_State.nAxisB_ErrorId  := fbRotatorSimB.nErrorId;
ELSE
    fbRotatorB(
        Axis := AxisB,
        bGo := GVL_Cmd.bAxisB_Go,
        rTarget := GVL_Cmd.rAxisB_Target,
        rVelocity := GVL_Cfg.rRotatorVelocity,
        rAccel := GVL_Cfg.rRotatorAccel,
        rDecel := GVL_Cfg.rRotatorDecel,
        rJerk := GVL_Cfg.rRotatorJerk,
        bStop := GVL_Cmd.bAxisB_Stop,
        bHome := GVL_Cmd.bAxisB_Home,
        bReset := GVL_Cmd.bAxisB_Reset
    );
    GVL_State.rAxisB_Position := fbRotatorB.rPosition;
    GVL_State.bAxisB_Busy     := fbRotatorB.bBusy;
    GVL_State.bAxisB_Done     := fbRotatorB.bDone;
    GVL_State.bAxisB_Error    := fbRotatorB.bError;
    GVL_State.nAxisB_ErrorId  := fbRotatorB.nErrorId;
END_IF

GVL_Cmd.bAxisB_Go    := FALSE;
GVL_Cmd.bAxisB_Stop  := FALSE;
GVL_Cmd.bAxisB_Home  := FALSE;
GVL_Cmd.bAxisB_Reset := FALSE;

// --- Slide A ----------------------------------------------------------
IF GVL_Cfg.bSimulate THEN
    fbSlideSimA(bDeploy := GVL_Cmd.bSlideA_Deploy, tSettle := GVL_Cfg.tSimSlideSettle);
    GVL_State.eSlideA := fbSlideSimA.eState;
    GVL_IO.bSlideA_DeployOut := FALSE;  // never assert real output in sim
ELSE
    fbSlideA(
        bDeploy := GVL_Cmd.bSlideA_Deploy,
        bLimitIn := GVL_IO.bSlideA_LimitIn,
        bLimitOut := GVL_IO.bSlideA_LimitOut,
        tStuck := GVL_Cfg.tSlideStuckTime
    );
    GVL_State.eSlideA := fbSlideA.eState;
    GVL_IO.bSlideA_DeployOut := fbSlideA.bSolenoid;
END_IF

// --- Slide B ----------------------------------------------------------
IF GVL_Cfg.bSimulate THEN
    fbSlideSimB(bDeploy := GVL_Cmd.bSlideB_Deploy, tSettle := GVL_Cfg.tSimSlideSettle);
    GVL_State.eSlideB := fbSlideSimB.eState;
    GVL_IO.bSlideB_DeployOut := FALSE;
ELSE
    fbSlideB(
        bDeploy := GVL_Cmd.bSlideB_Deploy,
        bLimitIn := GVL_IO.bSlideB_LimitIn,
        bLimitOut := GVL_IO.bSlideB_LimitOut,
        tStuck := GVL_Cfg.tSlideStuckTime
    );
    GVL_State.eSlideB := fbSlideB.eState;
    GVL_IO.bSlideB_DeployOut := fbSlideB.bSolenoid;
END_IF

// Heartbeat — flipped here so Python sees it tick every cycle.
GVL_State.bHeartbeat := NOT GVL_State.bHeartbeat;
