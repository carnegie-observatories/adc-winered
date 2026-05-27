#!/usr/bin/env python3
"""
MagIO - TCP interface for Magellan TCS communication.

This module mimics the behavior from the Objective-C MagIO class used by ADC_Controller.
It connects to the TCS (Telescope Control System) via TCP and sends/receives commands.

Usage by ADC_Controller:
    - Connects to TCS on port 5800
    - Calls getAirmass to fetch rotator encoder (rotatore) and elevation (telel)

Protocol:
    - Commands are sent as text terminated by newline
    - Responses are received as text terminated by newline
"""

import socket
import threading
from dataclasses import dataclass
from typing import Optional
from enum import IntEnum


class MagIOError(IntEnum):
    """Error codes matching the Objective-C implementation."""
    MAGIO_ERROR = 1100
    MAGIO_TIMEOUT = 1101
    MAGIO_REJECT1 = 1102
    MAGIO_REJECT2 = 1103
    MAGIO_REJECT3 = 1104


@dataclass
class AirmassData:
    """Data returned by getAirmass command."""
    airmass: Optional[float] = None
    rotangle: Optional[float] = None
    rotatore: Optional[float] = None
    azimuth: Optional[float] = None
    elevation: Optional[float] = None
    para: Optional[float] = None


@dataclass
class CoordinateData:
    """Telescope coordinate data."""
    alpha: float  # Right ascension in hours
    delta: float  # Declination in degrees
    equinox: float


class MagIO:
    """
    TCP connection to Magellan TCS (Telescope Control System).
    
    Mimics the Objective-C MagIO class behavior for communicating with the
    telescope control system. The ADC_Controller uses this to get rotator
    encoder and elevation values.
    
    Args:
        host: TCS hostname or IP address
        port: TCS port (default 5800)
        online: If False, runs in offline/simulation mode
        timeout: Socket timeout in seconds
    """
    
    DEFAULT_PORT = 5800
    RESPONSE_SIZE = 512
    
    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        online: bool = True,
        timeout: int = 5
    ):
        self.host = host
        self.port = port
        self.online = online
        self.timeout = timeout
        self.terminator = '\n'
        
        self._sock: Optional[socket.socket] = None
        self._lock = threading.RLock()
        self._count = 0
        
        # Simulation state
        self._sim_elevation = 45.0
        self._sim_rotator = 0.0
        self._sim_time = 0.0
    
    def open(self) -> int:
        """
        Open TCP connection to TCS.
        
        Returns:
            0 on success, error code on failure
        """
        with self._lock:
            if self._count == 0:
                if not self.online:
                    self._count += 1
                    return 0
                try:
                    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._sock.settimeout(self.timeout)
                    self._sock.connect((self.host, self.port))
                except socket.error as e:
                    self._sock = None
                    return MagIOError.MAGIO_ERROR
            self._count += 1
            return 0
    
    def close(self) -> None:
        """Close TCP connection to TCS."""
        with self._lock:
            self._count -= 1
            if self._count <= 0:
                self._count = 0
                if self._sock:
                    try:
                        self._sock.close()
                    except socket.error:
                        pass
                    self._sock = None
    
    def request(self, cmd: str, timeout: Optional[int] = None) -> tuple[int, str]:
        """
        Send command and receive response.
        
        Args:
            cmd: Command string (without terminator)
            timeout: Optional timeout override
        
        Returns:
            Tuple of (error_code, response_string)
        """
        with self._lock:
            if not self.online:
                # Simulation mode - return empty response
                return 0, ""
            
            if not self._sock:
                return MagIOError.MAGIO_ERROR, ""
            
            try:
                # Set timeout if specified
                if timeout is not None:
                    self._sock.settimeout(timeout)
                else:
                    self._sock.settimeout(self.timeout)
                
                # Send command with terminator
                command = f"{cmd}{self.terminator}"
                self._sock.sendall(command.encode('utf-8'))
                
                # Receive response until terminator
                response = ""
                while True:
                    chunk = self._sock.recv(self.RESPONSE_SIZE)
                    if not chunk:
                        break
                    response += chunk.decode('utf-8')
                    if self.terminator in response:
                        response = response.split(self.terminator)[0]
                        break
                
                return 0, response
                
            except socket.timeout:
                return MagIOError.MAGIO_TIMEOUT, ""
            except socket.error:
                return MagIOError.MAGIO_ERROR, ""
    
    def command(self, cmd: str, timeout: Optional[int] = None) -> int:
        """
        Send command without caring about response.
        
        Args:
            cmd: Command string
            timeout: Optional timeout override
        
        Returns:
            Error code (0 on success)
        """
        err, _ = self.request(cmd, timeout)
        return err
    
    # === TCS Commands (as used by ADC_Controller) ===
    
    def get_airmass(
        self,
        want_airmass: bool = False,
        want_rotangle: bool = False,
        want_rotatore: bool = False,
        want_azimuth: bool = False,
        want_elevation: bool = False,
        want_para: bool = False
    ) -> tuple[int, AirmassData]:
        """
        Get telescope airmass, rotator, and position data.
        
        This is the main method used by ADC_Controller to fetch:
        - rotatore: Rotator encoder value
        - elevation: Telescope elevation
        
        Args:
            want_*: Flags indicating which values to fetch
        
        Returns:
            Tuple of (error_code, AirmassData)
        """
        err = self.open()
        if err:
            return err, AirmassData()
        
        data = AirmassData()
        
        try:
            # In simulation mode, update and return simulated values
            if not self.online:
                import math
                import time
                self._sim_time = time.time()
                # Simulate slow rotator drift (10 degrees/minute)
                self._sim_rotator = (self._sim_time * 10.0 / 60.0) % 360.0
                # Simulate elevation varying between 30 and 70 degrees
                self._sim_elevation = 50.0 + 20.0 * math.sin(self._sim_time / 120.0)
                
                if want_rotatore:
                    data.rotatore = self._sim_rotator
                if want_elevation:
                    data.elevation = self._sim_elevation
                if want_airmass:
                    data.airmass = 1.0 / math.cos(math.radians(90 - self._sim_elevation))
                if want_azimuth:
                    data.azimuth = 180.0
                return 0, data
            
            if want_airmass:
                err, response = self.request("airmass")
                if err:
                    return err, data
                if self.online and response:
                    data.airmass = float(response)
            
            if want_rotangle:
                err, response = self.request("rotangle")
                if err:
                    return err, data
                if self.online and response:
                    data.rotangle = float(response)
            
            if want_rotatore:
                err, response = self.request("rotatore")
                if err:
                    return err, data
                if self.online and response:
                    data.rotatore = float(response)
            
            if want_azimuth:
                err, response = self.request("telaz")
                if err:
                    return err, data
                if self.online and response:
                    data.azimuth = float(response)
            
            if want_elevation:
                err, response = self.request("telel")
                if err:
                    return err, data
                if self.online and response:
                    data.elevation = float(response)
            
            if want_para:
                err, response = self.request("telpa")
                if err:
                    return err, data
                if self.online and response:
                    data.para = float(response)
            
            return 0, data
            
        finally:
            self.close()
    
    def get_coordinates(self, equinox: Optional[float] = None) -> tuple[int, CoordinateData]:
        """
        Get telescope coordinates (RA, Dec, Equinox).
        
        Args:
            equinox: Target equinox for precession (optional)
        
        Returns:
            Tuple of (error_code, CoordinateData)
        """
        err = self.open()
        if err:
            return err, CoordinateData(0, 0, 2000.0)
        
        try:
            alpha = 0.0
            delta = 0.0
            eq = 2000.0
            
            # Get RA
            err, response = self.request("ra")
            if err:
                return err, CoordinateData(0, 0, 2000.0)
            if self.online and response:
                parts = response.split(':')
                if len(parts) >= 3:
                    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
                    alpha = h + m/60.0 + s/3600.0
            
            # Get Dec
            err, response = self.request("dec")
            if err:
                return err, CoordinateData(alpha, 0, 2000.0)
            if self.online and response:
                parts = response.replace('-', ':-').replace('+', ':+').split(':')
                parts = [p for p in parts if p]
                if len(parts) >= 3:
                    sign = -1 if '-' in response else 1
                    h, m, s = abs(float(parts[0])), abs(float(parts[1])), abs(float(parts[2]))
                    delta = sign * (h + m/60.0 + s/3600.0)
            
            # Get Equinox
            err, response = self.request("epoch")
            if err:
                return err, CoordinateData(alpha, delta, 2000.0)
            if self.online and response:
                eq = float(response)
            
            return 0, CoordinateData(alpha, delta, eq)
            
        finally:
            self.close()
    
    def get_ut_st(self) -> tuple[int, Optional[int], Optional[int]]:
        """
        Get Universal Time and Sidereal Time.
        
        Returns:
            Tuple of (error_code, ut_seconds, st_seconds)
        """
        err = self.open()
        if err:
            return err, None, None
        
        try:
            ut = None
            st = None
            
            # Get UT
            err, response = self.request("ut")
            if err:
                return err, None, None
            if self.online and response:
                parts = response.split(':')
                if len(parts) >= 3:
                    hr, mi, sc = int(parts[0]), int(parts[1]), int(parts[2])
                    ut = hr * 3600 + mi * 60 + sc
            
            # Get ST
            err, response = self.request("st")
            if err:
                return err, ut, None
            if self.online and response:
                parts = response.split(':')
                if len(parts) >= 3:
                    hr, mi, sc = int(parts[0]), int(parts[1]), int(parts[2])
                    st = hr * 3600 + mi * 60 + sc
            
            return 0, ut, st
            
        finally:
            self.close()
    
    def get_weather(self) -> tuple[int, dict]:
        """
        Get weather data from WXT sensor.
        
        Returns:
            Tuple of (error_code, weather_dict)
        """
        err = self.open()
        if err:
            return err, {}
        
        weather = {}
        
        try:
            commands = [
                ("wxtemp", "temperature"),
                ("wxpres", "pressure"),
                ("wxhumid", "humidity"),
                ("wxwind", "wind"),
                ("wxwdir", "wind_direction"),
            ]
            
            for cmd, key in commands:
                err, response = self.request(cmd)
                if err:
                    return err, weather
                if self.online and response:
                    weather[key] = float(response)
            
            return 0, weather
            
        finally:
            self.close()
    
    def get_catalog_object(self) -> tuple[int, str]:
        """
        Get current catalog object name.
        
        Returns:
            Tuple of (error_code, object_name)
        """
        err = self.open()
        if err:
            return err, ""
        
        try:
            err, response = self.request("catobj")
            if err:
                return err, ""
            return 0, response
        finally:
            self.close()
    
    @staticmethod
    def error_string(err: int) -> str:
        """Convert error code to human-readable string."""
        error_messages = {
            MagIOError.MAGIO_ERROR: "TelIO: error",
            MagIOError.MAGIO_TIMEOUT: "TelIO: timeout",
            MagIOError.MAGIO_REJECT1: "TelIO: guider probe-1 move rejected",
            MagIOError.MAGIO_REJECT2: "TelIO: guider probe-2 move rejected",
            MagIOError.MAGIO_REJECT3: "TelIO: guider probe-3 move rejected",
        }
        return error_messages.get(err, f"Unknown error ({err})")


# === Example usage / test code ===
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MagIO TCS client")
    parser.add_argument("--host", default="localhost", help="TCS host")
    parser.add_argument("--port", type=int, default=5800, help="TCS port")
    parser.add_argument("--offline", action="store_true", help="Run in offline mode")
    args = parser.parse_args()
    
    tcs = MagIO(host=args.host, port=args.port, online=not args.offline)
    
    print(f"Connecting to TCS at {args.host}:{args.port}")
    print(f"Online mode: {tcs.online}")
    
    # Fetch what ADC_Controller uses: rotatore and elevation
    err, data = tcs.get_airmass(want_rotatore=True, want_elevation=True)
    
    if err:
        print(f"Error: {MagIO.error_string(err)}")
    else:
        print(f"Rotator encoder: {data.rotatore}")
        print(f"Elevation: {data.elevation}")
