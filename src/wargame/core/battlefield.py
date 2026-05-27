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
        }
        self.runtime_lanchester_matrix: Dict[str, Dict[str, float]] = self._base_lanchester_matrix()
        self.units: Dict[str, Unit] = {}
        self.shells: Dict[str, ShellImpact] = {}
        self.contacts: Dict[Tuple[str, str], EngagementPair] = {}
        self.event_log: List[BattleEvent] = []
        self.replay_frames: List[Dict[str, Any]] = []
        self.contact_history: Dict[Tuple[str, str], List[Tuple[float, float, float]]] = {}
        self.fire_missions: Dict[str, Dict[str, Any]] = {}
        self.pending_fire_orders: List[PendingFireOrder] = []
        self._logged_detections: Dict[Tuple[str, str], float] = {}
        self._logged_relays: Dict[Tuple[str, str, str], float] = {}
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
        for uid in list(self.units.keys()):
            if not self.units[uid].is_alive():
                unit = self.units[uid]
                self.log_event("destroyed", f"{unit.name} defeated and removed from battle", unit_id=uid, side=unit.side)
                self.remove_unit(uid, reason="destroyed")

    def alive_units(self) -> List[Unit]:
        return [u for u in self.units.values() if u.is_alive()]

    def alive_tanks_by_side(self, side: Side) -> List[Unit]:
        return [u for u in self.units.values() if u.is_alive() and u.kind == UnitKind.TANK and u.side == side]

    def terminal_status(self) -> Dict[str, Any]:
        red_tanks = len(self.alive_tanks_by_side(Side.RED))
        blue_tanks = len(self.alive_tanks_by_side(Side.BLUE))
        if red_tanks <= 0 and blue_tanks <= 0:
            return {"ended": True, "winner": "draw", "reason": "no_tanks", "red_tanks": red_tanks, "blue_tanks": blue_tanks}
        if red_tanks <= 0:
            return {"ended": True, "winner": "blue", "reason": "red_tanks_destroyed", "red_tanks": red_tanks, "blue_tanks": blue_tanks}
        if blue_tanks <= 0:
            return {"ended": True, "winner": "red", "reason": "blue_tanks_destroyed", "red_tanks": red_tanks, "blue_tanks": blue_tanks}
        return {"ended": False, "winner": None, "reason": None, "red_tanks": red_tanks, "blue_tanks": blue_tanks}

    def is_terminal(self) -> bool:
        return bool(self.terminal_status()["ended"])

    # -----------------------------
    # high-level update
    # -----------------------------
    def update(self, dt: float) -> SimulationResult:
        self.time_s += dt

        self._move_units(dt)
        detections = self._resolve_detection()
        self._resolve_contacts(detections, dt)
        self._resolve_artillery(detections, dt)
        self._resolve_shell_impacts()

        self.remove_destroyed()
        self._sample_replay()
        return self.snapshot()

    # -----------------------------
    # movement
    # -----------------------------
    def _move_units(self, dt: float) -> None:
        engaged_unit_ids = self._engaged_unit_ids()
        for unit in self.units.values():
            if not unit.is_alive():
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
            if not u.is_alive() or u.kind != UnitKind.TANK:
                continue

            for v_id in ids[i + 1 :]:
                v = alive[v_id]
                if not v.is_alive() or v.kind != UnitKind.TANK:
                    continue
                if u.side == v.side:
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

                k_uv = matrix.get(u.unit_type, {}).get(v.unit_type)
                k_vu = matrix.get(v.unit_type, {}).get(u.unit_type)
                if k_uv is None or k_vu is None:
                    k_uv = float(self.config.get("simulation", "combat", "default_k_attacker", default=0.0025))
                    k_vu = float(self.config.get("simulation", "combat", "default_k_defender", default=0.0025))

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

    # -----------------------------
    # artillery
    # -----------------------------
    def _resolve_artillery(self, detections: Dict[tuple[str, str], DetectionRecord], dt: float) -> None:
        artillery_units = [u for u in self.units.values() if u.is_artillery and u.is_alive()]
        tanks = [u for u in self.units.values() if u.is_tank and u.is_alive()]

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
            if target is None or not target.is_alive() or target.side == ar.side:
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
                target_pos = target.position

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
                    target_pos=target.position,
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
                    "target_pos": target.position.as_tuple(),
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
            if not ar.is_alive() or not target.is_alive() or target.side == ar.side:
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
                if not candidate.is_alive() or candidate.side == launcher.side:
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
            if unit.is_artillery and unit.is_alive() and unit.side != launcher.side and unit.shell_range_m
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
        expected_duration_s = float(self.config.get("simulation", "timeline", "expected_duration_s", default=3600.0))
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
                }
            )

        shells = [
            {
                "id": s.shell_id,
                "launcher_id": s.launcher_id,
                "target_id": s.target_id,
                "start": s.start_pos.as_tuple(),
                "target": s.target_pos.as_tuple(),
                "damage": s.damage,
                "impact_time": s.impact_time,
                "remaining": s.remaining_time(self.time_s),
                "accuracy": s.accuracy,
                "radius_m": s.radius_m,
                "kind": s.kind,
            }
            for s in self.shells.values()
            if s.is_enroute
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
                "assigned_at": float(mission.get("assigned_at", 0.0)),
            }
            for artillery_id, mission in self.fire_missions.items()
        ]

        summary = self.snapshot()
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
            "summary": {
                "active_units": summary.active_units,
                "red_strength": summary.red_strength,
                "blue_strength": summary.blue_strength,
                "active_contacts": summary.active_contacts,
                "ended": summary.ended,
                "winner": summary.winner,
                "end_reason": summary.end_reason,
                "red_tanks": summary.red_tanks,
                "blue_tanks": summary.blue_tanks,
                "expected_duration_s": summary.expected_duration_s,
                "progress_ratio": 1.0 if summary.ended else max(0.0, min(0.98, self.time_s / max(summary.expected_duration_s, 1.0))),
                "current_frame": int(self.time_s / 30.0),
                "total_frames": max(1, int(summary.expected_duration_s / 30.0)),
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
            if "ammo_remaining" in item:
                unit.ammo_remaining = item.get("ammo_remaining")
            if "waypoints" in item:
                unit.movement_path.waypoints = [Point(float(p[0]), float(p[1])) for p in item["waypoints"] if len(p) >= 2]
            if "order" in item and isinstance(item["order"], dict):
                unit.current_order = dict(item["order"])
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
                "assigned_at": float(mission.get("assigned_at", self.time_s)),
            }
        self.log_event("load", "Runtime state loaded from file")
