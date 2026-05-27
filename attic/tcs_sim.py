#!/usr/bin/env python3
"""
TCS Simulation Server - Provides random responses for MagIO testing.

This server mimics the Magellan TCS (Telescope Control System) protocol,
responding to commands with randomized but realistic telescope data.
"""

import socket
import threading
import random
import time
from typing import Optional


class TCSSimulator:
    """
    Simulates the Magellan TCS server for testing MagIO.
    
    Responds to all commands that MagIO can send with random but
    realistic values.
    """
    
    def __init__(self, host: str = "localhost", port: int = 5800):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Simulated telescope state
        self.elevation = 45.0
        self.azimuth = 180.0
        self.rotator = 0.0
        self.ra_hours = 12.5  # RA in hours
        self.dec_degrees = -30.0  # Dec in degrees
        self.equinox = 2000.0
        
        # Command handlers
        self._handlers = {
            "airmass": self._handle_airmass,
            "rotangle": self._handle_rotangle,
            "rotatore": self._handle_rotatore,
            "telaz": self._handle_telaz,
            "telel": self._handle_telel,
            "telpa": self._handle_telpa,
            "ra": self._handle_ra,
            "dec": self._handle_dec,
            "epoch": self._handle_epoch,
            "ut": self._handle_ut,
            "st": self._handle_st,
            "wxtemp": self._handle_wxtemp,
            "wxpres": self._handle_wxpres,
            "wxhumid": self._handle_wxhumid,
            "wxwind": self._handle_wxwind,
            "wxwdir": self._handle_wxwdir,
            "catobj": self._handle_catobj,
        }
        
        # Track received commands for testing
        self.received_commands: list[str] = []
    
    def _calculate_airmass(self) -> float:
        """Calculate airmass from elevation."""
        import math
        if self.elevation <= 0:
            return 99.9
        zenith_angle = 90.0 - self.elevation
        zenith_rad = math.radians(zenith_angle)
        return 1.0 / math.cos(zenith_rad)
    
    def _handle_airmass(self) -> str:
        return f"{self._calculate_airmass():.3f}"
    
    def _handle_rotangle(self) -> str:
        # Rotator angle (position angle on sky)
        return f"{self.rotator:.2f}"
    
    def _handle_rotatore(self) -> str:
        # Rotator encoder value (mechanical angle)
        encoder = self.rotator + random.uniform(-0.1, 0.1)
        return f"{encoder:.2f}"
    
    def _handle_telaz(self) -> str:
        return f"{self.azimuth:.2f}"
    
    def _handle_telel(self) -> str:
        return f"{self.elevation:.2f}"
    
    def _handle_telpa(self) -> str:
        # Parallactic angle
        pa = random.uniform(-180, 180)
        return f"{pa:.2f}"
    
    def _handle_ra(self) -> str:
        # Format: HH:MM:SS.ss
        h = int(self.ra_hours)
        m = int((self.ra_hours - h) * 60)
        s = ((self.ra_hours - h) * 60 - m) * 60
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    
    def _handle_dec(self) -> str:
        # Format: DD:MM:SS.s
        sign = "-" if self.dec_degrees < 0 else "+"
        dec_abs = abs(self.dec_degrees)
        d = int(dec_abs)
        m = int((dec_abs - d) * 60)
        s = ((dec_abs - d) * 60 - m) * 60
        return f"{sign}{d:02d}:{m:02d}:{s:04.1f}"
    
    def _handle_epoch(self) -> str:
        return f"{self.equinox:.1f}"
    
    def _handle_ut(self) -> str:
        # Current UTC time
        t = time.gmtime()
        return f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"
    
    def _handle_st(self) -> str:
        # Sidereal time (simplified simulation)
        st_hours = (time.time() / 3600) % 24
        h = int(st_hours)
        m = int((st_hours - h) * 60)
        s = int(((st_hours - h) * 60 - m) * 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    def _handle_wxtemp(self) -> str:
        # Temperature in Celsius
        return f"{random.uniform(5, 20):.1f}"
    
    def _handle_wxpres(self) -> str:
        # Pressure in mbar
        return f"{random.uniform(700, 760):.1f}"
    
    def _handle_wxhumid(self) -> str:
        # Humidity percentage
        return f"{random.uniform(10, 80):.1f}"
    
    def _handle_wxwind(self) -> str:
        # Wind speed in m/s
        return f"{random.uniform(0, 15):.1f}"
    
    def _handle_wxwdir(self) -> str:
        # Wind direction in degrees
        return f"{random.uniform(0, 360):.1f}"
    
    def _handle_catobj(self) -> str:
        # Catalog object name
        objects = ["NGC1234", "M31", "HD12345", "HIP98765", "Vega", "Sirius"]
        return random.choice(objects)
    
    def _handle_client(self, conn: socket.socket, addr: tuple) -> None:
        """Handle a single client connection."""
        try:
            conn.settimeout(5.0)
            buffer = ""
            
            while self._running:
                try:
                    data = conn.recv(512)
                    if not data:
                        break
                    
                    buffer += data.decode('utf-8')
                    
                    # Process complete commands (terminated by newline)
                    while '\n' in buffer:
                        cmd, buffer = buffer.split('\n', 1)
                        cmd = cmd.strip()
                        
                        if cmd:
                            with self._lock:
                                self.received_commands.append(cmd)
                            
                            # Generate response
                            handler = self._handlers.get(cmd.lower())
                            if handler:
                                response = handler()
                            else:
                                response = "ERROR"
                            
                            # Send response with newline terminator
                            conn.sendall(f"{response}\n".encode('utf-8'))
                            
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            conn.close()
    
    def start(self) -> None:
        """Start the simulation server."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(5)
        self._sock.settimeout(1.0)
        self._running = True
        
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
    
    def _accept_loop(self) -> None:
        """Accept incoming connections."""
        while self._running:
            try:
                conn, addr = self._sock.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    continue
                break
    
    def stop(self) -> None:
        """Stop the simulation server."""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def clear_commands(self) -> None:
        """Clear the received commands log."""
        with self._lock:
            self.received_commands.clear()
    
    def get_commands(self) -> list[str]:
        """Get a copy of received commands."""
        with self._lock:
            return list(self.received_commands)
    
    def update_position(
        self,
        elevation: Optional[float] = None,
        azimuth: Optional[float] = None,
        rotator: Optional[float] = None
    ) -> None:
        """Update simulated telescope position."""
        if elevation is not None:
            self.elevation = max(0, min(90, elevation))
        if azimuth is not None:
            self.azimuth = azimuth % 360
        if rotator is not None:
            self.rotator = rotator % 360
    
    def update_coordinates(
        self,
        ra_hours: Optional[float] = None,
        dec_degrees: Optional[float] = None,
        equinox: Optional[float] = None
    ) -> None:
        """Update simulated telescope coordinates."""
        if ra_hours is not None:
            self.ra_hours = ra_hours % 24
        if dec_degrees is not None:
            self.dec_degrees = max(-90, min(90, dec_degrees))
        if equinox is not None:
            self.equinox = equinox


def main():
    """Run the simulator as a standalone server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="TCS Simulation Server")
    parser.add_argument("--host", default="localhost", help="Bind host")
    parser.add_argument("--port", type=int, default=5800, help="Bind port")
    args = parser.parse_args()
    
    sim = TCSSimulator(host=args.host, port=args.port)
    
    print(f"Starting TCS simulator on {args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    
    sim.start()
    
    try:
        while True:
            # Slowly drift the telescope position for realism
            sim.update_position(
                elevation=sim.elevation + random.uniform(-0.1, 0.1),
                azimuth=sim.azimuth + random.uniform(-0.05, 0.05),
                rotator=sim.rotator + random.uniform(-0.02, 0.02)
            )
            time.sleep(1)
            
            # Print received commands
            cmds = sim.get_commands()
            if cmds:
                print(f"Commands received: {cmds}")
                sim.clear_commands()
                
    except KeyboardInterrupt:
        print("\nStopping simulator...")
        sim.stop()


if __name__ == "__main__":
    main()
