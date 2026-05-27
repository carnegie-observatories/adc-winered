// PLC entry point. Single FB_AdcController instance does all the work.
//
// Axis_A_ref / Axis_B_ref are linked to the NC axes via the System Manager:
// MOTION → NC-Task → Axis A/B → right-click → "Change Link" → bind to these
// AXIS_REF instances. See SYSTEM_MANAGER.md step 2.

PROGRAM MAIN
VAR
    fbAdc : FB_AdcController;

    // Link these to the NC axes in System Manager.
    Axis_A_ref : AXIS_REF;
    Axis_B_ref : AXIS_REF;

    // Task cycle in seconds. Keep in sync with the task period configured
    // in XAE (default 10ms here).
    rCycleSeconds : LREAL := 0.010;
END_VAR

fbAdc(
    AxisA := Axis_A_ref,
    AxisB := Axis_B_ref,
    rCycleSeconds := rCycleSeconds
);
