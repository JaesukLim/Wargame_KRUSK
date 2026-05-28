"""Unit and projectile data models."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Optional

from .types import MovementPath, Point, Side, UnitKind


_id_counter = itertools.count(1)


def reset_unit_ids() -> None:
    global _id_counter
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
    echelon: str = ""

    # Scenario phase lifecycle.
    # The older scenario/API field ``active_after_s`` remains as a compatibility
    # alias; loaders should map it into these phase gates when explicit gates
    # are not provided.
    active_after_s: float = 0.0
    present_after_s: float = 0.0
    detectable_after_s: float = 0.0
    targetable_after_s: float = 0.0
    maneuver_after_s: float = 0.0
    engage_after_s: float = 0.0
    activation_phase: str = "initial"
    activation_label: str = ""
    visible_before_activation: bool = True
    reserve_trigger_side: str = ""
    reserve_trigger_kind: str = "tank"
    reserve_trigger_loss_ratio: Optional[float] = None
    reserve_triggered: bool = False
    reserve_triggered_at_s: Optional[float] = None

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
    current_order: dict[str, Any] = field(default_factory=dict)

    def is_alive(self) -> bool:
        return self.strength > 0

    def is_present_at(self, now_s: float) -> bool:
        return self.is_alive() and now_s >= self.present_after_s

    def is_detectable_at(self, now_s: float) -> bool:
        return self.is_alive() and now_s >= self.detectable_after_s

    def can_be_damaged_at(self, now_s: float) -> bool:
        return self.is_alive() and now_s >= self.targetable_after_s

    def can_move_at(self, now_s: float) -> bool:
        return self.is_alive() and now_s >= self.maneuver_after_s

    def can_observe_at(self, now_s: float) -> bool:
        return self.is_present_at(now_s) and (self.is_tank or self.is_recon)

    def can_engage_at(self, now_s: float) -> bool:
        return self.is_alive() and now_s >= self.engage_after_s

    def lifecycle_state_at(self, now_s: float) -> str:
        if not self.is_alive():
            return "destroyed"
        if now_s < self.present_after_s:
            return "absent"
        if now_s < self.maneuver_after_s:
            return "present_hold"
        if now_s < self.engage_after_s:
            return "maneuvering"
        return "engaged"

    @property
    def normalized_strength(self) -> float:
        return max(0.0, min(1.0, self.strength / self.max_strength))

    @property
    def is_tank(self) -> bool:
        return self.kind == UnitKind.TANK

    @property
    def is_artillery(self) -> bool:
        return self.kind == UnitKind.ARTILLERY

    @property
    def is_command(self) -> bool:
        return self.kind == UnitKind.COMMAND

    @property
    def is_recon(self) -> bool:
        return self.kind == UnitKind.RECON


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
    radius_m: float = 0.0
    kind: str = "artillery"
    ballistic_travel_s: float = 0.0
    active: bool = True
    landed: bool = False

    def remaining_time(self, now: float) -> float:
        return max(0.0, self.impact_time - now)

    @property
    def is_enroute(self) -> bool:
        return self.active and not self.landed
