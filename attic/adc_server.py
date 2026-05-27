#!/usr/bin/env python3
"""
ADC Control Server - FastAPI implementation
Provides REST API for ADC hardware control.
"""

import asyncio
import math
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
from enum import Enum

from magio import MagIO
from plc import PLCDriver, PLCStatus, PLCCommand, SimulatedPLCDriver


# === Background Task Configuration ===
TCS_HOST = os.environ.get("TCS_HOST", "localhost")
TCS_PORT = int(os.environ.get("TCS_PORT", "5800"))
TCS_POLL_INTERVAL = float(os.environ.get("TCS_POLL_INTERVAL", "1.0"))  # seconds
TCS_ONLINE = os.environ.get("TCS_ONLINE", "true").lower() == "true"

# Beckhoff ADS PLC Configuration
ADS_NET_ID = os.environ.get("ADS_NET_ID", "127.0.0.1.1.1")  # Target PLC AMS Net ID
ADS_PORT = int(os.environ.get("ADS_PORT", "851"))  # TwinCAT 3 PLC runtime port
ADS_IP = os.environ.get("ADS_IP")  # Target PLC IP (required on Linux)
LOCAL_AMS_NET_ID = os.environ.get("LOCAL_AMS_NET_ID")  # Local AMS Net ID for routing
PLC_POLL_INTERVAL = float(os.environ.get("PLC_POLL_INTERVAL", "0.5"))  # seconds
PLC_ONLINE = os.environ.get("PLC_ONLINE", "false").lower() == "true"

# Runtime-configurable settings
class RuntimeSettings:
    """Runtime-configurable settings that can be changed via API."""
    def __init__(self):
        self.tcs_poll_interval = TCS_POLL_INTERVAL

runtime_settings = RuntimeSettings()


# === Prism Angle Calculations ===
RADS = 180.0 / math.pi  # Radians to degrees conversion factor


def modneg(x: float, max_val: float) -> float:
    """Normalize angle to range [-max/2, +max/2]."""
    while x > max_val / 2.0:
        x -= max_val
    while x <= -max_val / 2.0:
        x += max_val
    return x


class PrismMode(int, Enum):
    """Prism calculation mode."""
    NORMAL = 0       # Default mode with dispersion correction
    NO_DISPERSION = 1  # No dispersion correction
    INVERTED = 2     # Inverted dispersion correction


def calculate_prism_targets(
    elevation: float,
    rotator: float,
    prism_mode: PrismMode = PrismMode.NORMAL
) -> tuple[float, float]:
    """
    Calculate target prism angles based on telescope elevation and rotator.
    
    This implements the same algorithm as updateLensTarget in ADC_Controller.m.
    
    Args:
        elevation: Telescope elevation in degrees
        rotator: Telescope rotator angle in degrees
        prism_mode: Prism calculation mode (0, 1, or 2)
    
    Returns:
        Tuple of (target_a, target_b) prism angles in degrees, normalized to [-180, +180]
    """
    # Zenith angle
    z = 90.0 - elevation
    # Calculate y factor (clamp tan to max value at 59.01 degrees zenith)
    y = min(1.0, math.tan(z / RADS) / 1.665)
    # Calculate angle a
    a = math.acos(y) * RADS
    # Adjusted rotator
    r = 90.0 - rotator
    
    if prism_mode == PrismMode.NORMAL:
        # Normal mode with dispersion correction
        target_a = modneg(r + 180 - a, 360)
        target_b = modneg(r - 180 + a, 360)
    elif prism_mode == PrismMode.NO_DISPERSION:
        # No dispersion correction
        target_a = modneg(r + 90, 360)
        target_b = modneg(r - 90, 360)
    else:  # PrismMode.INVERTED
        # Inverted dispersion correction
        target_a = modneg(r + a, 360)
        target_b = modneg(r - a, 360)
    
    return target_a, target_b


async def poll_tcs_data(magio: MagIO, interval: float) -> None:
    """Background task to poll TCS for elevation and rotator position."""
    while True:
        try:
            err, data = magio.get_airmass(
                want_elevation=True,
                want_rotatore=True
            )
            if err == 0:
                if data.elevation is not None:
                    state.telescope.elevation = data.elevation
                if data.rotatore is not None:
                    state.telescope.rotator = data.rotatore
                state.tcs_connected = True
            else:
                state.tcs_connected = False
        except Exception:
            state.tcs_connected = False
        
        # Use runtime-configurable interval for TCS polling
        await asyncio.sleep(runtime_settings.tcs_poll_interval)


# Global PLC driver for command writes
plc_driver: Optional[PLCDriver] = None


async def poll_plc_data(plc: PLCDriver, interval: float) -> None:
    """Background task to poll ADC data from PLC."""
    global plc_driver
    plc_driver = plc
    
    while True:
        try:
            # When in AUTO mode, calculate target prism angles from telescope data
            if state.adc.control_mode == ControlMode.AUTO:
                try:
                    prism_mode = PrismMode(state.adc.prism_mode)
                except ValueError:
                    prism_mode = PrismMode.NORMAL
                
                target_a, target_b = calculate_prism_targets(
                    elevation=state.telescope.elevation,
                    rotator=state.telescope.rotator,
                    prism_mode=prism_mode
                )
                state.adc.target_a = target_a
                state.adc.target_b = target_b
                
                # Send targets to PLC
                plc.write_command(PLCCommand(
                    prism_a_target=target_a,
                    prism_b_target=target_b,
                    adc_slide_insert=state.adc.in_status,
                    mirror_insert=state.mirror.in_status,
                ))
            
            success, data = plc.read_status()
            if success:
                # Update ADC state from PLC data
                if data.adc_slide_inserted:
                    state.adc.position = SlidePosition.INSERTED
                elif data.adc_slide_retracted:
                    state.adc.position = SlidePosition.RETRACTED
                
                state.adc.prism_a = data.prism_a_position
                state.adc.prism_b = data.prism_b_position
                state.adc.moving = False  # Pneumatic actuator - no moving state
                state.adc.lens_a_moving = data.prism_a_moving
                state.adc.lens_b_moving = data.prism_b_moving
                state.adc.in_status = data.adc_slide_inserted
                state.adc.out_status = data.adc_slide_retracted
                
                # Update mirror state from PLC data
                if data.mirror_inserted:
                    state.mirror.position = SlidePosition.INSERTED
                elif data.mirror_retracted:
                    state.mirror.position = SlidePosition.RETRACTED
                
                state.mirror.moving = False  # Pneumatic actuator - no moving state
                state.mirror.in_status = data.mirror_inserted
                state.mirror.out_status = data.mirror_retracted
                
                state.plc_connected = True
            else:
                state.plc_connected = False
        except Exception:
            state.plc_connected = False
        
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown tasks."""
    # Create MagIO instance for TCS communication
    magio = MagIO(
        host=TCS_HOST,
        port=TCS_PORT,
        online=TCS_ONLINE,
        timeout=5
    )
    
    # Create PLC driver for ADC hardware
    if PLC_ONLINE:
        from ads_plc import ADSPLCDriver
        plc: PLCDriver = ADSPLCDriver(
            ams_net_id=ADS_NET_ID,
            ams_port=ADS_PORT,
            ip=ADS_IP,
            local_ams_net_id=LOCAL_AMS_NET_ID,
        )
    else:
        plc = SimulatedPLCDriver(poll_interval=PLC_POLL_INTERVAL)
    
    # Start background polling tasks
    tcs_task = asyncio.create_task(poll_tcs_data(magio, TCS_POLL_INTERVAL))
    plc_task = asyncio.create_task(poll_plc_data(plc, PLC_POLL_INTERVAL))
    
    yield
    
    # Shutdown: cancel all polling tasks
    tcs_task.cancel()
    plc_task.cancel()
    try:
        await tcs_task
    except asyncio.CancelledError:
        pass
    try:
        await plc_task
    except asyncio.CancelledError:
        pass
    plc.disconnect()


app = FastAPI(title="ADC Control API", version="1.0.0", lifespan=lifespan)


# === Enums ===
class SlidePosition(str, Enum):
    RETRACTED = "Retracted"
    INSERTED = "Inserted"


class ControlMode(str, Enum):
    OFF = "Off"
    AUTO = "Auto"


# === Request/Response Models ===
class TelescopeData(BaseModel):
    elevation: float
    rotator: float


class ADCStatus(BaseModel):
    position: SlidePosition
    prism_a: float
    prism_b: float
    target_a: float
    target_b: float
    control_mode: ControlMode
    prism_mode: int = 0  # 0: Normal, 1: No Dispersion, 2: Inverted
    moving: bool
    lens_a_moving: bool
    lens_b_moving: bool
    in_status: bool
    out_status: bool


class MirrorStatus(BaseModel):
    position: SlidePosition
    moving: bool
    in_status: bool
    out_status: bool


class PositionRequest(BaseModel):
    position: SlidePosition


class PrismRequest(BaseModel):
    prism_a: float | None = None
    prism_b: float | None = None


class ControlRequest(BaseModel):
    mode: ControlMode


class PrismModeRequest(BaseModel):
    mode: int  # 0: Normal, 1: No Dispersion, 2: Inverted


class ControlIntervalRequest(BaseModel):
    interval: float  # TCS poll interval in seconds


class SettingsResponse(BaseModel):
    tcs_poll_interval: float
    prism_mode: int


# === In-memory state (replace with hardware interface) ===
class HardwareState:
    def __init__(self):
        self.telescope = TelescopeData(elevation=45.0, rotator=0.0)
        self.tcs_connected = False  # TCS connection status from background polling
        self.plc_connected = False  # PLC connection status from background polling
        self.adc = ADCStatus(
            position=SlidePosition.RETRACTED,
            prism_a=0.0,
            prism_b=0.0,
            target_a=0.0,
            target_b=0.0,
            control_mode=ControlMode.OFF,
            prism_mode=0,  # Default to Normal mode
            moving=False,
            lens_a_moving=False,
            lens_b_moving=False,
            in_status=False,
            out_status=True,
        )
        self.mirror = MirrorStatus(
            position=SlidePosition.RETRACTED,
            moving=False,
            in_status=False,
            out_status=True,
        )


state = HardwareState()


# === Telescope Endpoints ===
@app.get("/telescope", response_model=TelescopeData)
async def get_telescope():
    """Get current telescope elevation and rotator values."""
    return state.telescope


# === ADC Endpoints ===
@app.get("/adc/status", response_model=ADCStatus)
async def get_adc_status():
    """Get current ADC status including prism positions."""
    return state.adc


@app.post("/adc/position")
async def set_adc_position(request: PositionRequest):
    """Set ADC slide position (Retracted/Inserted)."""
    # Send command to PLC
    if plc_driver:
        plc_driver.write_command(PLCCommand(
            prism_a_target=state.adc.target_a,
            prism_b_target=state.adc.target_b,
            adc_slide_insert=(request.position == SlidePosition.INSERTED),
            mirror_insert=state.mirror.in_status,
        ))
    
    state.adc.position = request.position
    # Update status indicators based on position
    state.adc.in_status = request.position == SlidePosition.INSERTED
    state.adc.out_status = request.position == SlidePosition.RETRACTED
    return {"status": "ok", "position": request.position}


@app.post("/adc/prism")
async def set_prism_values(request: PrismRequest):
    """Set prism A and/or B target positions."""
    target_a = state.adc.target_a
    target_b = state.adc.target_b
    
    if request.prism_a is not None:
        state.adc.target_a = request.prism_a
        target_a = request.prism_a
    if request.prism_b is not None:
        state.adc.target_b = request.prism_b
        target_b = request.prism_b
    
    # Send targets to PLC
    if plc_driver:
        plc_driver.write_command(PLCCommand(
            prism_a_target=target_a,
            prism_b_target=target_b,
            adc_slide_insert=state.adc.in_status,
            mirror_insert=state.mirror.in_status,
        ))
    
    return {"status": "ok", "target_a": state.adc.target_a, "target_b": state.adc.target_b}


@app.post("/adc/control")
async def set_control_mode(request: ControlRequest):
    """Set ADC control mode (Off/Auto)."""
    state.adc.control_mode = request.mode
    return {"status": "ok", "mode": request.mode}


@app.post("/adc/prism_mode")
async def set_prism_mode(request: PrismModeRequest):
    """Set prism calculation mode (0: Normal, 1: No Dispersion, 2: Inverted)."""
    if request.mode not in (0, 1, 2):
        return {"status": "error", "message": "Invalid prism mode. Must be 0 (Normal), 1 (No Dispersion), or 2 (Inverted)."}
    state.adc.prism_mode = request.mode
    return {"status": "ok", "prism_mode": request.mode}


# === Mirror Endpoints ===
@app.get("/mirror/status", response_model=MirrorStatus)
async def get_mirror_status():
    """Get current mirror status."""
    return state.mirror


@app.post("/mirror/position")
async def set_mirror_position(request: PositionRequest):
    """Set mirror slide position (Retracted/Inserted)."""
    # Send command to PLC
    if plc_driver:
        plc_driver.write_command(PLCCommand(
            prism_a_target=state.adc.target_a,
            prism_b_target=state.adc.target_b,
            adc_slide_insert=state.adc.in_status,
            mirror_insert=(request.position == SlidePosition.INSERTED),
        ))
    
    state.mirror.position = request.position
    state.mirror.in_status = request.position == SlidePosition.INSERTED
    state.mirror.out_status = request.position == SlidePosition.RETRACTED
    return {"status": "ok", "position": request.position}


# === Settings Endpoints ===
@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current server settings."""
    return SettingsResponse(
        tcs_poll_interval=runtime_settings.tcs_poll_interval,
        prism_mode=state.adc.prism_mode
    )


@app.post("/settings/interval")
async def set_tcs_poll_interval(request: ControlIntervalRequest):
    """Set the TCS poll interval in seconds."""
    if request.interval < 0.1:
        return {"status": "error", "message": "Interval must be at least 0.1 seconds"}
    if request.interval > 10.0:
        return {"status": "error", "message": "Interval must be at most 10 seconds"}
    runtime_settings.tcs_poll_interval = request.interval
    return {"status": "ok", "interval": request.interval}


# === Health Check ===
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "tcs_connected": state.tcs_connected,
        "plc_connected": state.plc_connected,
        "plc_online": PLC_ONLINE,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
