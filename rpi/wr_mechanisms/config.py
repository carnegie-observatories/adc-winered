"""Runtime configuration, read from environment variables with the `WR_` prefix.

Plain `os.environ` parsing rather than pydantic-settings: this package is
installed on a Raspberry Pi whose only dependencies should be `websockets` and
`gpiozero`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

GpioMode = Literal["real", "sim"]

# BCM numbering — "D26" in the wiring notes is GPIO26.
DEFAULT_PIN_ENABLE = 26
DEFAULT_PIN_MILKY_FLAT = 13
DEFAULT_PIN_SHUTTER = 6


class ConfigError(ValueError):
    """Bad environment variable. Fatal at startup — never raised at runtime."""


@dataclass(frozen=True, slots=True)
class Settings:
    ws_host: str = "0.0.0.0"
    ws_port: int = 52403

    gpio_mode: GpioMode = "real"

    pin_enable: int = DEFAULT_PIN_ENABLE
    pin_shutter: int = DEFAULT_PIN_SHUTTER
    pin_milky_flat: int = DEFAULT_PIN_MILKY_FLAT

    # Relay-board polarity: does driving the GPIO *high* energize the relay?
    # False on the wr-pi board, measured on the bench — driving D26 high left
    # the 12 V enable off. Opto-isolated relay boards are active-low as a rule;
    # a bare transistor driver would be active-high. Getting this wrong inverts
    # everything, silently.
    active_high: bool = False

    # Whether the enable relay has to be energized to pass 12 V. True for a
    # normally-open contact, false for normally-closed — with NC the load is
    # live whenever the coil is off, including while this service is stopped.
    enable_energized: bool = True

    # Mechanical polarity: which position the mechanism sits in while its relay
    # is energized. The other position is what the mechanism holds while the
    # coil is off — and, as long as the enable relay is normally-open, also
    # what the bench falls back to when this service stops.
    #
    # Both relays run on their normally-closed contacts, so energizing the coil
    # *removes* 12 V: the shutter closes and the diffuser drops into the beam.
    # Flip these two if the contacts ever go back to normally-open.
    shutter_energized_pos: str = "closed"
    milky_flat_energized_pos: str = "in"

    log_level: str = field(default="INFO")


def load(env: dict[str, str] | None = None) -> Settings:
    e = os.environ if env is None else env
    return Settings(
        ws_host=e.get("WR_WS_HOST", "0.0.0.0"),
        ws_port=_int(e, "WR_WS_PORT", 52403),
        gpio_mode=_choice(e, "WR_GPIO_MODE", "real", ("real", "sim")),  # type: ignore[arg-type]
        pin_enable=_int(e, "WR_PIN_ENABLE", DEFAULT_PIN_ENABLE),
        pin_shutter=_int(e, "WR_PIN_SHUTTER", DEFAULT_PIN_SHUTTER),
        pin_milky_flat=_int(e, "WR_PIN_MILKY_FLAT", DEFAULT_PIN_MILKY_FLAT),
        active_high=_bool(e, "WR_ACTIVE_HIGH", False),
        enable_energized=_bool(e, "WR_ENABLE_ENERGIZED", True),
        shutter_energized_pos=_choice(
            e, "WR_SHUTTER_ENERGIZED_POS", "closed", ("open", "closed")
        ),
        milky_flat_energized_pos=_choice(
            e, "WR_MILKY_FLAT_ENERGIZED_POS", "in", ("in", "out")
        ),
        log_level=e.get("WR_LOG_LEVEL", "INFO").upper(),
    )


def _int(e: dict[str, str] | os._Environ[str], key: str, default: int) -> int:
    raw = e.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from exc


def _bool(e: dict[str, str] | os._Environ[str], key: str, default: bool) -> bool:
    raw = e.get(key)
    if raw is None or raw == "":
        return default
    lowered = raw.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{key} must be a boolean, got {raw!r}")


def _choice(
    e: dict[str, str] | os._Environ[str], key: str, default: str, allowed: tuple[str, ...]
) -> str:
    raw = e.get(key)
    if raw is None or raw == "":
        return default
    value = raw.strip().lower()
    if value not in allowed:
        raise ConfigError(f"{key} must be one of {list(allowed)}, got {raw!r}")
    return value
