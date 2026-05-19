"""Core type definitions used across the simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Side(str, Enum):
    RED = "red"
    BLUE = "blue"

    @property
    def opponent(self) -> "Side":
        return Side.BLUE if self is Side.RED else Side.RED


class UnitKind(str, Enum):
    TANK = "tank"
    ARTILLERY = "artillery"
    COMMAND = "command"
    RECON = "recon"


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class MovementPath:
    waypoints: List[Point] = field(default_factory=list)
    loop: bool = False
    _index: int = 0

    def current_target(self) -> Optional[Point]:
        if not self.waypoints:
            return None
        if self._index >= len(self.waypoints):
            return None
        return self.waypoints[self._index]

    def advance(self) -> None:
        if not self.waypoints:
            return
        self._index += 1
        if self._index >= len(self.waypoints):
            self._index = len(self.waypoints) - 1
            if self.loop:
                self._index = 0

    def reached(self, distance: float) -> bool:
        if not self.waypoints:
            return True
        return distance <= 1e-3


@dataclass
class UnitTemplate:
    unit_type: str
    speed_mps: float
    detection_range_m: float
    command_range_m: float
    lanchester_fire_range_m: float = 0.0
    lanchester_kill_rate_self: float = 0.0
    lanchester_kill_rate_target: float = 0.0
    ammo_limit: Optional[int] = None
    fire_rate_per_min: Optional[float] = None
    shell_damage: Optional[float] = None
    shell_range_m: Optional[float] = None
    shell_speed_mps: Optional[float] = None
    shell_dispersion_m: Optional[float] = None
    color: str = "#ffffff"
