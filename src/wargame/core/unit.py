"""Unit and projectile data models."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from .types import MovementPath, Point, Side, UnitKind


_id_counter = itertools.count(1)


def _new_id() -> str:
    return f"U{next(_id_counter):04d}"


@dataclass
class Unit:
    name: str
    side: Side
    kind: UnitKind
    unit_type: str
    position: Point
    strength: float
    max_strength: float
    speed_mps: float
    detection_range_m: float
    command_range_m: float
    lanchester_range_m: float = 0.0
    lanchester_kills: float = 0.0
    armor: float = 1.0
    morale: float = 1.0
    movement_path: MovementPath = field(default_factory=MovementPath)
    color: str = "#ffffff"

    # Tank role specific
    fire_range_m: Optional[float] = None
    id: str = field(default_factory=_new_id)

    # Artillery role specific
    fire_rate_per_min: Optional[float] = None
    shell_damage: Optional[float] = None
    shell_range_m: Optional[float] = None
    shell_speed_mps: Optional[float] = None
    shell_dispersion_m: Optional[float] = None
    ammo_remaining: Optional[int] = None

    # Runtime state
    reload_timer: float = 0.0
    waypoint_eps_m: float = 10.0
    last_fired_at: float = -1_000_000.0

    def is_alive(self) -> bool:
        return self.strength > 0

    @property
    def normalized_strength(self) -> float:
        return max(0.0, min(1.0, self.strength / self.max_strength))

    @property
    def is_tank(self) -> bool:
        return self.kind == UnitKind.TANK

    @property
    def is_artillery(self) -> bool:
        return self.kind == UnitKind.ARTILLERY


@dataclass
class ShellImpact:
    shell_id: str
    launcher_id: str
    target_id: str
    start_pos: Point
    target_pos: Point
    damage: float
    launch_time: float
    impact_time: float
    accuracy: float
    active: bool = True
    landed: bool = False

    @property
    def remaining_time(self, now: float) -> float:
        return max(0.0, self.impact_time - now)

    @property
    def is_enroute(self) -> bool:
        return self.active and not self.landed
