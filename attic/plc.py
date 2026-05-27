#!/usr/bin/env python3
"""
PLC Interface Base Classes for ADC Control.

This module provides the abstract PLCDriver base class and data models
for PLC communication. Concrete implementations (e.g., ADSPLCDriver,
ModbusPLCDriver) should be in separate modules.
"""

from dataclasses import dataclass
from typing import Protocol
import random


@dataclass
class PLCStatus:
    """Status data read from the ADC PLC."""
    # ADC Slide (pneumatic - only limit switches, no moving state)
    adc_slide_inserted: bool = False
    adc_slide_retracted: bool = True
    # Prism A (motorized)
    prism_a_position: float = 0.0
    prism_a_moving: bool = False
    prism_a_at_target: bool = True
    # Prism B (motorized)
    prism_b_position: float = 0.0
    prism_b_moving: bool = False
    prism_b_at_target: bool = True
    # Mirror (pneumatic - only limit switches, no moving state)
    mirror_inserted: bool = False
    mirror_retracted: bool = True


@dataclass
class PLCCommand:
    """Command data to write to the ADC PLC."""
    prism_a_target: float = 0.0
    prism_b_target: float = 0.0
    adc_slide_insert: bool = False   # TRUE=insert, FALSE=retract
    mirror_insert: bool = False       # TRUE=insert, FALSE=retract


class PLCDriver(Protocol):
    """
    Protocol for PLC drivers.
    
    Implementations must provide connect(), disconnect(), read_status(),
    and write_command() methods.
    """
    
    def connect(self) -> bool:
        """Connect to PLC. Returns True on success."""
        ...
    
    def disconnect(self) -> None:
        """Disconnect from PLC."""
        ...
    
    def read_status(self) -> tuple[bool, PLCStatus]:
        """Read current status from PLC. Returns (success, status)."""
        ...
    
    def write_command(self, command: PLCCommand) -> bool:
        """Write command to PLC. Returns True on success."""
        ...


class SimulatedPLCDriver:
    """
    Simulated PLC driver for testing without real hardware.
    
    Simulates prism motion at configurable speed and instant slide/mirror moves.
    
    Args:
        move_speed: Prism movement speed in degrees per second
        poll_interval: Expected polling interval in seconds (for motion calculation)
    """
    
    def __init__(self, move_speed: float = 5.0, poll_interval: float = 0.5):
        self._connected = False
        self._move_speed = move_speed  # degrees per second
        self._poll_interval = poll_interval
        
        # Simulated state
        self._prism_a_position = 0.0
        self._prism_b_position = 0.0
        self._prism_a_target = 0.0
        self._prism_b_target = 0.0
        self._adc_slide_inserted = False
        self._mirror_inserted = False
    
    def connect(self) -> bool:
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        self._connected = False
    
    def read_status(self) -> tuple[bool, PLCStatus]:
        if not self._connected:
            if not self.connect():
                return False, PLCStatus()
        
        # Move prisms toward targets
        move_rate = self._move_speed * self._poll_interval
        threshold = 0.1
        
        # Prism A
        diff_a = self._prism_a_target - self._prism_a_position
        prism_a_moving = abs(diff_a) > threshold
        if prism_a_moving:
            step = min(abs(diff_a), move_rate) * (1 if diff_a > 0 else -1)
            self._prism_a_position += step
        
        # Prism B
        diff_b = self._prism_b_target - self._prism_b_position
        prism_b_moving = abs(diff_b) > threshold
        if prism_b_moving:
            step = min(abs(diff_b), move_rate) * (1 if diff_b > 0 else -1)
            self._prism_b_position += step
        
        # Add encoder noise
        noise_a = random.gauss(0, 0.001)
        noise_b = random.gauss(0, 0.001)
        
        return True, PLCStatus(
            adc_slide_inserted=self._adc_slide_inserted,
            adc_slide_retracted=not self._adc_slide_inserted,
            prism_a_position=self._prism_a_position + noise_a,
            prism_a_moving=prism_a_moving,
            prism_a_at_target=not prism_a_moving,
            prism_b_position=self._prism_b_position + noise_b,
            prism_b_moving=prism_b_moving,
            prism_b_at_target=not prism_b_moving,
            mirror_inserted=self._mirror_inserted,
            mirror_retracted=not self._mirror_inserted,
        )
    
    def write_command(self, command: PLCCommand) -> bool:
        if not self._connected:
            return False
        
        # Update targets
        self._prism_a_target = command.prism_a_target
        self._prism_b_target = command.prism_b_target
        
        # Handle slide commands (instant in simulation)
        self._adc_slide_inserted = command.adc_slide_insert
        self._mirror_inserted = command.mirror_insert
        
        return True
