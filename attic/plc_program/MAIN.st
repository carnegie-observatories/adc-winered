PROGRAM MAIN
VAR
    (* Internal state *)
    lrDiffA         : LREAL;        // Position error for Prism A
    lrDiffB         : LREAL;        // Position error for Prism B
    lrStepA         : LREAL;        // Movement step for Prism A
    lrStepB         : LREAL;        // Movement step for Prism B
    lrMoveRate      : LREAL;        // Movement per cycle (deg)
    
    (* Timing *)
    tCycleTime      : TIME := T#10MS;   // PLC cycle time
    lrCycleSeconds  : LREAL;            // Cycle time in seconds
    
    (* Random noise for encoder simulation *)
    nNoiseCounter   : UDINT;            // Counter for pseudo-random
    lrNoiseA        : LREAL;
    lrNoiseB        : LREAL;
END_VAR

(* ============================================== *)
(* ADC Simulation - Main Program                 *)
(* Replicates Python SimulatedPLCDriver behavior *)
(* ============================================== *)

(* Calculate movement rate based on cycle time *)
lrCycleSeconds := TIME_TO_LREAL(tCycleTime) / 1000.0;
lrMoveRate := GVL.lrMoveSpeed * lrCycleSeconds;

(* ============================================== *)
(* Prism A - Motorized Axis Simulation           *)
(* ============================================== *)

(* Calculate position error *)
lrDiffA := GVL.lrPrismATarget - GVL.lrPrismAPosition;

(* Check if moving (outside threshold) *)
GVL.bPrismAMoving := ABS(lrDiffA) > GVL.lrPositionThreshold;
GVL.bPrismAAtTarget := NOT GVL.bPrismAMoving;

(* Move toward target if not at target *)
IF GVL.bPrismAMoving THEN
    (* Calculate step size (limited to move rate) *)
    IF ABS(lrDiffA) < lrMoveRate THEN
        lrStepA := lrDiffA;  // Final approach
    ELSIF lrDiffA > 0 THEN
        lrStepA := lrMoveRate;  // Move positive
    ELSE
        lrStepA := -lrMoveRate;  // Move negative
    END_IF
    
    (* Update position *)
    GVL.lrPrismAPosition := GVL.lrPrismAPosition + lrStepA;
END_IF

(* ============================================== *)
(* Prism B - Motorized Axis Simulation           *)
(* ============================================== *)

(* Calculate position error *)
lrDiffB := GVL.lrPrismBTarget - GVL.lrPrismBPosition;

(* Check if moving (outside threshold) *)
GVL.bPrismBMoving := ABS(lrDiffB) > GVL.lrPositionThreshold;
GVL.bPrismBAtTarget := NOT GVL.bPrismBMoving;

(* Move toward target if not at target *)
IF GVL.bPrismBMoving THEN
    (* Calculate step size (limited to move rate) *)
    IF ABS(lrDiffB) < lrMoveRate THEN
        lrStepB := lrDiffB;  // Final approach
    ELSIF lrDiffB > 0 THEN
        lrStepB := lrMoveRate;  // Move positive
    ELSE
        lrStepB := -lrMoveRate;  // Move negative
    END_IF
    
    (* Update position *)
    GVL.lrPrismBPosition := GVL.lrPrismBPosition + lrStepB;
END_IF

(* ============================================== *)
(* ADC Slide - Pneumatic Simulation              *)
(* Instant switching based on command            *)
(* ============================================== *)

IF GVL.bAdcSlideInsert THEN
    GVL.bAdcSlideInserted := TRUE;
    GVL.bAdcSlideRetracted := FALSE;
ELSE
    GVL.bAdcSlideInserted := FALSE;
    GVL.bAdcSlideRetracted := TRUE;
END_IF

(* ============================================== *)
(* Mirror - Pneumatic Simulation                 *)
(* Instant switching based on command            *)
(* ============================================== *)

IF GVL.bMirrorInsert THEN
    GVL.bMirrorInserted := TRUE;
    GVL.bMirrorRetracted := FALSE;
ELSE
    GVL.bMirrorInserted := FALSE;
    GVL.bMirrorRetracted := TRUE;
END_IF

(* ============================================== *)
(* Optional: Add encoder noise (pseudo-random)   *)
(* Uncomment to simulate real encoder behavior   *)
(* ============================================== *)
(*
nNoiseCounter := nNoiseCounter + 1;
lrNoiseA := (SIN(UDINT_TO_LREAL(nNoiseCounter) * 0.1) * 0.001);
lrNoiseB := (COS(UDINT_TO_LREAL(nNoiseCounter) * 0.13) * 0.001);
GVL.lrPrismAPosition := GVL.lrPrismAPosition + lrNoiseA;
GVL.lrPrismBPosition := GVL.lrPrismBPosition + lrNoiseB;
*)
