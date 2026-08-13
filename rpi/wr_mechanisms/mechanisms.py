"""Mechanism positions on top of the relays.

Neither mechanism has a position sensor, so a position is only ever the last
thing commanded — exactly as on the PLC-backed server, where `mechanisms_topic`
echoes the commanded state back.

The relay-to-position mapping is configuration, not a constant: whether
energizing the shutter opens or closes it depends on how the actuator is wired,
and getting it wrong would be silent. `Settings.shutter_energized_pos` and
`Settings.milky_flat_energized_pos` name the position each mechanism holds while
its relay is energized; the other value is therefore the powered-down state.
"""

from __future__ import annotations

from typing import Any

from .config import Settings
from .gpio import MILKY_FLAT, SHUTTER, Relays

SHUTTER_POSITIONS = ("open", "closed")
MILKY_FLAT_POSITIONS = ("in", "out")


class Mechanisms:
    def __init__(self, relays: Relays, settings: Settings) -> None:
        self._relays = relays
        self._energized_pos = {
            SHUTTER: settings.shutter_energized_pos,
            MILKY_FLAT: settings.milky_flat_energized_pos,
        }
        self._positions = {
            SHUTTER: SHUTTER_POSITIONS,
            MILKY_FLAT: MILKY_FLAT_POSITIONS,
        }

    def start(self) -> None:
        self._relays.start()

    def close(self) -> None:
        self._relays.close()

    # --- commands --------------------------------------------------------

    def set_shutter(self, pos: str) -> None:
        self._set(SHUTTER, pos)

    def set_milky_flat(self, pos: str) -> None:
        self._set(MILKY_FLAT, pos)

    def _set(self, name: str, pos: str) -> None:
        if pos not in self._positions[name]:
            raise ValueError(f"{name} position must be one of {list(self._positions[name])}")
        self._relays.set(name, pos == self._energized_pos[name])

    # --- state -----------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """The `mechanisms` topic payload — same shape as the PLC server's."""
        return {
            "shutter": self._position(SHUTTER),
            "milky_flat": self._position(MILKY_FLAT),
        }

    def _position(self, name: str) -> str:
        energized = self._energized_pos[name]
        if self._relays.is_energized(name):
            return energized
        return next(p for p in self._positions[name] if p != energized)
