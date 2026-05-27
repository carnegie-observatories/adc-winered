// Software-only slide. Same outputs as FB_Slide; ignores hardware inputs.
// Transitions through MOVING for tSettle ms after bDeploy changes.
FUNCTION_BLOCK FB_SlideSim
VAR_INPUT
    bDeploy : BOOL;
    tSettle : TIME;
END_VAR
VAR_OUTPUT
    bSolenoid : BOOL;       // not wired; provided for interface parity
    eState    : E_SlideState;
END_VAR
VAR
    bDeployPrev : BOOL;
    bSettling   : BOOL;
    bTargetIn   : BOOL;
    tonSettle   : TON;
END_VAR

bSolenoid := bDeploy;

// Detect a change in the requested position.
IF bDeploy <> bDeployPrev THEN
    bDeployPrev := bDeploy;
    bTargetIn := bDeploy;
    bSettling := TRUE;
    tonSettle(IN := FALSE);
END_IF

IF bSettling THEN
    tonSettle(IN := TRUE, PT := tSettle);
    eState := E_SlideState.eSlideMoving;
    IF tonSettle.Q THEN
        bSettling := FALSE;
        tonSettle(IN := FALSE);
    END_IF
ELSE
    IF bTargetIn THEN
        eState := E_SlideState.eSlideIn;
    ELSE
        eState := E_SlideState.eSlideOut;
    END_IF
END_IF
