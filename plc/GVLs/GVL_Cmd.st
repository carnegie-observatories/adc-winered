// ADS-writable command surface. Python writes here; the PLC consumes and
// clears the edge-triggered bits. The level-triggered slide bits stay set.
{attribute 'qualified_only'}
VAR_GLOBAL

    // Rotator A
    rAxisA_Target : LREAL;
    bAxisA_Go     : BOOL;  // rising edge -> MC_MoveAbsolute; PLC clears after consume
    bAxisA_Stop   : BOOL;  // rising edge -> MC_Stop
    bAxisA_Home   : BOOL;  // rising edge -> MC_Home
    bAxisA_Reset  : BOOL;  // rising edge -> MC_Reset

    // Rotator B
    rAxisB_Target : LREAL;
    bAxisB_Go     : BOOL;
    bAxisB_Stop   : BOOL;
    bAxisB_Home   : BOOL;
    bAxisB_Reset  : BOOL;

    // Slides (level-triggered; TRUE = drive to IN)
    bSlideA_Deploy : BOOL;
    bSlideB_Deploy : BOOL;

END_VAR
