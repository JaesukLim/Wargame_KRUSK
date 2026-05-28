"""Battlefield simulation core."""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .config_loader import SimulationConfig
from .detection import DetectionRecord, detect_unit_targets
from .lanchester import square_step_with_report
from .terrain import TerrainGrid
from .types import Point, Side, UnitKind
from .unit import ShellImpact, Unit


@dataclass
class EngagementPair:
    attacker_id: str
    defender_id: str
    started_at: float
    last_deltas: Tuple[float, float] = (0.0, 0.0)
    last_k: Tuple[float, float] = (0.0, 0.0)
    last_range_m: float = 0.0
    terrain_factors: Tuple[float, float] = (1.0, 1.0)

@dataclass
class PendingFireOrder:
    arrival_time: float
    artillery_id: str
    target_id: str
    target_name: str
    target_pos: Point
    detector_id: str
    detector_name: str
    hq_id: str | None
    hq_name: str | None
    confidence: float
    reported_distance_m: float
    line_of_sight: bool
    terrain_factor: float
    altitude_factor: float
    range_factor: float
    fire_event_bonus: float
    assigned_from_detection_time: float
    detector_cell: tuple[int, int] | None = None
    target_cell: tuple[int, int] | None = None
    detector_cell_center: tuple[float, float] | None = None
    target_cell_center: tuple[float, float] | None = None
    grid_cell_size_m: float = 0.0
    grid_distance_cells: float = 0.0
    grid_metric: str = "chebyshev"

@dataclass
class SimulationResult:
    time_s: float
    active_units: int
    red_strength: float
    blue_strength: float
    active_contacts: int
    ended: bool = False
    winner: str | None = None
    end_reason: str | None = None
    red_tanks: int = 0
    blue_tanks: int = 0
    expected_duration_s: float = 3600.0


@dataclass
class BattleEvent:
    time_s: float
    category: str
    message: str
    unit_id: str | None = None
    target_id: str | None = None
    side: Side | None = None
    data: Dict[str, Any] | None = None


class BattleField:
    def __init__(self, terrain: TerrainGrid, config: SimulationConfig):
        self.terrain = terrain
        self.config = config
        self.runtime_parameters: Dict[str, float] = {
            "direct_fire_scale": 1.0,
            "combat_speed_scale": 0.60,
            "artillery_delay_s": 240.0,
            "artillery_damage_scale": 1.0,
            "target_area_scale": 1.0,
            "red_force_end_ratio": 0.50,
            "blue_tank_end_count": 0.0,
            "unit_removal_ratio": 0.20,
        }
        self._initial_strength_by_side: Dict[Side, float] = {Side.RED: 0.0, Side.BLUE: 0.0}
        self._initial_nonreserve_strength_by_side_kind: Dict[Tuple[Side, UnitKind], float] = {}
        self.runtime_lanchester_matrix: Dict[str, Dict[str, float]] = self._base_lanchester_matrix()
        self.units: Dict[str, Unit] = {}
        self.shells: Dict[str, ShellImpact] = {}
        self.contacts: Dict[Tuple[str, str], EngagementPair] = {}
        self.event_log: List[BattleEvent] = []
        self.replay_frames: List[Dict[str, Any]] = []
        self.contact_history: Dict[Tuple[str, str], List[Tuple[float, float, float]]] = {}
        self.fire_missions: Dict[str, Dict[str, Any]] = {}
        self.pending_fire_orders: List[PendingFireOrder] = []
        self.last_detections: Dict[Tuple[str, str], DetectionRecord] = {}
        self._logged_detections: Dict[Tuple[str, str], float] = {}
        self._logged_relays: Dict[Tuple[str, str, str], float] = {}
        self._reserve_activated_ids: set[str] = set()
        self._last_replay_sample_s = -1.0
        self.time_s = 0.0
        seed = int(self.config.get("simulation", "random_seed", default=19430712))
        self.rng = random.Random(seed)

    def set_runtime_parameters(self, parameters: Dict[str, float]) -> None:
        """Apply runtime-tunable model parameters.

        These values intentionally sit above the scenario/config files so the
        Godot operator UI can tune a running localhost simulation without
        mutating source assets.
        """

        self.runtime_parameters.update(
            {
                "direct_fire_scale": float(parameters.get("direct_fire_scale", self.runtime_parameters["direct_fire_scale"])),
                "combat_speed_scale": float(parameters.get("combat_speed_scale", self.runtime_parameters["combat_speed_scale"])),
                "artillery_delay_s": float(parameters.get("artillery_delay_s", self.runtime_parameters["artillery_delay_s"])),
                "artillery_damage_scale": float(parameters.get("artillery_damage_scale", self.runtime_parameters["artillery_damage_scale"])),
                "target_area_scale": float(parameters.get("target_area_scale", self.runtime_parameters["target_area_scale"])),
                "red_force_end_ratio": float(parameters.get("red_force_end_ratio", self.runtime_parameters["red_force_end_ratio"])),
                "blue_tank_end_count": float(parameters.get("blue_tank_end_count", self.runtime_parameters["blue_tank_end_count"])),
                "unit_removal_ratio": float(parameters.get("unit_removal_ratio", self.runtime_parameters["unit_removal_ratio"])),
            }
        )
        self.log_event("parameters", "Runtime model parameters updated", data=dict(self.runtime_parameters))

    def _base_lanchester_matrix(self) -> Dict[str, Dict[str, float]]:
        matrix = self.config.get("simulation", "lanchester", "kill_matrix", default={})
        return {
            str(attacker): {str(target): float(value) for target, value in targets.items()}
            for attacker, targets in matrix.items()
            if isinstance(targets, dict)
        }

    def set_lanchester_matrix(self, patch: Dict[str, Dict[str, float]], *, replace: bool = False) -> None:
        """Update the runtime Lanchester kill-rate matrix.

        The scenario/config matrix remains immutable on disk. This runtime
        surface lets the operator tune individual attacker-vs-defender
        coefficients instead of one global alpha slider.
        """

        matrix = self._base_lanchester_matrix() if replace else {
            attacker: dict(targets) for attacker, targets in self.runtime_lanchester_matrix.items()
        }
        for attacker, targets in patch.items():
            if not isinstance(targets, dict):
                continue
            attacker_key = str(attacker)
            row = matrix.setdefault(attacker_key, {})
            for target, value in targets.items():
                target_key = str(target)
                attacker_side = self._unit_type_side(attacker_key)
                target_side = self._unit_type_side(target_key)
                if attacker_side is not None and attacker_side == target_side:
                    continue
                next_value = max(0.0, float(value))
                row[target_key] = next_value
        self.runtime_lanchester_matrix = matrix
        self.log_event("parameters", "Lanchester matrix updated", data={"entries": sum(len(v) for v in patch.values())})

    def lanchester_matrix_payload(self) -> Dict[str, Any]:
        base = self._base_lanchester_matrix()
        unit_types = sorted(set(base.keys()) | {target for row in base.values() for target in row.keys()})
        red_types = sorted({u.unit_type for u in self.units.values() if u.side == Side.RED and u.kind == UnitKind.TANK})
        blue_types = sorted({u.unit_type for u in self.units.values() if u.side == Side.BLUE and u.kind == UnitKind.TANK})
        for unit_type in unit_types:
            if unit_type.startswith(("T-", "SU-", "IS-")):
                red_types.append(unit_type)
            elif unit_type.startswith(("Pz", "Panther", "Tiger")):
                blue_types.append(unit_type)
        red_types = sorted(set(red_types))
        blue_types = sorted(set(blue_types))
        unit_type_sides = {
            unit_type: side.value
            for unit_type in unit_types
            if (side := self._unit_type_side(unit_type)) is not None
        }
        return {
            "unit_types": unit_types,
            "red_unit_types": red_types,
            "blue_unit_types": blue_types,
            "unit_type_sides": unit_type_sides,
            "symmetric": False,
            "matrix": self.runtime_lanchester_matrix,
            "base_matrix": base,
            "schema": {"min": 0.0, "max": 0.02, "step": 0.0001, "label": "Lanchester kill-rate k"},
        }

    def _unit_type_side(self, unit_type: str) -> Optional[Side]:
        for unit in self.units.values():
            if unit.unit_type == unit_type and unit.kind == UnitKind.TANK:
                return unit.side
        if unit_type.startswith(("T-", "SU-", "IS-")):
            return Side.RED
        if unit_type.startswith(("Pz", "Panther", "Tiger")):
            return Side.BLUE
        return None

    # -----------------------------
    # lifecycle
    # -----------------------------
    def add_unit(self, unit: Unit) -> None:
        self.units[unit.id] = unit
        self._initial_strength_by_side[unit.side] = self._initial_strength_by_side.get(unit.side, 0.0) + max(unit.max_strength, unit.strength, 0.0)
        if unit.reserve_trigger_loss_ratio is None:
            key = (unit.side, unit.kind)
            self._initial_nonreserve_strength_by_side_kind[key] = self._initial_nonreserve_strength_by_side_kind.get(key, 0.0) + max(unit.max_strength, unit.strength, 0.0)
        if unit.reserve_triggered:
            self._reserve_activated_ids.add(unit.id)
        self.log_event(
            "unit_added",
            f"{unit.name} added to battlefield",
            unit_id=unit.id,
            side=unit.side,
            data={"kind": unit.kind.value, "type": unit.unit_type, "x": unit.position.x, "y": unit.position.y},
        )
        if unit.is_command:
            self.log_event("command_post", f"{unit.name} command post established in rear area", unit_id=unit.id, side=unit.side)

    def seed_units(self, units: List[Unit]) -> None:
        for unit in units:
            self.add_unit(unit)

    def replace_units(self, units: List[Unit]) -> None:
        self.units = {unit.id: unit for unit in units}
        self._initial_strength_by_side = {Side.RED: 0.0, Side.BLUE: 0.0}
        self._initial_nonreserve_strength_by_side_kind = {}
        self._reserve_activated_ids = {unit.id for unit in units if unit.reserve_triggered}
        for unit in units:
            self._initial_strength_by_side[unit.side] = self._initial_strength_by_side.get(unit.side, 0.0) + max(unit.max_strength, unit.strength, 0.0)
            if unit.reserve_trigger_loss_ratio is None:
                key = (unit.side, unit.kind)
                self._initial_nonreserve_strength_by_side_kind[key] = self._initial_nonreserve_strength_by_side_kind.get(key, 0.0) + max(unit.max_strength, unit.strength, 0.0)
        self.shells.clear()
        self.contacts.clear()
        self.contact_history.clear()
        self.fire_missions.clear()
        self.pending_fire_orders.clear()
        self._logged_detections.clear()
        self._logged_relays.clear()
        self.log_event("load", f"Runtime unit set replaced: {len(units)} units")

    def remove_unit(self, unit_id: str, *, reason: str = "operator") -> bool:
        unit = self.units.pop(unit_id, None)
        if unit is None:
            return False
        self.shells = {k: s for k, s in self.shells.items() if s.launcher_id != unit_id and s.target_id != unit_id}
        self.contacts = {k: c for k, c in self.contacts.items() if unit_id not in k}
        self.contact_history = {k: h for k, h in self.contact_history.items() if unit_id not in k}
        self.fire_missions = {
            artillery_id: mission
            for artillery_id, mission in self.fire_missions.items()
            if artillery_id != unit_id
            and mission.get("target_id") != unit_id
            and mission.get("detector_id") != unit_id
            and mission.get("hq_id") != unit_id
        }
        self._logged_detections = {k: t for k, t in self._logged_detections.items() if unit_id not in k}
        self._logged_relays = {k: t for k, t in self._logged_relays.items() if unit_id not in k}
        self.log_event("unit_removed", f"{unit.name} removed from battlefield", unit_id=unit.id, side=unit.side, data={"reason": reason})
        return True

    def remove_destroyed(self) -> None:
        removal_ratio = max(0.0, min(1.0, float(self.runtime_parameters.get("unit_removal_ratio", 0.20))))
        for uid in list(self.units.keys()):
            unit = self.units[uid]
            if not unit.is_alive() or unit.normalized_strength <= removal_ratio:
                reason = "destroyed" if not unit.is_alive() else "combat_ineffective"
                self.log_event(
                    reason,
                    f"{unit.name} removed from battle at {unit.normalized_strength:.0%} strength",
                    unit_id=uid,
                    side=unit.side,
                    data={"remaining_ratio": unit.normalized_strength, "threshold": removal_ratio},
                )
                self.remove_unit(uid, reason=reason)

    def alive_units(self) -> List[Unit]:
        return [u for u in self.units.values() if u.is_alive()]

    def alive_tanks_by_side(self, side: Side) -> List[Unit]:
        return [u for u in self.units.values() if u.is_alive() and u.kind == UnitKind.TANK and u.side == side]

    def terminal_status(self) -> Dict[str, Any]:
        red_tanks = len(self.alive_tanks_by_side(Side.RED))
        blue_tanks = len(self.alive_tanks_by_side(Side.BLUE))
        red_strength = sum(u.strength for u in self.units.values() if u.side == Side.RED)
        initial_red = max(self._initial_strength_by_side.get(Side.RED, 0.0), red_strength, 1.0)
        red_end_ratio = max(0.0, min(1.0, float(self.runtime_parameters.get("red_force_end_ratio", 0.50))))
        red_end_threshold = initial_red * red_end_ratio
        blue_tank_end_count = max(0, int(round(float(self.runtime_parameters.get("blue_tank_end_count", 0.0)))))
        base = {
            "red_tanks": red_tanks,
            "blue_tanks": blue_tanks,
            "red_strength": red_strength,
            "red_initial_strength": initial_red,
            "red_force_end_threshold": red_end_threshold,
            "blue_tank_end_count": blue_tank_end_count,
        }
        if red_strength <= red_end_threshold:
            return {**base, "ended": True, "winner": "blue", "reason": "red_force_threshold"}
        if blue_tanks <= blue_tank_end_count:
            return {**base, "ended": True, "winner": "red", "reason": "blue_tanks_destroyed"}
        return {**base, "ended": False, "winner": None, "reason": None}

    def is_terminal(self) -> bool:
        return bool(self.terminal_status()["ended"])

    # -----------------------------
    # high-level update
    # -----------------------------
    def update(self, dt: float) -> SimulationResult:
        self.time_s += dt

        self._activate_conditional_reserves()
        self._move_units(dt)
        detections = self._resolve_detection()
        self._resolve_contacts(detections, dt)
        self._resolve_artillery(detections, dt)
        self._resolve_shell_impacts()
        self._prune_old_shell_visuals()

        self.remove_destroyed()
        self._sample_replay()
        return self.snapshot()

    def _shell_visual_window_s(self) -> float:
        return max(
            30.0,
            float(self.config.get("simulation", "timeline", "frame_interval_s", default=0.0) or 0.0),
        )

    def _prune_old_shell_visuals(self) -> None:
        visual_window_s = self._shell_visual_window_s()
        self.shells = {
            sid: shell
            for sid, shell in self.shells.items()
            if shell.is_enroute or not shell.landed or self.time_s - shell.impact_time <= visual_window_s
        }

    def _activate_conditional_reserves(self) -> None:
        for unit in self.units.values():
            trigger_ratio = unit.reserve_trigger_loss_ratio
            if trigger_ratio is None or unit.reserve_triggered:
                continue
            side = self._side_from_string(unit.reserve_trigger_side) or unit.side
            kind = self._kind_from_string(unit.reserve_trigger_kind) or unit.kind
            loss_ratio = self._nonreserve_loss_ratio(side, kind)
            if loss_ratio + 1e-9 < max(0.0, min(1.0, trigger_ratio)):
                continue

            unit.reserve_triggered = True
            unit.reserve_triggered_at_s = self.time_s
            self._reserve_activated_ids.add(unit.id)
            unit.active_after_s = min(unit.active_after_s, self.time_s)
            unit.present_after_s = min(unit.present_after_s, self.time_s)
            unit.detectable_after_s = min(unit.detectable_after_s, self.time_s)
            unit.targetable_after_s = min(unit.targetable_after_s, self.time_s)
            unit.maneuver_after_s = min(unit.maneuver_after_s, self.time_s)
            unit.engage_after_s = min(unit.engage_after_s, self.time_s)
            self.log_event(
                "reserve_activated",
                f"{unit.name} reserve released after {side.value} {kind.value} losses reached {loss_ratio:.0%}",
                unit_id=unit.id,
                side=unit.side,
                data={
                    "trigger_side": side.value,
                    "trigger_kind": kind.value,
                    "loss_ratio": loss_ratio,
                    "threshold": trigger_ratio,
                },
            )

    def _side_from_string(self, value: str) -> Side | None:
        value = value.lower().strip()
        if value == Side.RED.value:
            return Side.RED
        if value == Side.BLUE.value:
            return Side.BLUE
        return None

    def _kind_from_string(self, value: str) -> UnitKind | None:
        value = value.lower().strip()
        for kind in UnitKind:
            if value == kind.value:
                return kind
        if value == "command_post":
            return UnitKind.COMMAND
        return None

    def _nonreserve_loss_ratio(self, side: Side, kind: UnitKind) -> float:
        initial = self._initial_nonreserve_strength_by_side_kind.get((side, kind), 0.0)
        if initial <= 0.0:
            return 0.0
        current = sum(
            unit.strength
            for unit in self.units.values()
            if unit.side == side
            and unit.kind == kind
            and unit.reserve_trigger_loss_ratio is None
            and unit.is_alive()
        )
        return max(0.0, min(1.0, (initial - current) / initial))

    # -----------------------------
    # movement
    # -----------------------------
    def _move_units(self, dt: float) -> None:
        engaged_unit_ids = self._engaged_unit_ids()
        gate_time = max(0.0, self.time_s - dt)
        for unit in self.units.values():
            if not unit.can_move_at(gate_time):
                continue
            if unit.id in engaged_unit_ids:
                # Units that have made direct-fire contact hold position until
                # contact breaks.  Their waypoint stack is preserved so the
                # route can resume naturally after the engagement ends.
                continue
            path = unit.movement_path
            if not path.waypoints:
                continue

            target = path.current_target()
            if target is None:
                continue

            dx = target.x - unit.position.x
            dy = target.y - unit.position.y
            remaining = (dx**2 + dy**2) ** 0.5
            if remaining <= unit.waypoint_eps_m:
                path.advance()
                continue

            cost = self.terrain.movement_cost(unit.position, "vehicle")
            if math.isinf(cost):
                continue

            speed = unit.speed_mps / cost
            step = speed * dt
            nx = dx / remaining
            ny = dy / remaining
            new_x = unit.position.x + nx * step
            new_y = unit.position.y + ny * step
            if (new_x - target.x) ** 2 + (new_y - target.y) ** 2 > remaining**2:
                new_x = target.x
                new_y = target.y
            unit.position = Point(new_x, new_y)

    def _engaged_unit_ids(self) -> set[str]:
        engaged: set[str] = set()
        for contact in self.contacts.values():
            engaged.add(contact.attacker_id)
            engaged.add(contact.defender_id)
        return engaged

    # -----------------------------
    # detection + fire contacts
    # -----------------------------
    def _resolve_detection(self) -> Dict[tuple[str, str], DetectionRecord]:
        detections = detect_unit_targets(
            units=self.alive_units(),
            terrain=self.terrain,
            detection_config=self.config.get("simulation", "detection", default={}),
            now_s=self.time_s,
            rng=self.rng,
        )
        self._log_detections(detections)
        self.last_detections = detections
        return detections

    def _resolve_contacts(self, detections: Dict[tuple[str, str], DetectionRecord], dt: float) -> None:
        default_contact_distance = float(self.config.get("simulation", "combat", "lanchester_range_m", default=1800.0))
        matrix = self.runtime_lanchester_matrix

        # build side-specific unit lookup for faster pair iteration
        ids = list(self.units.keys())
        alive = self.units

        active_pairs = set()
        for i, u_id in enumerate(ids):
            u = alive[u_id]
            if not u.is_alive() or not u.can_be_damaged_at(self.time_s):
                continue

            for v_id in ids[i + 1 :]:
                v = alive[v_id]
                if not v.is_alive() or not v.can_be_damaged_at(self.time_s):
                    continue
                if u.side == v.side:
                    continue
                if not self._can_form_direct_fire_pair(u, v):
                    continue

                d = self._dist(u.position, v.position)
                contact_distance = min(
                    u.lanchester_range_m or default_contact_distance,
                    v.lanchester_range_m or default_contact_distance,
                    default_contact_distance,
                )
                if d > contact_distance:
                    continue

                # Must have mutual detection of either side, or artillery-style fog of war can hide it
                seen_uv = detections.get((u_id, v_id)) is not None or detections.get((v_id, u_id)) is not None
                if not seen_uv:
                    continue

                key = tuple(sorted((u_id, v_id)))
                active_pairs.add(key)

                k_uv, k_vu = self._direct_fire_coefficients(u, v, matrix)

                terrain_u = self._terrain_damping_at_position(u.position)
                terrain_v = self._terrain_damping_at_position(v.position)
                range_factor = max(0.25, 1.0 - d / max(contact_distance * 1.5, 1.0))

                direct_fire_scale = self.runtime_parameters["direct_fire_scale"]
                combat_speed_scale = self.runtime_parameters["combat_speed_scale"]
                effective_fire_scale = direct_fire_scale * combat_speed_scale
                report = square_step_with_report(
                    a_strength=u.strength,
                    b_strength=v.strength,
                    dt=dt,
                    k_ab=k_uv * range_factor * effective_fire_scale,
                    k_ba=k_vu * range_factor * effective_fire_scale,
                    terrain_factor_a=terrain_u,
                    terrain_factor_b=terrain_v,
                    fatigue_a=u.morale,
                    fatigue_b=v.morale,
                )

                u.strength = report.attacker_new
                v.strength = report.defender_new
                u.last_fired_at = self.time_s
                v.last_fired_at = self.time_s

                # maintain/refresh contacts map
                keypair = key
                c = self.contacts.get(keypair)
                if c is None:
                    self.log_event(
                        "engagement_start",
                        f"{u.name} engaged {v.name} at {d:.0f}m",
                        unit_id=u.id,
                        target_id=v.id,
                        side=u.side,
                        data={
                            "range_m": d,
                            "k_ab": k_uv * range_factor * effective_fire_scale,
                            "k_ba": k_vu * range_factor * effective_fire_scale,
                            "direct_fire_scale": direct_fire_scale,
                            "combat_speed_scale": combat_speed_scale,
                        },
                    )
                    self.contacts[keypair] = EngagementPair(
                        attacker_id=u_id,
                        defender_id=v_id,
                        started_at=self.time_s,
                        last_deltas=(report.kill_a, report.kill_b),
                        last_k=(k_uv * range_factor * effective_fire_scale, k_vu * range_factor * effective_fire_scale),
                        last_range_m=d,
                        terrain_factors=(terrain_u, terrain_v),
                    )
                else:
                    c.last_deltas = (report.kill_a, report.kill_b)
                    c.last_k = (k_uv * range_factor * effective_fire_scale, k_vu * range_factor * effective_fire_scale)
                    c.last_range_m = d
                    c.terrain_factors = (terrain_u, terrain_v)
                self.contact_history.setdefault(keypair, []).append((self.time_s, u.strength, v.strength))
                self.contact_history[keypair] = self.contact_history[keypair][-360:]

        # remove stale contacts
        for k in list(self.contacts.keys()):
            if tuple(sorted(k)) not in active_pairs:
                c = self.contacts[k]
                a = self.units.get(c.attacker_id)
                b = self.units.get(c.defender_id)
                if a and b:
                    self.log_event("engagement_end", f"{a.name} and {b.name} broke contact", unit_id=a.id, target_id=b.id, side=a.side)
                self.contacts.pop(k)

    def _can_form_direct_fire_pair(self, a: Unit, b: Unit) -> bool:
        if a.kind == UnitKind.TANK and b.kind == UnitKind.TANK:
            return a.can_engage_at(self.time_s) and b.can_engage_at(self.time_s)
        if a.kind == UnitKind.TANK and b.kind == UnitKind.ARTILLERY:
            return a.can_engage_at(self.time_s)
        if a.kind == UnitKind.ARTILLERY and b.kind == UnitKind.TANK:
            return b.can_engage_at(self.time_s)
        return False

    def _direct_fire_coefficients(
        self,
        attacker: Unit,
        defender: Unit,
        matrix: Dict[str, Dict[str, float]],
    ) -> Tuple[float, float]:
        default_attacker = float(self.config.get("simulation", "combat", "default_k_attacker", default=0.0025))
        default_defender = float(self.config.get("simulation", "combat", "default_k_defender", default=0.0025))
        k_ab = matrix.get(attacker.unit_type, {}).get(defender.unit_type)
        k_ba = matrix.get(defender.unit_type, {}).get(attacker.unit_type)

        if attacker.kind == UnitKind.TANK and defender.kind == UnitKind.TANK:
            return (
                default_attacker if k_ab is None else k_ab,
                default_defender if k_ba is None else k_ba,
            )

        if attacker.kind == UnitKind.TANK and defender.kind == UnitKind.ARTILLERY:
            return (
                default_attacker * 1.35 if k_ab is None else k_ab,
                (default_defender * 0.25 if defender.can_engage_at(self.time_s) else 0.0) if k_ba is None else k_ba,
            )

        if attacker.kind == UnitKind.ARTILLERY and defender.kind == UnitKind.TANK:
            return (
                (default_attacker * 0.25 if attacker.can_engage_at(self.time_s) else 0.0) if k_ab is None else k_ab,
                default_defender * 1.35 if k_ba is None else k_ba,
            )

        return (0.0, 0.0)

    # -----------------------------
    # artillery
    # -----------------------------
    def _resolve_artillery(self, detections: Dict[tuple[str, str], DetectionRecord], dt: float) -> None:
        artillery_units = [u for u in self.units.values() if u.is_artillery and u.can_engage_at(self.time_s)]
        tanks = [u for u in self.units.values() if u.is_tank and u.can_be_damaged_at(self.time_s)]

        if not artillery_units or not tanks:
            return

        self._assign_wta_fire_orders(artillery_units, tanks, detections)
        self._activate_due_fire_orders()

        for ar in artillery_units:
            if ar.reload_timer > 0:
                ar.reload_timer = max(0.0, ar.reload_timer - dt)
                continue
            mission = self.fire_missions.get(ar.id)
            if mission is None:
                continue
            target = self.units.get(str(mission.get("target_id", "")))
            if target is None or not target.can_be_damaged_at(self.time_s) or target.side == ar.side:
                self.fire_missions.pop(ar.id, None)
                continue
            target_pos = mission.get("target_pos")
            if not isinstance(target_pos, Point):
                target_pos = target.position
            if ar.shell_range_m is None or self._dist(ar.position, target_pos) > ar.shell_range_m:
                continue
            rec = DetectionRecord(
                detector_id=str(mission.get("detector_id", "")),
                target_id=target.id,
                confidence=float(mission.get("confidence", 0.35)),
                distance_m=float(mission.get("reported_distance_m", self._dist(ar.position, target_pos))),
                line_of_sight=bool(mission.get("line_of_sight", True)),
                terrain_factor=float(mission.get("terrain_factor", 1.0)),
                altitude_factor=float(mission.get("altitude_factor", 1.0)),
                range_factor=float(mission.get("range_factor", 1.0)),
                fire_event_bonus=float(mission.get("fire_event_bonus", 0.0)),
                detector_cell=self._tuple_int_pair(mission.get("detector_cell")),
                target_cell=self._tuple_int_pair(mission.get("target_cell")),
                detector_cell_center=self._tuple_float_pair(mission.get("detector_cell_center")),
                target_cell_center=self._tuple_float_pair(mission.get("target_cell_center")),
                grid_cell_size_m=float(mission.get("grid_cell_size_m", 0.0)),
                grid_distance_cells=float(mission.get("grid_distance_cells", 0.0)),
                grid_metric=str(mission.get("grid_metric", "chebyshev")),
            )
            self._fire_artillery(ar, target, rec, target_pos=target_pos)
            rate = ar.fire_rate_per_min or 2.0
            ar.reload_timer = max(0.0, 60.0 / rate)

    def _assign_wta_fire_orders(
        self,
        artillery_units: List[Unit],
        tanks: List[Unit],
        detections: Dict[tuple[str, str], DetectionRecord],
    ) -> None:
        """Create delayed fire orders from recon reports through command posts.

        Artillery does not receive a mission immediately after detection.
        A recon report must first travel through the command chain, represented
        here by a configurable command delay.
        """

        command_delay_s = self._command_delay_s()

        for ar in artillery_units:
            if ar.shell_range_m is None:
                continue

            # Avoid stacking multiple pending orders for the same artillery unit.
            if any(order.artillery_id == ar.id for order in self.pending_fire_orders):
                continue

            candidates: List[Tuple[float, Unit, DetectionRecord, Unit, Optional[Unit]]] = []

            for target in tanks:
                if target.side == ar.side:
                    continue

                report = self._best_commanded_detection_report(ar, target.id, detections, recon_only=True)
                if report is None:
                    continue

                rec, detector, hq = report
                target_pos = self._reported_target_point(rec, target)

                if self._dist(ar.position, target_pos) > ar.shell_range_m:
                    continue

                target_value = target.strength / max(target.max_strength, 1.0)
                score = rec.confidence * (0.65 + target_value) / max(self._dist(ar.position, target_pos), 1.0)
                candidates.append((score, target, rec, detector, hq))

            if not candidates:
                continue

            _, target, rec, detector, hq = max(candidates, key=lambda item: item[0])

            current = self.fire_missions.get(ar.id)
            if current and current.get("target_id") == target.id and self.time_s - float(current.get("assigned_at", 0.0)) < 45.0:
                continue

            arrival_time = self.time_s + command_delay_s

            self.pending_fire_orders.append(
                PendingFireOrder(
                    arrival_time=arrival_time,
                    artillery_id=ar.id,
                    target_id=target.id,
                    target_name=target.name,
                    target_pos=self._reported_target_point(rec, target),
                    detector_id=detector.id,
                    detector_name=detector.name,
                    hq_id=hq.id if hq is not None else None,
                    hq_name=hq.name if hq is not None else None,
                    confidence=rec.confidence,
                    reported_distance_m=rec.distance_m,
                    line_of_sight=rec.line_of_sight,
                    terrain_factor=rec.terrain_factor,
                    altitude_factor=rec.altitude_factor,
                    range_factor=rec.range_factor,
                    fire_event_bonus=rec.fire_event_bonus,
                    assigned_from_detection_time=self.time_s,
                    detector_cell=rec.detector_cell,
                    target_cell=rec.target_cell,
                    detector_cell_center=rec.detector_cell_center,
                    target_cell_center=rec.target_cell_center,
                    grid_cell_size_m=rec.grid_cell_size_m,
                    grid_distance_cells=rec.grid_distance_cells,
                    grid_metric=rec.grid_metric,
                )
            )

            self.log_event(
                "fire_order_pending",
                f"{detector.name} report queued for {ar.name}; fire order will arrive in {command_delay_s:.1f}s",
                unit_id=ar.id,
                target_id=target.id,
                side=ar.side,
                data={
                    "confidence": rec.confidence,
                    "detector_id": detector.id,
                    "hq_id": hq.id if hq is not None else None,
                    "target_pos": self._reported_target_point(rec, target).as_tuple(),
                    "target_cell": list(rec.target_cell) if rec.target_cell is not None else None,
                    "detector_cell": list(rec.detector_cell) if rec.detector_cell is not None else None,
                    "arrival_time": arrival_time,
                    "command_delay_s": command_delay_s,
                    "wta": True,
                },
            )

    def _activate_due_fire_orders(self) -> None:
        """Promote delayed fire orders into active artillery fire missions."""

        remaining_orders: List[PendingFireOrder] = []

        for order in self.pending_fire_orders:
            if self.time_s < order.arrival_time:
                remaining_orders.append(order)
                continue

            ar = self.units.get(order.artillery_id)
            target = self.units.get(order.target_id)

            if ar is None or target is None:
                continue
            if not ar.can_engage_at(self.time_s) or not target.can_be_damaged_at(self.time_s) or target.side == ar.side:
                continue
            if ar.shell_range_m is None or self._dist(ar.position, order.target_pos) > ar.shell_range_m:
                continue

            self.fire_missions[ar.id] = {
                "target_id": order.target_id,
                "target_name": order.target_name,
                "target_pos": order.target_pos,
                "detector_id": order.detector_id,
                "detector_name": order.detector_name,
                "hq_id": order.hq_id,
                "hq_name": order.hq_name,
                "confidence": order.confidence,
                "reported_distance_m": order.reported_distance_m,
                "line_of_sight": order.line_of_sight,
                "terrain_factor": order.terrain_factor,
                "altitude_factor": order.altitude_factor,
                "range_factor": order.range_factor,
                "fire_event_bonus": order.fire_event_bonus,
                "detector_cell": list(order.detector_cell) if order.detector_cell is not None else None,
                "target_cell": list(order.target_cell) if order.target_cell is not None else None,
                "detector_cell_center": list(order.detector_cell_center) if order.detector_cell_center is not None else None,
                "target_cell_center": list(order.target_cell_center) if order.target_cell_center is not None else None,
                "grid_cell_size_m": order.grid_cell_size_m,
                "grid_distance_cells": order.grid_distance_cells,
                "grid_metric": order.grid_metric,
                "assigned_at": self.time_s,
                "order_created_at": order.assigned_from_detection_time,
                "order_arrived_at": self.time_s,
            }

            self.log_event(
                "artillery_target",
                f"{order.hq_name if order.hq_name else 'Command net'} assigned {ar.name} delayed WTA fire mission on {target.name} from {order.detector_name} report",
                unit_id=ar.id,
                target_id=target.id,
                side=ar.side,
                data={
                    "confidence": order.confidence,
                    "detector_id": order.detector_id,
                    "hq_id": order.hq_id,
                    "target_pos": order.target_pos.as_tuple(),
                    "target_cell": list(order.target_cell) if order.target_cell is not None else None,
                    "detector_cell": list(order.detector_cell) if order.detector_cell is not None else None,
                    "command_delay_s": self.time_s - order.assigned_from_detection_time,
                    "wta": True,
                },
            )

        self.pending_fire_orders = remaining_orders




    def _command_delay_s(self) -> float:
        command_cfg = self.config.get("simulation", "command", default={})
        return (
            float(command_cfg.get("observer_to_hq_delay_s", 0.0))
            + float(command_cfg.get("hq_processing_delay_s", 0.0))
            + float(command_cfg.get("hq_to_artillery_delay_s", 0.0))
            + float(command_cfg.get("artillery_order_processing_delay_s", 0.0))
        )
    
    
    def _fire_artillery(self, launcher: Unit, target: Unit, detection: DetectionRecord, *, target_pos: Point | None = None) -> None:
        if launcher.ammo_remaining is not None and launcher.ammo_remaining <= 0:
            return
        if launcher.shell_speed_mps is None or launcher.shell_damage is None:
            return
        if launcher.shell_range_m is None:
            return

        aim_point = target_pos or target.position
        dist = self._dist(launcher.position, aim_point)
        ballistic_travel = dist / max(launcher.shell_speed_mps, 1.0)
        artillery_delay_s = self.runtime_parameters["artillery_delay_s"]

        # terrain influence and hit quality degrade with distance and confidence
        travel = max(2.0, artillery_delay_s, ballistic_travel)
        range_factor = max(0.2, 1.0 - dist / launcher.shell_range_m)
        dispersion = launcher.shell_dispersion_m or 150.0
        dispersion_penalty = max(0.35, 1.0 - dispersion / max(dist, 1.0))
        accuracy = max(0.05, min(1.0, detection.confidence * range_factor * dispersion_penalty))
        target_area_scale = max(self.runtime_parameters["target_area_scale"], 0.1)
        radius_m = max(75.0, min(650.0, dispersion * math.sqrt(target_area_scale) * 1.6))
        damage = launcher.shell_damage * range_factor * self.runtime_parameters["artillery_damage_scale"] / target_area_scale
        shell_id = f"S-{uuid.uuid4().hex[:10]}"
        shell = ShellImpact(
            shell_id=shell_id,
            launcher_id=launcher.id,
            target_id=target.id,
            start_pos=launcher.position,
            target_pos=aim_point,
            damage=damage,
            launch_time=self.time_s,
            impact_time=self.time_s + travel,
            accuracy=accuracy,
            radius_m=radius_m,
            ballistic_travel_s=ballistic_travel,
        )
        self.shells[shell_id] = shell
        launcher.last_fired_at = self.time_s
        self.log_event(
            "shell_launch",
            f"{launcher.name} fired assigned WTA mission on {target.name}; impact in {travel:.1f}s",
            unit_id=launcher.id,
            target_id=target.id,
            side=launcher.side,
            data={
                "shell_id": shell_id,
                "accuracy": accuracy,
                "damage": damage,
                "radius_m": radius_m,
                "travel_s": travel,
                "ballistic_travel_s": ballistic_travel,
                "artillery_delay_s": artillery_delay_s,
                "target_area_scale": target_area_scale,
            },
        )
        if launcher.ammo_remaining is not None:
            launcher.ammo_remaining -= 1
        self._resolve_counter_battery(launcher, detection)

    def _resolve_shell_impacts(self) -> None:
        for sid, shell in list(self.shells.items()):
            if not shell.active or shell.landed:
                continue
            if self.time_s < shell.impact_time:
                continue
            launcher = self.units.get(shell.launcher_id)
            target = self.units.get(shell.target_id)
            if launcher is None:
                shell.landed = True
                continue
            affected: list[tuple[Unit, float, float]] = []
            radius = max(shell.radius_m, 1.0)
            for candidate in self.units.values():
                if not candidate.can_be_damaged_at(self.time_s) or candidate.side == launcher.side:
                    continue
                distance_to_impact = self._dist(candidate.position, shell.target_pos)
                if distance_to_impact > radius:
                    continue
                falloff = max(0.0, 1.0 - distance_to_impact / radius)
                # Carleton-style area effect approximation: intensity decays
                # across the target area but keeps a non-zero fragmentation
                # floor near the beaten zone.
                area_factor = 0.25 + 0.75 * falloff
                if candidate.id == shell.target_id:
                    area_factor = max(area_factor, 0.85)
                damage = shell.damage * shell.accuracy * area_factor
                if damage <= 0.0:
                    continue
                candidate.strength = max(0.0, candidate.strength - damage)
                affected.append((candidate, damage, distance_to_impact))
            shell.landed = True
            target_name = target.name if target is not None else "target position"
            self.log_event(
                "shell_impact",
                f"Shell {shell.shell_id} impacted {target_name}; {len(affected)} units in beaten zone",
                unit_id=shell.launcher_id,
                target_id=shell.target_id,
                side=launcher.side,
                data={
                    "accuracy": shell.accuracy,
                    "radius_m": shell.radius_m,
                    "affected": [
                        {"unit_id": unit.id, "name": unit.name, "damage": damage, "distance_m": dist}
                        for unit, damage, dist in affected
                    ],
                },
            )

    def _resolve_counter_battery(self, launcher: Unit, detection: DetectionRecord) -> None:
        """Apply a small DES counter-battery risk after an indirect-fire shot.

        The design notes call for indirect fire to include delayed effects and
        counter-battery losses for artillery.  This intentionally remains an
        aggregate gun-count reduction, not individual round ballistics.
        """

        candidates = [
            unit
            for unit in self.units.values()
            if unit.is_artillery and unit.can_engage_at(self.time_s) and unit.side != launcher.side and unit.shell_range_m
        ]
        if not candidates:
            return
        candidates = [unit for unit in candidates if self._dist(unit.position, launcher.position) <= float(unit.shell_range_m or 0.0)]
        if not candidates:
            return
        responder = min(candidates, key=lambda unit: self._dist(unit.position, launcher.position))
        probability = min(0.65, 0.12 + detection.confidence * 0.35)
        if self.rng.random() > probability:
            return
        base_damage = max(0.05, float(responder.shell_damage or 0.3) * 0.08)
        damage = base_damage * self.runtime_parameters["artillery_damage_scale"]
        launcher.strength = max(0.0, launcher.strength - damage)
        self.log_event(
            "counter_battery",
            f"{responder.name} counter-battery fire reduced {launcher.name} by {damage:.2f}",
            unit_id=responder.id,
            target_id=launcher.id,
            side=responder.side,
            data={"damage": damage, "probability": probability, "confidence": detection.confidence},
        )

    # -----------------------------
    # helpers
    # -----------------------------
    def _dist(self, a: Point, b: Point) -> float:
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

    def _terrain_damping_at_position(self, p: Point) -> float:
        terrain_mod = self.config.get(
            "simulation",
            "combat",
            "terrain_damping",
            default={"plain": 1.0, "hill": 0.93, "mountain": 0.82, "water": 0.0},
        )
        cell = self.terrain.cells.get(self.terrain.rowcol_for_position(p))
        if cell is None:
            return 1.0
        if cell.water:
            return float(terrain_mod.get("water", 0.0))
        return float(terrain_mod.get(cell.landform_name, 1.0))

    def _reported_target_point(self, detection: DetectionRecord, target: Unit) -> Point:
        """Return the cell-level target report consumed by artillery/WTA."""

        center = detection.target_cell_center
        if center is None:
            return target.position
        return Point(float(center[0]), float(center[1]))

    def _tuple_int_pair(self, value: Any) -> tuple[int, int] | None:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return (int(value[0]), int(value[1]))
        return None

    def _tuple_float_pair(self, value: Any) -> tuple[float, float] | None:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return (float(value[0]), float(value[1]))
        return None

    def _best_friendly_detection(
        self,
        side: Side,
        target_id: str,
        detections: Dict[tuple[str, str], DetectionRecord],
    ) -> Optional[DetectionRecord]:
        best: Optional[DetectionRecord] = None
        for (detector_id, tid), rec in detections.items():
            if tid != target_id:
                continue
            detector = self.units.get(detector_id)
            if detector is None or detector.side != side:
                continue
            if best is None or rec.confidence > best.confidence:
                best = rec
        return best

    def _command_posts(self, side: Side) -> List[Unit]:
        return [u for u in self.units.values() if u.side == side and u.is_command and u.is_alive()]

    def _best_commanded_detection(
        self,
        artillery: Unit,
        target_id: str,
        detections: Dict[tuple[str, str], DetectionRecord],
    ) -> Optional[DetectionRecord]:
        report = self._best_commanded_detection_report(artillery, target_id, detections, recon_only=False)
        return report[0] if report is not None else None

    def _best_commanded_detection_report(
        self,
        artillery: Unit,
        target_id: str,
        detections: Dict[tuple[str, str], DetectionRecord],
        *,
        recon_only: bool,
    ) -> Optional[Tuple[DetectionRecord, Unit, Optional[Unit]]]:
        """Return report, detector, and HQ for detector -> HQ -> artillery."""

        command_required = bool(self.config.get("simulation", "command", "require_hq_for_artillery_tasking", default=True))
        command_posts = self._command_posts(artillery.side) if command_required else []
        best: Optional[Tuple[DetectionRecord, Unit, Optional[Unit]]] = None

        for (detector_id, tid), rec in detections.items():
            if tid != target_id:
                continue
            detector = self.units.get(detector_id)
            if detector is None or detector.side != artillery.side:
                continue
            if recon_only and not detector.is_recon:
                continue

            if not command_required or not command_posts:
                candidate = (rec, detector, None)
                if best is None or rec.confidence > best[0].confidence:
                    best = candidate
                continue

            for hq in command_posts:
                detector_to_hq = self._dist(detector.position, hq.position)
                hq_to_artillery = self._dist(hq.position, artillery.position)
                can_relay = detector_to_hq <= max(detector.command_range_m, hq.command_range_m)
                can_task = hq_to_artillery <= max(hq.command_range_m, artillery.command_range_m)
                if not (can_relay and can_task):
                    continue
                key = (detector.id, hq.id, target_id)
                last = self._logged_relays.get(key, -1_000_000.0)
                relay_interval = float(self.config.get("simulation", "command", "relay_log_interval_s", default=20.0))
                if self.time_s - last > relay_interval:
                    target = self.units.get(target_id)
                    self.log_event(
                        "intel_relay",
                        f"{detector.name} relayed {target.name if target else target_id} contact to {hq.name}; WTA tasking link open to {artillery.name}",
                        unit_id=detector.id,
                        target_id=target_id,
                        side=artillery.side,
                        data={
                            "confidence": rec.confidence,
                            "detector_to_hq_m": detector_to_hq,
                            "hq_to_artillery_m": hq_to_artillery,
                            "recon_only": recon_only,
                        },
                    )
                    self._logged_relays[key] = self.time_s
                candidate = (rec, detector, hq)
                if best is None or rec.confidence > best[0].confidence:
                    best = candidate
        return best

    def _log_detections(self, detections: Dict[tuple[str, str], DetectionRecord]) -> None:
        for (detector_id, target_id), rec in detections.items():
            key = (detector_id, target_id)
            last = self._logged_detections.get(key, -1_000_000.0)
            detect_interval = float(self.config.get("simulation", "command", "detection_log_interval_s", default=25.0))
            if self.time_s - last < detect_interval:
                continue
            detector = self.units.get(detector_id)
            target = self.units.get(target_id)
            if not detector or not target:
                continue
            self.log_event(
                "detection",
                f"{detector.name} detected {target.name} at {rec.distance_m:.0f}m (confidence {rec.confidence:.0%})",
                unit_id=detector_id,
                target_id=target_id,
                side=detector.side,
                data={"confidence": rec.confidence, "distance_m": rec.distance_m, "range_factor": rec.range_factor, "los": rec.line_of_sight},
            )
            self._logged_detections[key] = self.time_s

    def log_event(
        self,
        category: str,
        message: str,
        unit_id: str | None = None,
        target_id: str | None = None,
        side: Side | None = None,
        data: Dict[str, Any] | None = None,
    ) -> None:
        self.event_log.append(BattleEvent(self.time_s, category, message, unit_id, target_id, side, data or {}))
        self.event_log = self.event_log[-500:]

    def _sample_replay(self) -> None:
        if self.time_s - self._last_replay_sample_s < 2.0:
            return
        self.replay_frames.append(self.export_state(include_logs=False))
        self.replay_frames = self.replay_frames[-900:]
        self._last_replay_sample_s = self.time_s

    def snapshot(self) -> SimulationResult:
        red = sum(u.strength for u in self.units.values() if u.side == Side.RED)
        blue = sum(u.strength for u in self.units.values() if u.side == Side.BLUE)
        terminal = self.terminal_status()
        expected_duration_s = float(
            self.config.get(
                "simulation",
                "timeline",
                "expected_duration_s",
                default=self.config.get("simulation", "duration_seconds", default=3600.0),
            )
        )
        return SimulationResult(
            time_s=self.time_s,
            active_units=len(self.alive_units()),
            red_strength=red,
            blue_strength=blue,
            active_contacts=len(self.contacts),
            ended=bool(terminal["ended"]),
            winner=terminal["winner"],
            end_reason=terminal["reason"],
            red_tanks=int(terminal["red_tanks"]),
            blue_tanks=int(terminal["blue_tanks"]),
            expected_duration_s=expected_duration_s,
        )

    def terrain_payload(self) -> Dict[str, Any]:
        return self.terrain.export_payload()

    def engagements_payload(self) -> Dict[str, Any]:
        engagements = []
        for contact in self.contacts.values():
            a = self.units.get(contact.attacker_id)
            b = self.units.get(contact.defender_id)
            if not a or not b:
                continue
            history = [
                {"time_s": t, "a_strength": a_s, "b_strength": b_s}
                for t, a_s, b_s in self.contact_history.get(tuple(sorted((a.id, b.id))), [])[-120:]
            ]
            engagements.append(
                {
                    "id": "-".join(sorted((a.id, b.id))),
                    "attacker": self._unit_brief(a),
                    "defender": self._unit_brief(b),
                    "started_at": contact.started_at,
                    "active_seconds": self.time_s - contact.started_at,
                    "range_m": contact.last_range_m,
                    "last_deltas": {
                        "attacker_loss": contact.last_deltas[0],
                        "defender_loss": contact.last_deltas[1],
                    },
                    "last_k": {
                        "attacker_to_defender": contact.last_k[0],
                        "defender_to_attacker": contact.last_k[1],
                    },
                    "terrain_factors": {
                        "attacker": contact.terrain_factors[0],
                        "defender": contact.terrain_factors[1],
                    },
                    "law": "Lanchester Square Law",
                    "history": history,
                }
            )
        return {"time_s": self.time_s, "engagements": engagements}

    def _unit_brief(self, unit: Unit) -> Dict[str, Any]:
        return {
            "id": unit.id,
            "name": unit.name,
            "side": unit.side.value,
            "kind": "command_post" if unit.is_command else unit.kind.value,
            "type": unit.unit_type,
            "echelon": unit.echelon,
            "strength": unit.strength,
            "max_strength": unit.max_strength,
            "normalized_strength": unit.normalized_strength,
            "damage_state": self._damage_state(unit),
        }

    def _damage_state(self, unit: Unit) -> Dict[str, float]:
        lost = max(0.0, unit.max_strength - unit.strength)
        return {
            "killed": round(lost * 0.55, 3),
            "mobility_kill": round(lost * 0.25, 3),
            "firepower_kill": round(lost * 0.20, 3),
            "no_kill": round(max(unit.strength, 0.0), 3),
        }

    def tank_counts_by_side_and_type(self) -> Dict[str, Dict[str, int]]:
        counts: Dict[str, Dict[str, int]] = {Side.RED.value: {}, Side.BLUE.value: {}}
        for unit in self.units.values():
            if unit.is_alive() and unit.kind == UnitKind.TANK:
                side_counts = counts.setdefault(unit.side.value, {})
                side_counts[unit.unit_type] = side_counts.get(unit.unit_type, 0) + 1
        return counts

    def loss_exchange_payload(self) -> Dict[str, Any]:
        initial_red = max(self._initial_strength_by_side.get(Side.RED, 0.0), 0.0)
        initial_blue = max(self._initial_strength_by_side.get(Side.BLUE, 0.0), 0.0)
        current_red = sum(unit.strength for unit in self.units.values() if unit.side == Side.RED and unit.is_alive())
        current_blue = sum(unit.strength for unit in self.units.values() if unit.side == Side.BLUE and unit.is_alive())
        red_losses = max(0.0, initial_red - current_red)
        blue_losses = max(0.0, initial_blue - current_blue)
        return {
            "red_losses": red_losses,
            "blue_losses": blue_losses,
            "red_loss_ratio": red_losses / initial_red if initial_red > 0.0 else 0.0,
            "blue_loss_ratio": blue_losses / initial_blue if initial_blue > 0.0 else 0.0,
            "red_losses_per_blue_loss": red_losses / blue_losses if blue_losses > 1e-9 else None,
            "blue_losses_per_red_loss": blue_losses / red_losses if red_losses > 1e-9 else None,
        }

    def reserve_status_payload(self) -> Dict[str, Any]:
        pending = []
        triggered = []
        thresholds = []
        pending_strength = 0.0
        triggered_strength = 0.0
        pending_strength_by_side: Dict[str, float] = {Side.RED.value: 0.0, Side.BLUE.value: 0.0}
        triggered_strength_by_side: Dict[str, float] = {Side.RED.value: 0.0, Side.BLUE.value: 0.0}
        activated_ids = set(self._reserve_activated_ids)
        for unit in self.units.values():
            if unit.reserve_trigger_loss_ratio is None:
                continue
            strength = max(unit.strength, 0.0)
            item = {
                "id": unit.id,
                "name": unit.name,
                "side": unit.side.value,
                "strength": strength,
                "max_strength": unit.max_strength,
                "trigger_side": unit.reserve_trigger_side or unit.side.value,
                "trigger_kind": unit.reserve_trigger_kind or unit.kind.value,
                "threshold": unit.reserve_trigger_loss_ratio,
                "triggered": unit.reserve_triggered,
                "triggered_at_s": unit.reserve_triggered_at_s,
                "lifecycle_state": unit.lifecycle_state_at(self.time_s),
            }
            thresholds.append(unit.reserve_trigger_loss_ratio)
            if unit.reserve_triggered:
                activated_ids.add(unit.id)
                triggered.append(item)
                triggered_strength += strength
                triggered_strength_by_side[unit.side.value] = triggered_strength_by_side.get(unit.side.value, 0.0) + strength
            else:
                pending.append(item)
                pending_strength += strength
                pending_strength_by_side[unit.side.value] = pending_strength_by_side.get(unit.side.value, 0.0) + strength
        return {
            "pending_units": len(pending),
            "triggered_units": len(activated_ids | {str(item["id"]) for item in triggered}),
            "triggered_surviving_units": len(triggered),
            "pending_strength": pending_strength,
            "triggered_strength": triggered_strength,
            "pending_strength_by_side": pending_strength_by_side,
            "triggered_strength_by_side": triggered_strength_by_side,
            "pending": pending,
            "triggered": triggered,
            "threshold": min(thresholds) if thresholds else None,
            "red_tank_loss_ratio": self._nonreserve_loss_ratio(Side.RED, UnitKind.TANK),
        }

    def export_state(self, include_logs: bool = True) -> Dict[str, Any]:
        units = []
        for u in self.units.values():
            cell = self.terrain.cells.get(self.terrain.rowcol_for_position(u.position))
            units.append(
                {
                    "id": u.id,
                    "name": u.name,
                    "side": u.side.value,
                    "kind": "command_post" if u.is_command else u.kind.value,
                    "type": u.unit_type,
                    "echelon": u.echelon,
                    "x": u.position.x,
                    "y": u.position.y,
                    "strength": u.strength,
                    "max_strength": u.max_strength,
                    "normalized_strength": u.normalized_strength,
                    "morale": u.morale,
                    "speed_mps": u.speed_mps,
                    "armor": u.armor,
                    "detection_range_m": u.detection_range_m,
                    "command_range_m": u.command_range_m,
                    "lanchester_range_m": u.lanchester_range_m,
                    "ammo_remaining": u.ammo_remaining,
                    "waypoints": [p.as_tuple() for p in u.movement_path.waypoints],
                    "order": dict(u.current_order),
                    "elevation_m": cell.elevation_m if cell else None,
                    "damage_state": self._damage_state(u),
                    "active_after_s": u.active_after_s,
                    "present_after_s": u.present_after_s,
                    "detectable_after_s": u.detectable_after_s,
                    "targetable_after_s": u.targetable_after_s,
                    "maneuver_after_s": u.maneuver_after_s,
                    "engage_after_s": u.engage_after_s,
                    "activation_phase": u.activation_phase,
                    "activation_label": u.activation_label,
                    "visible_before_activation": u.visible_before_activation,
                    "reserve_trigger_side": u.reserve_trigger_side,
                    "reserve_trigger_kind": u.reserve_trigger_kind,
                    "reserve_trigger_loss_ratio": u.reserve_trigger_loss_ratio,
                    "reserve_triggered": u.reserve_triggered,
                    "reserve_triggered_at_s": u.reserve_triggered_at_s,
                    "lifecycle_state": u.lifecycle_state_at(self.time_s),
                    "present": u.is_present_at(self.time_s),
                    "detectable": u.is_detectable_at(self.time_s),
                    "targetable": u.can_be_damaged_at(self.time_s),
                    "can_move": u.can_move_at(self.time_s),
                    "can_engage": u.can_engage_at(self.time_s),
                }
            )

        shell_visual_window_s = self._shell_visual_window_s()
        shells = [
            {
                "id": s.shell_id,
                "launcher_id": s.launcher_id,
                "target_id": s.target_id,
                "start": s.start_pos.as_tuple(),
                "target": s.target_pos.as_tuple(),
                "damage": s.damage,
                "launch_time": s.launch_time,
                "impact_time": s.impact_time,
                "remaining": s.remaining_time(self.time_s),
                "accuracy": s.accuracy,
                "radius_m": s.radius_m,
                "kind": s.kind,
                "active": s.active,
                "landed": s.landed,
                "ballistic_travel_s": s.ballistic_travel_s,
                "visual_recent": s.landed and self.time_s - s.impact_time <= shell_visual_window_s,
            }
            for s in self.shells.values()
            if s.is_enroute or (s.landed and self.time_s - s.impact_time <= shell_visual_window_s)
        ]
        fire_missions = [
            {
                "artillery_id": artillery_id,
                "target_id": str(mission.get("target_id", "")),
                "target_name": str(mission.get("target_name", "")),
                "target": mission["target_pos"].as_tuple() if isinstance(mission.get("target_pos"), Point) else None,
                "detector_id": str(mission.get("detector_id", "")),
                "detector_name": str(mission.get("detector_name", "")),
                "hq_id": mission.get("hq_id"),
                "hq_name": mission.get("hq_name"),
                "confidence": float(mission.get("confidence", 0.0)),
                "reported_distance_m": float(mission.get("reported_distance_m", 0.0)),
                "line_of_sight": bool(mission.get("line_of_sight", True)),
                "terrain_factor": float(mission.get("terrain_factor", 1.0)),
                "altitude_factor": float(mission.get("altitude_factor", 1.0)),
                "range_factor": float(mission.get("range_factor", 1.0)),
                "fire_event_bonus": float(mission.get("fire_event_bonus", 0.0)),
                "detector_cell": mission.get("detector_cell"),
                "target_cell": mission.get("target_cell"),
                "detector_cell_center": mission.get("detector_cell_center"),
                "target_cell_center": mission.get("target_cell_center"),
                "grid_cell_size_m": float(mission.get("grid_cell_size_m", 0.0)),
                "grid_distance_cells": float(mission.get("grid_distance_cells", 0.0)),
                "grid_metric": str(mission.get("grid_metric", "chebyshev")),
                "assigned_at": float(mission.get("assigned_at", 0.0)),
            }
            for artillery_id, mission in self.fire_missions.items()
        ]
        pending_fire_orders = [
            {
                "arrival_time": order.arrival_time,
                "artillery_id": order.artillery_id,
                "target_id": order.target_id,
                "target_name": order.target_name,
                "target": order.target_pos.as_tuple(),
                "detector_id": order.detector_id,
                "detector_name": order.detector_name,
                "hq_id": order.hq_id,
                "hq_name": order.hq_name,
                "confidence": order.confidence,
                "reported_distance_m": order.reported_distance_m,
                "line_of_sight": order.line_of_sight,
                "terrain_factor": order.terrain_factor,
                "altitude_factor": order.altitude_factor,
                "range_factor": order.range_factor,
                "fire_event_bonus": order.fire_event_bonus,
                "detector_cell": list(order.detector_cell) if order.detector_cell is not None else None,
                "target_cell": list(order.target_cell) if order.target_cell is not None else None,
                "detector_cell_center": list(order.detector_cell_center) if order.detector_cell_center is not None else None,
                "target_cell_center": list(order.target_cell_center) if order.target_cell_center is not None else None,
                "grid_cell_size_m": order.grid_cell_size_m,
                "grid_distance_cells": order.grid_distance_cells,
                "grid_metric": order.grid_metric,
                "assigned_from_detection_time": order.assigned_from_detection_time,
            }
            for order in self.pending_fire_orders
        ]

        summary = self.snapshot()
        terminal = self.terminal_status()
        present_units = [u for u in self.units.values() if u.is_present_at(self.time_s)]
        absent_units = [u for u in self.units.values() if u.is_alive() and not u.is_present_at(self.time_s)]
        maneuvering_units = [u for u in self.units.values() if u.can_move_at(self.time_s)]
        reserve_status = self.reserve_status_payload()
        exchange = self.loss_exchange_payload()
        timeline_frames = int(self.config.get("simulation", "timeline", "frames", default=0) or 0)
        timeline_interval_s = float(
            self.config.get("simulation", "timeline", "frame_interval_s", default=0.0) or 0.0
        )
        if timeline_frames <= 0:
            timeline_frames = max(1, int(summary.expected_duration_s / 30.0))
        if timeline_interval_s <= 0.0:
            timeline_interval_s = max(summary.expected_duration_s / max(timeline_frames - 1, 1), 1.0)
        payload = {
            "time_s": self.time_s,
            "terrain": {
                "bounds": list(self.terrain.bounds),
                "width_m": self.terrain.width_m(),
                "height_m": self.terrain.height_m(),
            },
            "units": units,
            "shells": shells,
            "fire_missions": fire_missions,
            "pending_fire_orders": pending_fire_orders,
            "detection_grid_cell_size_m": float(
                self.config.get("simulation", "detection", "grid_cell_size_m", default=250.0)
            ),
            "detections": [
                {
                    "detector_id": det_id,
                    "target_id": tgt_id,
                    "x": float(center[0]),
                    "y": float(center[1]),
                    "unit_x": tgt.position.x,
                    "unit_y": tgt.position.y,
                    "detector_side": (det.side.value if det else None),
                    "confidence": rec.confidence,
                    "distance_m": rec.distance_m,
                    "line_of_sight": rec.line_of_sight,
                    "range_factor": rec.range_factor,
                    "detector_cell": list(rec.detector_cell) if rec.detector_cell is not None else None,
                    "target_cell": list(rec.target_cell) if rec.target_cell is not None else None,
                    "detector_cell_center": list(rec.detector_cell_center) if rec.detector_cell_center is not None else None,
                    "target_cell_center": list(rec.target_cell_center) if rec.target_cell_center is not None else None,
                    "grid_cell_size_m": rec.grid_cell_size_m,
                    "grid_distance_cells": rec.grid_distance_cells,
                    "grid_metric": rec.grid_metric,
                }
                for (det_id, tgt_id), rec in self.last_detections.items()
                if (tgt := self.units.get(tgt_id)) is not None
                for det in [self.units.get(det_id)]
                for center in [rec.target_cell_center or tgt.position.as_tuple()]
            ],
            "summary": {
                "active_units": summary.active_units,
                "present_units": len(present_units),
                "absent_units": len(absent_units),
                "maneuvering_units": len(maneuvering_units),
                "red_strength": summary.red_strength,
                "blue_strength": summary.blue_strength,
                "active_contacts": summary.active_contacts,
                "ended": summary.ended,
                "winner": summary.winner,
                "end_reason": summary.end_reason,
                "red_tanks": summary.red_tanks,
                "blue_tanks": summary.blue_tanks,
                "red_initial_strength": float(terminal.get("red_initial_strength", 0.0)),
                "red_force_end_threshold": float(terminal.get("red_force_end_threshold", 0.0)),
                "blue_tank_end_count": int(terminal.get("blue_tank_end_count", 0)),
                "unit_removal_ratio": float(self.runtime_parameters.get("unit_removal_ratio", 0.20)),
                "tank_counts": self.tank_counts_by_side_and_type(),
                "reserve_status": reserve_status,
                "reserve_pending_units": reserve_status["pending_units"],
                "reserve_triggered_units": reserve_status["triggered_units"],
                "reserve_pending_strength": reserve_status["pending_strength"],
                "reserve_triggered_strength": reserve_status["triggered_strength"],
                "red_tank_loss_ratio": reserve_status["red_tank_loss_ratio"],
                "exchange": exchange,
                "loss_exchange_ratio": exchange["red_losses_per_blue_loss"],
                "expected_duration_s": summary.expected_duration_s,
                "progress_ratio": 1.0 if summary.ended else max(0.0, min(0.98, self.time_s / max(summary.expected_duration_s, 1.0))),
                "current_frame": min(timeline_frames, int(self.time_s / timeline_interval_s) + 1),
                "total_frames": timeline_frames,
            },
            "parameters": dict(self.runtime_parameters),
            "lanchester_matrix": self.runtime_lanchester_matrix,
            "model": {
                "direct_fire": "Lanchester Square Law",
                "indirect_fire": "Lanchester Linear Law + DES delay",
                "targeting": "Greedy WTA",
                "damage_state": "4-State K/M/F/No-kill aggregate",
                "combat_power": "Bracken weighted strength",
            },
            "contacts": self.engagements_payload()["engagements"],
        }
        if include_logs:
            payload["events"] = [
                {
                    "time_s": e.time_s,
                    "category": e.category,
                    "message": e.message,
                    "unit_id": e.unit_id,
                    "target_id": e.target_id,
                    "side": e.side.value if e.side else None,
                    "data": e.data or {},
                }
                for e in self.event_log
            ]
            payload["replay_frames"] = self.replay_frames
        return payload

    def load_state(self, state: Dict[str, Any]) -> None:
        self.time_s = float(state.get("time_s", self.time_s))
        if "fire_missions" in state:
            self.fire_missions.clear()
        if "shells" in state:
            self.shells.clear()
        if "pending_fire_orders" in state:
            self.pending_fire_orders.clear()
        if "contacts" in state:
            self.contacts.clear()
            self.contact_history.clear()
        for item in state.get("units", []):
            unit = self.units.get(item.get("id"))
            if unit is None:
                continue
            unit.position = Point(float(item.get("x", unit.position.x)), float(item.get("y", unit.position.y)))
            unit.strength = float(item.get("strength", unit.strength))
            unit.max_strength = float(item.get("max_strength", unit.max_strength))
            unit.morale = float(item.get("morale", unit.morale))
            unit.speed_mps = float(item.get("speed_mps", unit.speed_mps))
            unit.armor = float(item.get("armor", unit.armor))
            unit.detection_range_m = float(item.get("detection_range_m", unit.detection_range_m))
            unit.command_range_m = float(item.get("command_range_m", unit.command_range_m))
            unit.lanchester_range_m = float(item.get("lanchester_range_m", unit.lanchester_range_m))
            for attr in (
                "active_after_s",
                "present_after_s",
                "detectable_after_s",
                "targetable_after_s",
                "maneuver_after_s",
                "engage_after_s",
            ):
                if attr in item:
                    setattr(unit, attr, float(item[attr]))
            if "reserve_trigger_side" in item:
                unit.reserve_trigger_side = str(item["reserve_trigger_side"])
            if "reserve_trigger_kind" in item:
                unit.reserve_trigger_kind = str(item["reserve_trigger_kind"])
            if "reserve_trigger_loss_ratio" in item:
                value = item["reserve_trigger_loss_ratio"]
                unit.reserve_trigger_loss_ratio = float(value) if value is not None else None
            if "reserve_triggered" in item:
                unit.reserve_triggered = bool(item["reserve_triggered"])
            if "reserve_triggered_at_s" in item:
                value = item["reserve_triggered_at_s"]
                unit.reserve_triggered_at_s = float(value) if value is not None else None
            if "activation_phase" in item:
                unit.activation_phase = str(item["activation_phase"])
            if "activation_label" in item:
                unit.activation_label = str(item["activation_label"])
            if "visible_before_activation" in item:
                unit.visible_before_activation = bool(item["visible_before_activation"])
            if "echelon" in item:
                unit.echelon = str(item["echelon"])
            elif "echelon_label" in item:
                unit.echelon = str(item["echelon_label"])
            if "ammo_remaining" in item:
                unit.ammo_remaining = item.get("ammo_remaining")
            if "waypoints" in item:
                unit.movement_path.waypoints = [Point(float(p[0]), float(p[1])) for p in item["waypoints"] if len(p) >= 2]
            if "order" in item and isinstance(item["order"], dict):
                unit.current_order = dict(item["order"])
        for shell in state.get("shells", []):
            if not isinstance(shell, dict):
                continue
            shell_id = str(shell.get("id") or shell.get("shell_id") or "")
            launcher_id = str(shell.get("launcher_id", ""))
            target_id = str(shell.get("target_id", ""))
            start_pair = shell.get("start")
            target_pair = shell.get("target")
            if shell_id == "" or launcher_id not in self.units:
                continue
            if not (isinstance(start_pair, (list, tuple)) and len(start_pair) >= 2):
                start_pair = self.units[launcher_id].position.as_tuple()
            if not (isinstance(target_pair, (list, tuple)) and len(target_pair) >= 2):
                target_pair = self.units[target_id].position.as_tuple() if target_id in self.units else start_pair
            impact_time = float(shell.get("impact_time", self.time_s + float(shell.get("remaining", 0.0))))
            launch_time = float(shell.get("launch_time", self.time_s))
            self.shells[shell_id] = ShellImpact(
                shell_id=shell_id,
                launcher_id=launcher_id,
                target_id=target_id,
                start_pos=Point(float(start_pair[0]), float(start_pair[1])),
                target_pos=Point(float(target_pair[0]), float(target_pair[1])),
                damage=float(shell.get("damage", 0.0)),
                launch_time=launch_time,
                impact_time=impact_time,
                accuracy=float(shell.get("accuracy", 1.0)),
                radius_m=float(shell.get("radius_m", 0.0)),
                kind=str(shell.get("kind", "artillery")),
                ballistic_travel_s=float(shell.get("ballistic_travel_s", 0.0)),
                active=True,
                landed=bool(shell.get("landed", False)),
            )
        for mission in state.get("fire_missions", []):
            if not isinstance(mission, dict):
                continue
            artillery_id = str(mission.get("artillery_id", ""))
            target_id = str(mission.get("target_id", ""))
            if artillery_id not in self.units or target_id not in self.units:
                continue
            target_pair = mission.get("target")
            target_pos = self.units[target_id].position
            if isinstance(target_pair, (list, tuple)) and len(target_pair) >= 2:
                target_pos = Point(float(target_pair[0]), float(target_pair[1]))
            self.fire_missions[artillery_id] = {
                "target_id": target_id,
                "target_name": str(mission.get("target_name", self.units[target_id].name)),
                "target_pos": target_pos,
                "detector_id": str(mission.get("detector_id", "")),
                "detector_name": str(mission.get("detector_name", "")),
                "hq_id": mission.get("hq_id"),
                "hq_name": mission.get("hq_name"),
                "confidence": float(mission.get("confidence", 0.35)),
                "reported_distance_m": float(mission.get("reported_distance_m", 0.0)),
                "line_of_sight": bool(mission.get("line_of_sight", True)),
                "terrain_factor": float(mission.get("terrain_factor", 1.0)),
                "altitude_factor": float(mission.get("altitude_factor", 1.0)),
                "range_factor": float(mission.get("range_factor", 1.0)),
                "fire_event_bonus": float(mission.get("fire_event_bonus", 0.0)),
                "detector_cell": mission.get("detector_cell"),
                "target_cell": mission.get("target_cell"),
                "detector_cell_center": mission.get("detector_cell_center"),
                "target_cell_center": mission.get("target_cell_center"),
                "grid_cell_size_m": float(mission.get("grid_cell_size_m", 0.0)),
                "grid_distance_cells": float(mission.get("grid_distance_cells", 0.0)),
                "grid_metric": str(mission.get("grid_metric", "chebyshev")),
                "assigned_at": float(mission.get("assigned_at", self.time_s)),
            }
        for order in state.get("pending_fire_orders", []):
            if not isinstance(order, dict):
                continue
            artillery_id = str(order.get("artillery_id", ""))
            target_id = str(order.get("target_id", ""))
            if artillery_id not in self.units or target_id not in self.units:
                continue
            target_pair = order.get("target")
            target_pos = self.units[target_id].position
            if isinstance(target_pair, (list, tuple)) and len(target_pair) >= 2:
                target_pos = Point(float(target_pair[0]), float(target_pair[1]))
            self.pending_fire_orders.append(
                PendingFireOrder(
                    arrival_time=float(order.get("arrival_time", self.time_s)),
                    artillery_id=artillery_id,
                    target_id=target_id,
                    target_name=str(order.get("target_name", self.units[target_id].name)),
                    target_pos=target_pos,
                    detector_id=str(order.get("detector_id", "")),
                    detector_name=str(order.get("detector_name", "")),
                    hq_id=order.get("hq_id"),
                    hq_name=order.get("hq_name"),
                    confidence=float(order.get("confidence", 0.35)),
                    reported_distance_m=float(order.get("reported_distance_m", 0.0)),
                    line_of_sight=bool(order.get("line_of_sight", True)),
                    terrain_factor=float(order.get("terrain_factor", 1.0)),
                    altitude_factor=float(order.get("altitude_factor", 1.0)),
                    range_factor=float(order.get("range_factor", 1.0)),
                    fire_event_bonus=float(order.get("fire_event_bonus", 0.0)),
                    assigned_from_detection_time=float(order.get("assigned_from_detection_time", self.time_s)),
                    detector_cell=self._tuple_int_pair(order.get("detector_cell")),
                    target_cell=self._tuple_int_pair(order.get("target_cell")),
                    detector_cell_center=self._tuple_float_pair(order.get("detector_cell_center")),
                    target_cell_center=self._tuple_float_pair(order.get("target_cell_center")),
                    grid_cell_size_m=float(order.get("grid_cell_size_m", 0.0)),
                    grid_distance_cells=float(order.get("grid_distance_cells", 0.0)),
                    grid_metric=str(order.get("grid_metric", "chebyshev")),
                )
            )
        for contact in state.get("contacts", []):
            if not isinstance(contact, dict):
                continue
            attacker = contact.get("attacker", {})
            defender = contact.get("defender", {})
            if not isinstance(attacker, dict) or not isinstance(defender, dict):
                continue
            attacker_id = str(attacker.get("id", ""))
            defender_id = str(defender.get("id", ""))
            if attacker_id not in self.units or defender_id not in self.units:
                continue
            key = tuple(sorted((attacker_id, defender_id)))
            last_deltas = contact.get("last_deltas", {})
            last_k = contact.get("last_k", {})
            terrain = contact.get("terrain_factors", {})
            self.contacts[key] = EngagementPair(
                attacker_id=attacker_id,
                defender_id=defender_id,
                started_at=float(contact.get("started_at", self.time_s)),
                last_deltas=(
                    float(last_deltas.get("attacker_loss", 0.0)) if isinstance(last_deltas, dict) else 0.0,
                    float(last_deltas.get("defender_loss", 0.0)) if isinstance(last_deltas, dict) else 0.0,
                ),
                last_k=(
                    float(last_k.get("attacker_to_defender", 0.0)) if isinstance(last_k, dict) else 0.0,
                    float(last_k.get("defender_to_attacker", 0.0)) if isinstance(last_k, dict) else 0.0,
                ),
                last_range_m=float(contact.get("range_m", 0.0)),
                terrain_factors=(
                    float(terrain.get("attacker", 1.0)) if isinstance(terrain, dict) else 1.0,
                    float(terrain.get("defender", 1.0)) if isinstance(terrain, dict) else 1.0,
                ),
            )
            self.contact_history[key] = [
                (float(h.get("time_s", self.time_s)), float(h.get("a_strength", 0.0)), float(h.get("b_strength", 0.0)))
                for h in contact.get("history", [])
                if isinstance(h, dict)
            ][-360:]
        self.log_event("load", "Runtime state loaded from file")
