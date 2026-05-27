"""Runtime configuration. Pulled from environment variables with the `ADC_` prefix.

Example:

    ADC_PLC_MODE=real ADC_PLC_AMS_NET_ID=10.8.104.50.1.1 \
    ADC_TCS_MODE=real ADC_TCS_HOST=mag2tcs \
    uv run adc-winered serve
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Mode = Literal["real", "sim"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADC_", env_file=".env", extra="ignore")

    # Backend selection.
    plc_mode: Mode = "sim"
    tcs_mode: Mode = "sim"

    # Real-PLC connection.
    plc_ams_net_id: str = ""
    plc_ams_port: int = 851
    plc_ip: str = ""

    # Real-TCS connection.
    tcs_host: str = "127.0.0.1"
    tcs_port: int = 5800

    # External API.
    ws_host: str = "0.0.0.0"
    ws_port: int = 52403

    # Tracking-loop tuning.
    control_interval_s: float = Field(default=30.0, gt=0.0)
    deadband_deg: float = Field(default=0.7, gt=0.0)

    # Simulator tuning (only used when *_mode == "sim").
    rotator_velocity_deg_s: float = Field(default=30.0, gt=0.0)
    slide_settle_s: float = Field(default=0.5, gt=0.0)
    tcs_sim_drift: bool = False
