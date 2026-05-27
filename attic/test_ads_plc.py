#!/usr/bin/env python3
"""
Integration tests for Beckhoff ADS PLC communication.

These tests verify that all PLC variables can be read and written.
Requires a running TwinCAT PLC with the expected GVL structure.

Usage:
    pytest test_ads_plc.py -v
    
    # Or with custom PLC address:
    ADS_NET_ID=192.168.1.100.1.1 pytest test_ads_plc.py -v
"""

import os
import pytest
import pyads

from ads_plc import ADSPLCDriver
from plc import PLCCommand, PLCStatus


# PLC connection settings from environment
AMS_NET_ID = os.getenv("ADS_NET_ID", "127.0.0.1.1.1")
AMS_PORT = int(os.getenv("ADS_PORT", "851"))
ADS_IP = os.getenv("ADS_IP")  # Required on Linux
LOCAL_AMS_NET_ID = os.getenv("LOCAL_AMS_NET_ID")  # Local AMS ID for routing


@pytest.fixture
def plc() -> ADSPLCDriver:
    """Create and connect to PLC, disconnect after test."""
    driver = ADSPLCDriver(AMS_NET_ID, AMS_PORT, ip=ADS_IP, local_ams_net_id=LOCAL_AMS_NET_ID)
    connected = driver.connect()
    if not connected:
        pytest.skip(f"Cannot connect to PLC at {AMS_NET_ID}:{AMS_PORT}")
    yield driver
    driver.disconnect()


class TestPLCConnection:
    """Test basic PLC connectivity."""
    
    def test_connect(self):
        """Test that we can connect to the PLC."""
        driver = ADSPLCDriver(AMS_NET_ID, AMS_PORT, ip=ADS_IP, local_ams_net_id=LOCAL_AMS_NET_ID)
        try:
            connected = driver.connect()
            assert connected, f"Failed to connect to PLC at {AMS_NET_ID}:{AMS_PORT} (ip={ADS_IP})"
        finally:
            driver.disconnect()
    
    def test_disconnect(self):
        """Test that disconnect works cleanly."""
        driver = ADSPLCDriver(AMS_NET_ID, AMS_PORT, ip=ADS_IP, local_ams_net_id=LOCAL_AMS_NET_ID)
        driver.connect()
        driver.disconnect()
        # Should not raise, even if called multiple times
        driver.disconnect()


class TestReadStatusVariables:
    """Test reading all status variables from PLC."""
    
    def test_read_status_returns_success(self, plc: ADSPLCDriver):
        """Test that read_status returns success."""
        success, status = plc.read_status()
        assert success, "read_status() should return success"
        assert isinstance(status, PLCStatus)
    
    def test_read_adc_slide_inserted(self, plc: ADSPLCDriver):
        """Test reading GVL.bAdcSlideInserted."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.adc_slide_inserted, bool)
    
    def test_read_adc_slide_retracted(self, plc: ADSPLCDriver):
        """Test reading GVL.bAdcSlideRetracted."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.adc_slide_retracted, bool)
    
    def test_read_prism_a_position(self, plc: ADSPLCDriver):
        """Test reading GVL.lrPrismAPosition."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.prism_a_position, float)
    
    def test_read_prism_a_moving(self, plc: ADSPLCDriver):
        """Test reading GVL.bPrismAMoving."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.prism_a_moving, bool)
    
    def test_read_prism_a_at_target(self, plc: ADSPLCDriver):
        """Test reading GVL.bPrismAAtTarget."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.prism_a_at_target, bool)
    
    def test_read_prism_b_position(self, plc: ADSPLCDriver):
        """Test reading GVL.lrPrismBPosition."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.prism_b_position, float)
    
    def test_read_prism_b_moving(self, plc: ADSPLCDriver):
        """Test reading GVL.bPrismBMoving."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.prism_b_moving, bool)
    
    def test_read_prism_b_at_target(self, plc: ADSPLCDriver):
        """Test reading GVL.bPrismBAtTarget."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.prism_b_at_target, bool)
    
    def test_read_mirror_inserted(self, plc: ADSPLCDriver):
        """Test reading GVL.bMirrorInserted."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.mirror_inserted, bool)
    
    def test_read_mirror_retracted(self, plc: ADSPLCDriver):
        """Test reading GVL.bMirrorRetracted."""
        success, status = plc.read_status()
        assert success
        assert isinstance(status.mirror_retracted, bool)


class TestWriteCommandVariables:
    """Test writing all command variables to PLC."""
    
    def test_write_command_returns_success(self, plc: ADSPLCDriver):
        """Test that write_command returns success."""
        command = PLCCommand()
        success = plc.write_command(command)
        assert success, "write_command() should return success"
    
    def test_write_prism_a_target(self, plc: ADSPLCDriver):
        """Test writing GVL.lrPrismATarget."""
        test_value = 45.5
        command = PLCCommand(prism_a_target=test_value)
        success = plc.write_command(command)
        assert success
        
        # Verify by reading back
        value = plc._plc.read_by_name(
            ADSPLCDriver.VAR_PRISM_A_TARGET, pyads.PLCTYPE_LREAL
        )
        assert abs(value - test_value) < 0.001
    
    def test_write_prism_b_target(self, plc: ADSPLCDriver):
        """Test writing GVL.lrPrismBTarget."""
        test_value = 90.25
        command = PLCCommand(prism_b_target=test_value)
        success = plc.write_command(command)
        assert success
        
        # Verify by reading back
        value = plc._plc.read_by_name(
            ADSPLCDriver.VAR_PRISM_B_TARGET, pyads.PLCTYPE_LREAL
        )
        assert abs(value - test_value) < 0.001
    
    def test_write_adc_slide_insert_true(self, plc: ADSPLCDriver):
        """Test writing GVL.bAdcSlideInsert = TRUE."""
        command = PLCCommand(adc_slide_insert=True)
        success = plc.write_command(command)
        assert success
        
        # Verify by reading back
        value = plc._plc.read_by_name(
            ADSPLCDriver.VAR_ADC_SLIDE_INSERT, pyads.PLCTYPE_BOOL
        )
        assert value is True
    
    def test_write_adc_slide_insert_false(self, plc: ADSPLCDriver):
        """Test writing GVL.bAdcSlideInsert = FALSE."""
        command = PLCCommand(adc_slide_insert=False)
        success = plc.write_command(command)
        assert success
        
        # Verify by reading back
        value = plc._plc.read_by_name(
            ADSPLCDriver.VAR_ADC_SLIDE_INSERT, pyads.PLCTYPE_BOOL
        )
        assert value is False
    
    def test_write_mirror_insert_true(self, plc: ADSPLCDriver):
        """Test writing GVL.bMirrorInsert = TRUE."""
        command = PLCCommand(mirror_insert=True)
        success = plc.write_command(command)
        assert success
        
        # Verify by reading back
        value = plc._plc.read_by_name(
            ADSPLCDriver.VAR_MIRROR_INSERT, pyads.PLCTYPE_BOOL
        )
        assert value is True
    
    def test_write_mirror_insert_false(self, plc: ADSPLCDriver):
        """Test writing GVL.bMirrorInsert = FALSE."""
        command = PLCCommand(mirror_insert=False)
        success = plc.write_command(command)
        assert success
        
        # Verify by reading back
        value = plc._plc.read_by_name(
            ADSPLCDriver.VAR_MIRROR_INSERT, pyads.PLCTYPE_BOOL
        )
        assert value is False


class TestDirectVariableAccess:
    """Test direct read/write of individual PLC variables."""
    
    @pytest.mark.parametrize("var_name,var_type", [
        (ADSPLCDriver.VAR_ADC_SLIDE_INSERTED, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_ADC_SLIDE_RETRACTED, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_PRISM_A_POSITION, pyads.PLCTYPE_LREAL),
        (ADSPLCDriver.VAR_PRISM_A_MOVING, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_PRISM_A_AT_TARGET, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_PRISM_B_POSITION, pyads.PLCTYPE_LREAL),
        (ADSPLCDriver.VAR_PRISM_B_MOVING, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_PRISM_B_AT_TARGET, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_MIRROR_INSERTED, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_MIRROR_RETRACTED, pyads.PLCTYPE_BOOL),
        (ADSPLCDriver.VAR_MOVE_SPEED, pyads.PLCTYPE_LREAL),
        (ADSPLCDriver.VAR_POSITION_THRESHOLD, pyads.PLCTYPE_LREAL),
    ])
    def test_read_status_variable(self, plc: ADSPLCDriver, var_name: str, var_type):
        """Test reading each status variable directly."""
        value = plc._plc.read_by_name(var_name, var_type)
        if var_type == pyads.PLCTYPE_BOOL:
            assert isinstance(value, bool), f"{var_name} should be bool"
        elif var_type == pyads.PLCTYPE_LREAL:
            assert isinstance(value, float), f"{var_name} should be float"
    
    @pytest.mark.parametrize("var_name,var_type,test_value", [
        (ADSPLCDriver.VAR_PRISM_A_TARGET, pyads.PLCTYPE_LREAL, 12.34),
        (ADSPLCDriver.VAR_PRISM_B_TARGET, pyads.PLCTYPE_LREAL, 56.78),
        (ADSPLCDriver.VAR_ADC_SLIDE_INSERT, pyads.PLCTYPE_BOOL, True),
        (ADSPLCDriver.VAR_ADC_SLIDE_INSERT, pyads.PLCTYPE_BOOL, False),
        (ADSPLCDriver.VAR_MIRROR_INSERT, pyads.PLCTYPE_BOOL, True),
        (ADSPLCDriver.VAR_MIRROR_INSERT, pyads.PLCTYPE_BOOL, False),
        (ADSPLCDriver.VAR_MOVE_SPEED, pyads.PLCTYPE_LREAL, 10.0),
        (ADSPLCDriver.VAR_POSITION_THRESHOLD, pyads.PLCTYPE_LREAL, 0.05),
    ])
    def test_write_command_variable(self, plc: ADSPLCDriver, var_name: str, var_type, test_value):
        """Test writing each command variable directly."""
        # Write the value
        plc._plc.write_by_name(var_name, test_value, var_type)
        
        # Read it back
        read_value = plc._plc.read_by_name(var_name, var_type)
        
        if var_type == pyads.PLCTYPE_LREAL:
            assert abs(read_value - test_value) < 0.001, f"{var_name} round-trip failed"
        else:
            assert read_value == test_value, f"{var_name} round-trip failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
