"""Relay outputs.

Three relays on the Pi's header (BCM numbering):

| Pin  | Load                                                    |
|------|---------------------------------------------------------|
| D26  | Enable — feeds 12 V to both mechanisms. Always on.       |
| D13  | Milky-flat diffuser                                      |
| D6   | Shutter                                                  |

`Relays` is the interface; `GpiozeroRelays` drives real hardware and
`SimRelays` keeps the same bookkeeping in memory so the server can be
exercised on a laptop and in tests.

Everything here talks in terms of *energized* / not, never in terms of
mechanism positions — the mechanical mapping lives in `mechanisms.py`.
"""

from __future__ import annotations

import abc
import logging

from .config import Settings

log = logging.getLogger(__name__)

ENABLE = "enable"
SHUTTER = "shutter"
MILKY_FLAT = "milky_flat"


class RelayError(RuntimeError):
    """The GPIO layer refused a write, or could not be brought up at all."""


class Relays(abc.ABC):
    """Three named relays, plus the enable line that powers the other two."""

    def __init__(self, settings: Settings) -> None:
        self._pins = {
            ENABLE: settings.pin_enable,
            SHUTTER: settings.pin_shutter,
            MILKY_FLAT: settings.pin_milky_flat,
        }
        self._active_high = settings.active_high
        self._energized = {name: False for name in self._pins}

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        """Claim the pins and raise the enable line.

        Enable is asserted here and stays asserted for the life of the
        process. Both mechanisms are left de-energized, which is the state the
        hardware was already resting in.
        """
        self._open()
        self.set(ENABLE, True)
        log.info(
            "relays up: enable=D%d shutter=D%d milky_flat=D%d (%s relay board)",
            self._pins[ENABLE], self._pins[SHUTTER], self._pins[MILKY_FLAT],
            "active-high" if self._active_high else "active-low",
        )

    def close(self) -> None:
        """De-energize everything, enable last, and release the pins.

        Dropping enable cuts 12 V to both mechanisms, so they revert to their
        unpowered rest positions. That is deliberate: a stopped service should
        leave the bench in a known state rather than a latched one.
        """
        for name in (SHUTTER, MILKY_FLAT, ENABLE):
            try:
                self.set(name, False)
            except RelayError:
                log.exception("failed to de-energize %s during shutdown", name)
        self._release()

    # --- state -----------------------------------------------------------

    def set(self, name: str, energized: bool) -> None:
        self._write(self._pins[name], energized)
        self._energized[name] = energized

    def is_energized(self, name: str) -> bool:
        return self._energized[name]

    # --- backend hooks ---------------------------------------------------

    @abc.abstractmethod
    def _open(self) -> None: ...

    @abc.abstractmethod
    def _write(self, pin: int, energized: bool) -> None: ...

    @abc.abstractmethod
    def _release(self) -> None: ...


class GpiozeroRelays(Relays):
    """Real hardware, via gpiozero's default pin factory (lgpio on Pi OS)."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._devices: dict[int, object] = {}

    def _open(self) -> None:
        try:
            from gpiozero import DigitalOutputDevice
        except ImportError as exc:  # pragma: no cover - depends on the host
            raise RelayError(
                "gpiozero is not installed; install it or run with WR_GPIO_MODE=sim"
            ) from exc
        try:
            for pin in self._pins.values():
                # active_high folds the board polarity in, so `.value = True`
                # means "energized" everywhere above this line.
                self._devices[pin] = DigitalOutputDevice(
                    pin, active_high=self._active_high, initial_value=False
                )
        except Exception as exc:  # pragma: no cover - depends on the host
            self._release()
            raise RelayError(f"could not claim GPIO pins: {exc}") from exc

    def _write(self, pin: int, energized: bool) -> None:
        device = self._devices.get(pin)
        if device is None:  # pragma: no cover - only if start() was skipped
            raise RelayError(f"pin {pin} is not open")
        try:
            device.value = 1 if energized else 0  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - depends on the host
            raise RelayError(f"write to pin {pin} failed: {exc}") from exc

    def _release(self) -> None:
        for device in self._devices.values():
            try:
                device.close()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - depends on the host
                log.exception("failed to close a GPIO device")
        self._devices.clear()


class SimRelays(Relays):
    """In-memory relays. Same bookkeeping, no hardware."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.writes: list[tuple[int, bool]] = []

    def _open(self) -> None:
        log.warning("GPIO simulation mode — no pins are being driven")

    def _write(self, pin: int, energized: bool) -> None:
        self.writes.append((pin, energized))

    def _release(self) -> None:
        pass


def make_relays(settings: Settings) -> Relays:
    if settings.gpio_mode == "sim":
        return SimRelays(settings)
    return GpiozeroRelays(settings)
