{attribute 'qualified_only'}
VAR_GLOBAL
    (* ============================================== *)
    (* ADC Control - Global Variable List            *)
    (* ============================================== *)
    
    (* ----- ADC Slide (Pneumatic) ----- *)
    (* Status - Limit switches *)
    bAdcSlideInserted   : BOOL;     // TRUE when slide is fully inserted
    bAdcSlideRetracted  : BOOL;     // TRUE when slide is fully retracted
    (* Command *)
    bAdcSlideInsert     : BOOL;     // TRUE = insert, FALSE = retract
    
    (* ----- Prism A (Motorized) ----- *)
    (* Status *)
    lrPrismAPosition    : LREAL;    // Current position in degrees
    bPrismAMoving       : BOOL;     // TRUE while motor is moving
    bPrismAAtTarget     : BOOL;     // TRUE when position matches target
    (* Command *)
    lrPrismATarget      : LREAL;    // Target position in degrees
    
    (* ----- Prism B (Motorized) ----- *)
    (* Status *)
    lrPrismBPosition    : LREAL;    // Current position in degrees
    bPrismBMoving       : BOOL;     // TRUE while motor is moving
    bPrismBAtTarget     : BOOL;     // TRUE when position matches target
    (* Command *)
    lrPrismBTarget      : LREAL;    // Target position in degrees
    
    (* ----- Mirror (Pneumatic) ----- *)
    (* Status - Limit switches *)
    bMirrorInserted     : BOOL;     // TRUE when mirror is fully inserted
    bMirrorRetracted    : BOOL;     // TRUE when mirror is fully retracted
    (* Command *)
    bMirrorInsert       : BOOL;     // TRUE = insert, FALSE = retract
    
    (* ----- Simulation Parameters ----- *)
    lrMoveSpeed         : LREAL := 5.0;     // Prism move speed (degrees/second)
    lrPositionThreshold : LREAL := 0.1;     // At-target threshold (degrees)
END_VAR
