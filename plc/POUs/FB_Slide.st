// Real pneumatic slide. Drives the solenoid output when bDeploy=TRUE,
// reports state via limit switches with a stuck-detection timer.
FUNCTION_BLOCK FB_Slide
VAR_INPUT
    bDeploy   : BOOL;        // level: TRUE = drive to IN
    bLimitIn  : BOOL;
    bLimitOut : BOOL;
    tStuck    : TIME;        // moving longer than this -> ERROR
END_VAR
VAR_OUTPUT
    bSolenoid : BOOL;        // drives the EL2002 channel
    eState    : E_SlideState;
END_VAR
VAR
    tonStuck : TON;
END_VAR

// Solenoid drive is a direct mirror of the deploy request.
bSolenoid := bDeploy;

// Decode state from limit switches.
IF bLimitIn AND NOT bLimitOut THEN
    eState := E_SlideState.eSlideIn;
    tonStuck(IN := FALSE);
ELSIF bLimitOut AND NOT bLimitIn THEN
    eState := E_SlideState.eSlideOut;
    tonStuck(IN := FALSE);
ELSIF bLimitIn AND bLimitOut THEN
    // Both switches asserted simultaneously -> wiring fault.
    eState := E_SlideState.eSlideError;
    tonStuck(IN := FALSE);
ELSE
    // Neither switch asserted -> mid-travel.
    eState := E_SlideState.eSlideMoving;
    tonStuck(IN := TRUE, PT := tStuck);
    IF tonStuck.Q THEN
        eState := E_SlideState.eSlideError;
    END_IF
END_IF
