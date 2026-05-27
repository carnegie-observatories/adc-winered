#!/usr/bin/env python3
"""
Comprehensive tests for MagIO TCS client.

Tests all commands against the TCS simulation server to verify
correct protocol handling and data parsing.
"""

import pytest
import time
import math
from magio import MagIO, MagIOError, AirmassData, CoordinateData
from tcs_sim import TCSSimulator


# === Fixtures ===

@pytest.fixture(scope="module")
def tcs_server():
    """Start a TCS simulation server for the test module."""
    # Use a different port to avoid conflicts
    port = 15800
    sim = TCSSimulator(host="localhost", port=port)
    sim.start()
    time.sleep(0.2)  # Give server time to start
    yield sim
    sim.stop()


@pytest.fixture
def tcs(tcs_server):
    """Create a MagIO client connected to the test server."""
    return MagIO(host="localhost", port=15800, online=True, timeout=5)


@pytest.fixture
def tcs_offline():
    """Create an offline MagIO client."""
    return MagIO(host="localhost", port=15800, online=False)


# === Connection Tests ===

class TestConnection:
    """Test basic connection handling."""
    
    def test_open_close(self, tcs):
        """Test opening and closing connection."""
        err = tcs.open()
        assert err == 0, "Failed to open connection"
        tcs.close()
    
    def test_multiple_open_close(self, tcs):
        """Test reference counting with multiple open/close."""
        err1 = tcs.open()
        assert err1 == 0
        
        err2 = tcs.open()
        assert err2 == 0
        
        tcs.close()  # Should not actually close yet
        
        # Connection should still work
        err, _ = tcs.request("telel")
        assert err == 0
        
        tcs.close()  # Now it closes
    
    def test_offline_mode(self, tcs_offline):
        """Test offline mode doesn't try to connect."""
        err = tcs_offline.open()
        assert err == 0
        tcs_offline.close()
    
    def test_connection_refused(self):
        """Test handling of connection refused."""
        tcs = MagIO(host="localhost", port=19999, online=True, timeout=1)
        err = tcs.open()
        assert err == MagIOError.MAGIO_ERROR


# === Request/Command Tests ===

class TestRequestCommand:
    """Test basic request and command methods."""
    
    def test_request_simple(self, tcs, tcs_server):
        """Test simple request/response."""
        tcs_server.clear_commands()
        
        err = tcs.open()
        assert err == 0
        
        err, response = tcs.request("telel")
        assert err == 0
        assert response != ""
        assert float(response)  # Should be a valid float
        
        tcs.close()
        
        # Verify server received the command
        cmds = tcs_server.get_commands()
        assert "telel" in cmds
    
    def test_command_simple(self, tcs):
        """Test command method (no response needed)."""
        err = tcs.open()
        assert err == 0
        
        err = tcs.command("telel")
        assert err == 0
        
        tcs.close()
    
    def test_offline_request(self, tcs_offline):
        """Test request in offline mode returns empty."""
        err, response = tcs_offline.request("telel")
        assert err == 0
        assert response == ""


# === Airmass Tests ===

class TestGetAirmass:
    """Test get_airmass method."""
    
    def test_get_airmass_all(self, tcs, tcs_server):
        """Test fetching all airmass-related values."""
        tcs_server.clear_commands()
        tcs_server.update_position(elevation=45.0, azimuth=180.0, rotator=90.0)
        
        err, data = tcs.get_airmass(
            want_airmass=True,
            want_rotangle=True,
            want_rotatore=True,
            want_azimuth=True,
            want_elevation=True,
            want_para=True
        )
        
        assert err == 0
        assert isinstance(data, AirmassData)
        assert data.airmass is not None
        assert data.rotangle is not None
        assert data.rotatore is not None
        assert data.azimuth is not None
        assert data.elevation is not None
        assert data.para is not None
        
        # Verify values are reasonable
        assert 1.0 <= data.airmass <= 10.0  # Valid airmass range
        assert 0 <= data.azimuth < 360
        assert 0 <= data.elevation <= 90
        
        # Verify all commands were sent
        cmds = tcs_server.get_commands()
        assert "airmass" in cmds
        assert "rotangle" in cmds
        assert "rotatore" in cmds
        assert "telaz" in cmds
        assert "telel" in cmds
        assert "telpa" in cmds
    
    def test_get_airmass_partial(self, tcs, tcs_server):
        """Test fetching only some values."""
        tcs_server.clear_commands()
        
        err, data = tcs.get_airmass(
            want_rotatore=True,
            want_elevation=True
        )
        
        assert err == 0
        assert data.rotatore is not None
        assert data.elevation is not None
        assert data.airmass is None  # Not requested
        assert data.rotangle is None
        
        # Verify only requested commands were sent
        cmds = tcs_server.get_commands()
        assert "rotatore" in cmds
        assert "telel" in cmds
        assert "airmass" not in cmds
    
    def test_get_airmass_elevation_values(self, tcs, tcs_server):
        """Test airmass calculation at different elevations."""
        test_elevations = [90.0, 60.0, 45.0, 30.0]
        
        for elev in test_elevations:
            tcs_server.update_position(elevation=elev)
            err, data = tcs.get_airmass(want_airmass=True, want_elevation=True)
            
            assert err == 0
            assert abs(data.elevation - elev) < 1.0  # Allow small drift
            
            # Verify airmass is reasonable for elevation
            expected_airmass = 1.0 / math.cos(math.radians(90 - elev))
            assert abs(data.airmass - expected_airmass) < 0.1
    
    def test_get_airmass_offline(self, tcs_offline):
        """Test airmass in offline mode."""
        err, data = tcs_offline.get_airmass(
            want_rotatore=True,
            want_elevation=True
        )
        
        assert err == 0
        assert data.rotatore is None  # No data in offline mode
        assert data.elevation is None


# === Coordinate Tests ===

class TestGetCoordinates:
    """Test get_coordinates method."""
    
    def test_get_coordinates(self, tcs, tcs_server):
        """Test fetching telescope coordinates."""
        tcs_server.clear_commands()
        tcs_server.update_coordinates(ra_hours=12.5, dec_degrees=-30.0, equinox=2000.0)
        
        err, data = tcs.get_coordinates()
        
        assert err == 0
        assert isinstance(data, CoordinateData)
        assert data.alpha is not None
        assert data.delta is not None
        assert data.equinox is not None
        
        # Verify values are reasonable
        assert 0 <= data.alpha < 24  # RA in hours
        assert -90 <= data.delta <= 90  # Dec in degrees
        
        # Verify commands were sent
        cmds = tcs_server.get_commands()
        assert "ra" in cmds
        assert "dec" in cmds
        assert "epoch" in cmds
    
    def test_get_coordinates_parsing(self, tcs, tcs_server):
        """Test coordinate parsing accuracy."""
        # Set known coordinates
        tcs_server.update_coordinates(ra_hours=6.75, dec_degrees=45.5)  # 6h 45m, +45d 30m
        
        err, data = tcs.get_coordinates()
        
        assert err == 0
        # Allow small tolerance for parsing/formatting
        assert abs(data.alpha - 6.75) < 0.01
        assert abs(data.delta - 45.5) < 0.1
    
    def test_get_coordinates_negative_dec(self, tcs, tcs_server):
        """Test negative declination parsing."""
        tcs_server.update_coordinates(dec_degrees=-45.5)
        
        err, data = tcs.get_coordinates()
        
        assert err == 0
        assert data.delta < 0


# === Time Tests ===

class TestGetTime:
    """Test time-related methods."""
    
    def test_get_ut_st(self, tcs, tcs_server):
        """Test fetching UT and ST."""
        tcs_server.clear_commands()
        
        err, ut, st = tcs.get_ut_st()
        
        assert err == 0
        assert ut is not None
        assert st is not None
        
        # Verify values are in valid range (seconds since midnight)
        assert 0 <= ut < 86400
        assert 0 <= st < 86400
        
        # Verify commands were sent
        cmds = tcs_server.get_commands()
        assert "ut" in cmds
        assert "st" in cmds
    
    def test_get_ut_st_offline(self, tcs_offline):
        """Test time in offline mode."""
        err, ut, st = tcs_offline.get_ut_st()
        
        assert err == 0
        assert ut is None
        assert st is None


# === Weather Tests ===

class TestGetWeather:
    """Test weather data retrieval."""
    
    def test_get_weather(self, tcs, tcs_server):
        """Test fetching weather data."""
        tcs_server.clear_commands()
        
        err, weather = tcs.get_weather()
        
        assert err == 0
        assert isinstance(weather, dict)
        
        # Verify all weather keys are present
        assert "temperature" in weather
        assert "pressure" in weather
        assert "humidity" in weather
        assert "wind" in weather
        assert "wind_direction" in weather
        
        # Verify values are reasonable
        assert -40 <= weather["temperature"] <= 50  # Celsius
        assert 500 <= weather["pressure"] <= 1100  # mbar
        assert 0 <= weather["humidity"] <= 100  # percent
        assert weather["wind"] >= 0  # m/s
        assert 0 <= weather["wind_direction"] < 360  # degrees
        
        # Verify commands were sent
        cmds = tcs_server.get_commands()
        assert "wxtemp" in cmds
        assert "wxpres" in cmds
        assert "wxhumid" in cmds
        assert "wxwind" in cmds
        assert "wxwdir" in cmds
    
    def test_get_weather_offline(self, tcs_offline):
        """Test weather in offline mode."""
        err, weather = tcs_offline.get_weather()
        
        assert err == 0
        assert weather == {}


# === Catalog Tests ===

class TestGetCatalog:
    """Test catalog object retrieval."""
    
    def test_get_catalog_object(self, tcs, tcs_server):
        """Test fetching catalog object name."""
        tcs_server.clear_commands()
        
        err, name = tcs.get_catalog_object()
        
        assert err == 0
        assert isinstance(name, str)
        assert len(name) > 0
        
        # Verify command was sent
        cmds = tcs_server.get_commands()
        assert "catobj" in cmds
    
    def test_get_catalog_object_offline(self, tcs_offline):
        """Test catalog in offline mode."""
        err, name = tcs_offline.get_catalog_object()
        
        assert err == 0
        assert name == ""


# === Error Handling Tests ===

class TestErrorHandling:
    """Test error handling and error strings."""
    
    def test_error_string_known(self):
        """Test error string for known errors."""
        assert "error" in MagIO.error_string(MagIOError.MAGIO_ERROR).lower()
        assert "timeout" in MagIO.error_string(MagIOError.MAGIO_TIMEOUT).lower()
        assert "reject" in MagIO.error_string(MagIOError.MAGIO_REJECT1).lower()
        assert "reject" in MagIO.error_string(MagIOError.MAGIO_REJECT2).lower()
        assert "reject" in MagIO.error_string(MagIOError.MAGIO_REJECT3).lower()
    
    def test_error_string_unknown(self):
        """Test error string for unknown error code."""
        result = MagIO.error_string(9999)
        assert "9999" in result or "unknown" in result.lower()


# === Integration Tests ===

class TestIntegration:
    """Integration tests simulating ADC_Controller usage."""
    
    def test_adc_controller_pattern(self, tcs, tcs_server):
        """
        Test the pattern used by ADC_Controller.updateTCS().
        
        ADC_Controller calls:
            err = [tcs getAirmass:NULL rotangle:NULL rotatore:&r
                       azimuth:NULL elevation:&e para:NULL];
        """
        tcs_server.clear_commands()
        tcs_server.update_position(elevation=60.0, rotator=45.0)
        
        err, data = tcs.get_airmass(
            want_rotatore=True,
            want_elevation=True
        )
        
        assert err == 0
        assert data.rotatore is not None
        assert data.elevation is not None
        
        # These should not have been fetched
        assert data.airmass is None
        assert data.rotangle is None
        assert data.azimuth is None
        assert data.para is None
        
        # Verify only the needed commands were sent
        cmds = tcs_server.get_commands()
        assert len(cmds) == 2
        assert "rotatore" in cmds
        assert "telel" in cmds
    
    def test_repeated_queries(self, tcs, tcs_server):
        """Test rapid repeated queries (as would happen in update loop)."""
        tcs_server.clear_commands()
        
        for _ in range(10):
            err, data = tcs.get_airmass(
                want_rotatore=True,
                want_elevation=True
            )
            assert err == 0
        
        # Should have sent 20 commands total (2 per iteration)
        cmds = tcs_server.get_commands()
        assert len(cmds) == 20
    
    def test_all_commands_received(self, tcs, tcs_server):
        """Verify all MagIO commands are properly received by server."""
        tcs_server.clear_commands()
        
        # Call all methods to generate all commands
        tcs.get_airmass(
            want_airmass=True,
            want_rotangle=True,
            want_rotatore=True,
            want_azimuth=True,
            want_elevation=True,
            want_para=True
        )
        tcs.get_coordinates()
        tcs.get_ut_st()
        tcs.get_weather()
        tcs.get_catalog_object()
        
        cmds = tcs_server.get_commands()
        
        # All expected commands
        expected = [
            "airmass", "rotangle", "rotatore", "telaz", "telel", "telpa",
            "ra", "dec", "epoch",
            "ut", "st",
            "wxtemp", "wxpres", "wxhumid", "wxwind", "wxwdir",
            "catobj"
        ]
        
        for cmd in expected:
            assert cmd in cmds, f"Command '{cmd}' was not received by server"


# === Run tests ===

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
