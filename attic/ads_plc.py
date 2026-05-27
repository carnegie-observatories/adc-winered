#!/usr/bin/env python3
"""
Beckhoff ADS PLC Driver for ADC Control.

This module provides the ADSPLCDriver class for communicating with
Beckhoff TwinCAT PLCs via the ADS protocol using pyads.
"""

import pyads

from plc import PLCDriver, PLCStatus, PLCCommand


class ADSPLCDriver(PLCDriver):
    """
    Beckhoff ADS PLC driver using pyads.
    
    Connects to TwinCAT PLC and reads/writes variables via ADS protocol.
    
    Args:
        ams_net_id: Target PLC AMS Net ID (e.g., "192.168.1.100.1.1")
        ams_port: TwinCAT runtime port (851 for PLC runtime 1)
    """
    
    # PLC variable names (TwinCAT Global Variable List)
    VAR_ADC_SLIDE_INSERTED = "GVL.bAdcSlideInserted"
    VAR_ADC_SLIDE_RETRACTED = "GVL.bAdcSlideRetracted"
    VAR_PRISM_A_POSITION = "GVL.lrPrismAPosition"
    VAR_PRISM_A_MOVING = "GVL.bPrismAMoving"
    VAR_PRISM_A_AT_TARGET = "GVL.bPrismAAtTarget"
    VAR_PRISM_B_POSITION = "GVL.lrPrismBPosition"
    VAR_PRISM_B_MOVING = "GVL.bPrismBMoving"
    VAR_PRISM_B_AT_TARGET = "GVL.bPrismBAtTarget"
    VAR_MIRROR_INSERTED = "GVL.bMirrorInserted"
    VAR_MIRROR_RETRACTED = "GVL.bMirrorRetracted"
    
    VAR_PRISM_A_TARGET = "GVL.lrPrismATarget"
    VAR_PRISM_B_TARGET = "GVL.lrPrismBTarget"
    VAR_ADC_SLIDE_INSERT = "GVL.bAdcSlideInsert"
    VAR_MIRROR_INSERT = "GVL.bMirrorInsert"
    
    # Simulation parameters
    VAR_MOVE_SPEED = "GVL.lrMoveSpeed"
    VAR_POSITION_THRESHOLD = "GVL.lrPositionThreshold"
    
    def __init__(
        self, 
        ams_net_id: str, 
        ams_port: int = 851, 
        ip: str | None = None,
        local_ams_net_id: str | None = None,
    ):
        self._ams_net_id = ams_net_id
        self._ams_port = ams_port
        self._ip = ip  # Required on Linux for routing
        self._local_ams_net_id = local_ams_net_id  # Local AMS ID for routing
        self._plc: pyads.Connection | None = None
        self._connected = False
    
    def connect(self) -> bool:
        try:
            # Set local AMS address if specified (required for Linux routing)
            if self._local_ams_net_id:
                pyads.open_port()
                pyads.set_local_address(self._local_ams_net_id)
            
            self._plc = pyads.Connection(self._ams_net_id, self._ams_port, self._ip)
            self._plc.open()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        if self._plc:
            try:
                self._plc.close()
            except Exception:
                pass
        self._connected = False
        self._plc = None
    
    def read_status(self) -> tuple[bool, PLCStatus]:
        if not self._connected or not self._plc:
            if not self.connect():
                return False, PLCStatus()
        
        try:
            # Read all status variables
            status = PLCStatus(
                adc_slide_inserted=self._plc.read_by_name(
                    self.VAR_ADC_SLIDE_INSERTED, pyads.PLCTYPE_BOOL
                ),
                adc_slide_retracted=self._plc.read_by_name(
                    self.VAR_ADC_SLIDE_RETRACTED, pyads.PLCTYPE_BOOL
                ),
                prism_a_position=self._plc.read_by_name(
                    self.VAR_PRISM_A_POSITION, pyads.PLCTYPE_LREAL
                ),
                prism_a_moving=self._plc.read_by_name(
                    self.VAR_PRISM_A_MOVING, pyads.PLCTYPE_BOOL
                ),
                prism_a_at_target=self._plc.read_by_name(
                    self.VAR_PRISM_A_AT_TARGET, pyads.PLCTYPE_BOOL
                ),
                prism_b_position=self._plc.read_by_name(
                    self.VAR_PRISM_B_POSITION, pyads.PLCTYPE_LREAL
                ),
                prism_b_moving=self._plc.read_by_name(
                    self.VAR_PRISM_B_MOVING, pyads.PLCTYPE_BOOL
                ),
                prism_b_at_target=self._plc.read_by_name(
                    self.VAR_PRISM_B_AT_TARGET, pyads.PLCTYPE_BOOL
                ),
                mirror_inserted=self._plc.read_by_name(
                    self.VAR_MIRROR_INSERTED, pyads.PLCTYPE_BOOL
                ),
                mirror_retracted=self._plc.read_by_name(
                    self.VAR_MIRROR_RETRACTED, pyads.PLCTYPE_BOOL
                ),
            )
            return True, status
        except Exception:
            self._connected = False
            return False, PLCStatus()
    
    def write_command(self, command: PLCCommand) -> bool:
        if not self._connected or not self._plc:
            if not self.connect():
                return False
        
        try:
            # Write all command variables
            self._plc.write_by_name(
                self.VAR_PRISM_A_TARGET, command.prism_a_target, pyads.PLCTYPE_LREAL
            )
            self._plc.write_by_name(
                self.VAR_PRISM_B_TARGET, command.prism_b_target, pyads.PLCTYPE_LREAL
            )
            self._plc.write_by_name(
                self.VAR_ADC_SLIDE_INSERT, command.adc_slide_insert, pyads.PLCTYPE_BOOL
            )
            self._plc.write_by_name(
                self.VAR_MIRROR_INSERT, command.mirror_insert, pyads.PLCTYPE_BOOL
            )
            return True
        except Exception:
            return False
