// ADS-readable telemetry. Mirrors plc_client.py _AXIS_SYMBOLS / _SLIDE_SYMBOLS.
// Treat as read-only from the Python side.
{attribute 'qualified_only'}
VAR_GLOBAL

    // Rotator A
    rAxisA_Position : LREAL;
    bAxisA_Busy     : BOOL;
    bAxisA_Done     : BOOL;
    bAxisA_Error    : BOOL;
    nAxisA_ErrorId  : DINT;

    // Rotator B
    rAxisB_Position : LREAL;
    bAxisB_Busy     : BOOL;
    bAxisB_Done     : BOOL;
    bAxisB_Error    : BOOL;
    nAxisB_ErrorId  : DINT;

    // Slides
    eSlideA : E_SlideState;
    eSlideB : E_SlideState;

    // Heartbeat: toggled every cycle by MAIN. Python uses it for liveness.
    bHeartbeat : BOOL;

END_VAR
