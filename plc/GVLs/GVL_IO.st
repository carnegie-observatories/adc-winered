// Hardware-linked I/O. Each variable is bound to an EtherCAT channel via
// TcLinkTo. If the System Manager topology numbers differ from what's
// documented here, update the path strings (XAE → variable Properties → Path).
//
// Topology (per docs/bring-up.md and bench verification):
//   Term 1 (EK1200) — bus coupler
//   Term 2 (EL2002) — 2-ch DO; ch.1 = Deploy B, ch.2 = Deploy A
//   Term 3 (EL1084) — 4-ch DI; ch.1 = Sense B OUT, ch.2 = Sense B IN,
//                              ch.3 = Sense A OUT, ch.4 = Sense A IN
//
// Syntax note: BOOLs link to the channel's Input/Output sub-item directly
// (no '.member :=' prefix). Reference:
// https://infosys.beckhoff.com/content/1033/tc3_plc_intro/3107974923.html
{attribute 'qualified_only'}
VAR_GLOBAL

    // --- Slide A: Deploy A on EL2002 ch.2, limits on EL1084 ch.3/4 -----
    {attribute 'TcLinkTo' := 'TIID^Device 1 (EtherCAT)^Term 1 (EK1200)^Term 2 (EL2002)^Channel 2^Output'}
    bSlideA_DeployOut : BOOL;

    {attribute 'TcLinkTo' := 'TIID^Device 1 (EtherCAT)^Term 1 (EK1200)^Term 3 (EL1084)^Channel 4^Input'}
    bSlideA_LimitIn : BOOL;

    {attribute 'TcLinkTo' := 'TIID^Device 1 (EtherCAT)^Term 1 (EK1200)^Term 3 (EL1084)^Channel 3^Input'}
    bSlideA_LimitOut : BOOL;

    // --- Slide B: Deploy B on EL2002 ch.1, limits on EL1084 ch.1/2 -----
    {attribute 'TcLinkTo' := 'TIID^Device 1 (EtherCAT)^Term 1 (EK1200)^Term 2 (EL2002)^Channel 1^Output'}
    bSlideB_DeployOut : BOOL;

    {attribute 'TcLinkTo' := 'TIID^Device 1 (EtherCAT)^Term 1 (EK1200)^Term 3 (EL1084)^Channel 2^Input'}
    bSlideB_LimitIn : BOOL;

    {attribute 'TcLinkTo' := 'TIID^Device 1 (EtherCAT)^Term 1 (EK1200)^Term 3 (EL1084)^Channel 1^Input'}
    bSlideB_LimitOut : BOOL;

    // Rotator axes (EL7342 channels) are bound via the NC axis configuration,
    // not via GVL_IO. See docs/bring-up.md § 3.

END_VAR
