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
class SimulationResult:
    time_s: float
    active_units: int
    red_strength: float
    blue_strength: float
    active_contacts: int


class BattleField:
    def __init__(self, terrain: TerrainGrid, config: SimulationConfig):
        self.terrain = terrain
        self.config = config
        self.units: Dict[str, Unit] = {}
        self.shells: Dict[str, ShellImpact] = {}
        self.contacts: Dict[Tuple[str, str], EngagementPair] = {}
        self.time_s = 0.0
        seed = int(self.config.get("simulation", "random_seed", default=19430712))
        self.rng = random.Random(seed)

    # -----------------------------
    # lifecycle
    # -----------------------------
    def add_unit(self, unit: Unit) -> None:
        self.units[unit.id] = unit

    def seed_units(self, units: List[Unit]) -> None:
        for unit in units:
            self.add_unit(unit)

    def remove_destroyed(self) -> None:
        for uid in list(self.units.keys()):
            if not self.units[uid].is_alive():
                self.units.pop(uid)
                self.shells = {
                    k: s for k, s in self.shells.items() if s.launcher_id != uid and s.target_id != uid
                }

    def alive_units(self) -> List[Unit]:
        return [u for u in self.units.values() if u.is_alive()]

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
        return self.snapshot()

    # -----------------------------
    # movement
    # -----------------------------
    def _move_units(self, dt: float) -> None:
        for unit in self.units.values():
            if not unit.is_alive():
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

    # -----------------------------
    # detection + fire contacts
    # -----------------------------
    def _resolve_detection(self) -> Dict[tuple[str, str], DetectionRecord]:
        return detect_unit_targets(
            units=self.alive_units(),
            terrain=self.terrain,
            detection_config=self.config.get("simulation", "detection", default={}),
            now_s=self.time_s,
            rng=self.rng,
        )

    def _resolve_contacts(self, detections: Dict[tuple[str, str], DetectionRecord], dt: float) -> None:
        default_contact_distance = float(self.config.get("simulation", "combat", "lanchester_range_m", default=1800.0))
        matrix = self.config.get("simulation", "lanchester", "kill_matrix", default={})

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

                report = square_step_with_report(
                    a_strength=u.strength,
                    b_strength=v.strength,
                    dt=dt,
                    k_ab=k_uv * range_factor,
                    k_ba=k_vu * range_factor,
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
                    self.contacts[keypair] = EngagementPair(
                        attacker_id=u_id,
                        defender_id=v_id,
                        started_at=self.time_s,
                        last_deltas=(report.kill_a, report.kill_b),
                        last_k=(k_uv * range_factor, k_vu * range_factor),
                        last_range_m=d,
                        terrain_factors=(terrain_u, terrain_v),
                    )
                else:
                    c.last_deltas = (report.kill_a, report.kill_b)
                    c.last_k = (k_uv * range_factor, k_vu * range_factor)
                    c.last_range_m = d
                    c.terrain_factors = (terrain_u, terrain_v)

        # remove stale contacts
        for k in list(self.contacts.keys()):
            if tuple(sorted(k)) not in active_pairs:
                self.contacts.pop(k)

    # -----------------------------
    # artillery
    # -----------------------------
    def _resolve_artillery(self, detections: Dict[tuple[str, str], DetectionRecord], dt: float) -> None:
        artillery_units = [u for u in self.units.values() if u.is_artillery and u.is_alive()]
        tanks = [u for u in self.units.values() if u.is_tank and u.is_alive()]

        if not artillery_units or not tanks:
            return

        for ar in artillery_units:
            if ar.reload_timer > 0:
                ar.reload_timer = max(0.0, ar.reload_timer - dt)
                continue

            # Pick the best enemy target known to this side.  This represents
            # reconnaissance reports being shared with fire-support units.
            visible: List[Tuple[float, Unit, DetectionRecord]] = []
            for t in tanks:
                if t.side == ar.side:
                    continue
                rec = self._best_friendly_detection(ar.side, t.id, detections)
                if rec is None:
                    continue
                if ar.shell_range_m is None:
                    continue
                if rec.distance_m > ar.shell_range_m:
                    continue
                if self._dist(ar.position, t.position) > (ar.shell_range_m):
                    continue
                visible.append((rec.confidence / max(rec.distance_m, 1.0), t, rec))

            if not visible:
                continue

            _, target, rec = max(visible, key=lambda x: x[0])
            self._fire_artillery(ar, target, rec)
            rate = ar.fire_rate_per_min or 2.0
            ar.reload_timer = max(0.0, 60.0 / rate)

    def _fire_artillery(self, launcher: Unit, target: Unit, detection: DetectionRecord) -> None:
        if launcher.ammo_remaining is not None and launcher.ammo_remaining <= 0:
            return
        if launcher.shell_speed_mps is None or launcher.shell_damage is None:
            return
        if launcher.shell_range_m is None:
            return

        dist = self._dist(launcher.position, target.position)
        travel = dist / max(launcher.shell_speed_mps, 1.0)

        # terrain influence and hit quality degrade with distance and confidence
        travel = max(2.0, travel)
        range_factor = max(0.2, 1.0 - dist / launcher.shell_range_m)
        dispersion = launcher.shell_dispersion_m or 150.0
        dispersion_penalty = max(0.35, 1.0 - dispersion / max(dist, 1.0))
        accuracy = max(0.05, min(1.0, detection.confidence * range_factor * dispersion_penalty))
        damage = launcher.shell_damage * range_factor
        shell_id = f"S-{uuid.uuid4().hex[:10]}"
        shell = ShellImpact(
            shell_id=shell_id,
            launcher_id=launcher.id,
            target_id=target.id,
            start_pos=launcher.position,
            target_pos=target.position,
            damage=damage,
            launch_time=self.time_s,
            impact_time=self.time_s + travel,
            accuracy=accuracy,
        )
        self.shells[shell_id] = shell
        launcher.last_fired_at = self.time_s
        if launcher.ammo_remaining is not None:
            launcher.ammo_remaining -= 1

    def _resolve_shell_impacts(self) -> None:
        for sid, shell in list(self.shells.items()):
            if not shell.active or shell.landed:
                continue
            if self.time_s < shell.impact_time:
                continue
            target = self.units.get(shell.target_id)
            if target is None or not target.is_alive():
                shell.landed = True
                continue
            target.strength = max(0.0, target.strength - shell.damage * shell.accuracy)
            shell.landed = True

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

    def snapshot(self) -> SimulationResult:
        red = sum(u.strength for u in self.units.values() if u.side == Side.RED)
        blue = sum(u.strength for u in self.units.values() if u.side == Side.BLUE)
        return SimulationResult(
            time_s=self.time_s,
            active_units=len(self.alive_units()),
            red_strength=red,
            blue_strength=blue,
            active_contacts=len(self.contacts),
        )

    def export_state(self) -> Dict[str, Any]:
        units = []
        for u in self.units.values():
            units.append(
                {
                    "id": u.id,
                    "name": u.name,
                    "side": u.side.value,
                    "kind": u.kind.value,
                    "type": u.unit_type,
                    "x": u.position.x,
                    "y": u.position.y,
                    "strength": u.strength,
                    "max_strength": u.max_strength,
                    "morale": u.morale,
                    "speed_mps": u.speed_mps,
                    "ammo_remaining": u.ammo_remaining,
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
            }
            for s in self.shells.values()
            if s.is_enroute
        ]

        return {
            "time_s": self.time_s,
            "units": units,
            "shells": shells,
            "contacts": [
                {
                    "a": c.attacker_id,
                    "b": c.defender_id,
                    "active_seconds": self.time_s - c.started_at,
                    "last_deltas": c.last_deltas,
                    "last_k": c.last_k,
                    "range_m": c.last_range_m,
                    "terrain_factors": c.terrain_factors,
                }
                for c in self.contacts.values()
            ],
        }
