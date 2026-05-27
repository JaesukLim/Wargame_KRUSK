"""Detection and sensor model utilities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

from .types import Point
from .terrain import TerrainGrid
from .unit import Unit


@dataclass(frozen=True)
class DetectionRecord:
    detector_id: str
    target_id: str
    confidence: float
    distance_m: float
    line_of_sight: bool = True
    terrain_factor: float = 1.0
    altitude_factor: float = 1.0
    range_factor: float = 1.0
    fire_event_bonus: float = 0.0


def _euclid(a: Point, b: Point) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def detect_targets(
    observers: Iterable[Tuple[str, Point, float]],
    targets: Iterable[Tuple[str, Point, float]],
    terrain: TerrainGrid,
    base_probability: float,
    range_factor: float = 1.0,
) -> Dict[tuple[str, str], DetectionRecord]:
    """Compute detections between observers and targets.

    observers/targets tuples are (unit_id, position, detection_range_m)
    """
    out: Dict[tuple[str, str], DetectionRecord] = {}
    for o_id, o_pos, o_rng in observers:
        for t_id, t_pos, t_rng in targets:
            d = _euclid(o_pos, t_pos)
            if d <= o_rng * range_factor and d <= t_rng:
                if not terrain.line_of_sight(o_pos, t_pos):
                    continue
                # Simple probability shaping by distance
                p = base_probability * max(0.0, 1.0 - d / max(o_rng, 1.0))
                out[(o_id, t_id)] = DetectionRecord(
                    detector_id=o_id,
                    target_id=t_id,
                    confidence=max(0.05, p),
                    distance_m=d,
                )
    return out


def detect_unit_targets(
    units: Iterable[Unit],
    terrain: TerrainGrid,
    detection_config: Dict[str, Any],
    now_s: float,
    rng: random.Random,
) -> Dict[tuple[str, str], DetectionRecord]:
    """Scanned-style probabilistic target detection.

    The design document describes a sequential/scanned detection flow where
    optical equipment, terrain, altitude, and firing events combine into a
    final confidence.  This function keeps the formula explicit so designers
    can tune it from config without touching code:

        confidence = optical_base * range_factor * terrain_factor
                     * altitude_factor + fire_event_bonus

    If ``probabilistic`` is true, the record is emitted only when the seeded
    random draw succeeds.  Otherwise every candidate above the minimum
    confidence is returned, which is useful for debugging/grid search.
    """

    unit_list = [u for u in units if u.is_alive()]
    terrain_mod = detection_config.get(
        "terrain_modifiers",
        {"plain": 1.0, "hill": 0.9, "mountain": 0.75, "water": 0.9},
    )
    altitude_mod = detection_config.get("altitude_modifiers", {"low": 1.0, "mid": 0.9, "high": 0.8})
    base_by_kind = detection_config.get("base_probability_by_kind", {})
    base_default = float(detection_config.get("base_probability", 0.86))
    range_decay_power = float(detection_config.get("range_decay_power", 1.0))
    blocked_los_factor = float(detection_config.get("blocked_los_factor", 0.35))
    fire_event_bonus_value = float(detection_config.get("fire_event_bonus", 0.15))
    fire_event_memory_s = float(detection_config.get("fire_event_memory_s", 30.0))
    probabilistic = bool(detection_config.get("probabilistic", True))
    min_confidence = float(detection_config.get("min_confidence_to_report", 0.05))

    out: Dict[tuple[str, str], DetectionRecord] = {}
    for observer in unit_list:
        # Only tanks (기갑) and recon (정찰) scan. Artillery fires on relayed
        # recon intel through HQ; command posts are relay nodes — neither detects.
        if not (observer.is_tank or observer.is_recon):
            continue
        base_probability = float(base_by_kind.get(observer.kind.value, base_default))
        for target in unit_list:
            if observer.id == target.id or observer.side == target.side:
                continue

            d = _euclid(observer.position, target.position)
            if d > observer.detection_range_m:
                continue

            cell = terrain.cells[terrain.rowcol_for_position(target.position)]
            los = terrain.line_of_sight(observer.position, target.position)
            terrain_factor = float(terrain_mod.get(cell.landform_name, 1.0))
            altitude_factor = float(altitude_mod.get(terrain.elevation_band(observer.position), 0.9))
            range_factor = max(0.0, 1.0 - d / max(observer.detection_range_m, 1.0)) ** range_decay_power
            fire_bonus = (
                fire_event_bonus_value
                if now_s - target.last_fired_at <= fire_event_memory_s
                else 0.0
            )

            confidence = base_probability * range_factor * terrain_factor * altitude_factor
            if not los:
                confidence *= blocked_los_factor
            confidence = max(0.0, min(1.0, confidence + fire_bonus))

            if confidence < min_confidence:
                continue
            if probabilistic and rng.random() > confidence:
                continue

            out[(observer.id, target.id)] = DetectionRecord(
                detector_id=observer.id,
                target_id=target.id,
                confidence=confidence,
                distance_m=d,
                line_of_sight=los,
                terrain_factor=terrain_factor,
                altitude_factor=altitude_factor,
                range_factor=range_factor,
                fire_event_bonus=fire_bonus,
            )
    return out
