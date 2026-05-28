"""Detection and sensor model utilities."""

from __future__ import annotations

import math
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
    detector_cell: tuple[int, int] | None = None
    target_cell: tuple[int, int] | None = None
    detector_cell_center: tuple[float, float] | None = None
    target_cell_center: tuple[float, float] | None = None
    grid_cell_size_m: float = 0.0
    grid_distance_cells: float = 0.0
    grid_metric: str = "chebyshev"


def _euclid(a: Point, b: Point) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _terrain_bounds(terrain: TerrainGrid) -> tuple[float, float, float, float]:
    return terrain.bounds


def _grid_cell_for_position(pos: Point, terrain: TerrainGrid, cell_size_m: float) -> tuple[int, int]:
    """Return the detection-grid cell containing ``pos``.

    The configured detection grid is the source of truth for detection.  Unit
    movement inside a cell should not change detection eligibility; crossing a
    cell boundary should.  The returned tuple is ``(row, col)`` in map-space
    grid coordinates.
    """

    min_x, min_y, max_x, max_y = _terrain_bounds(terrain)
    cell_size = max(float(cell_size_m), 1.0)
    max_col = max(0, int(math.floor((max_x - min_x) / cell_size)))
    max_row = max(0, int(math.floor((max_y - min_y) / cell_size)))
    col = int(math.floor((pos.x - min_x) / cell_size))
    row = int(math.floor((pos.y - min_y) / cell_size))
    return (max(0, min(max_row, row)), max(0, min(max_col, col)))


def _grid_cell_center(cell: tuple[int, int], terrain: TerrainGrid, cell_size_m: float) -> Point:
    min_x, min_y, max_x, max_y = _terrain_bounds(terrain)
    cell_size = max(float(cell_size_m), 1.0)
    row, col = cell
    x = min_x + (col + 0.5) * cell_size
    y = min_y + (row + 0.5) * cell_size
    return Point(max(min_x, min(max_x, x)), max(min_y, min(max_y, y)))


def _grid_distance_cells(a: tuple[int, int], b: tuple[int, int], metric: str) -> float:
    dr = abs(a[0] - b[0])
    dc = abs(a[1] - b[1])
    if metric == "manhattan":
        return float(dr + dc)
    if metric == "chebyshev":
        return float(max(dr, dc))
    return float((dr * dr + dc * dc) ** 0.5)


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
    """Grid-cell based scanned target detection.

    The detector first maps both observer and target to the configured detection
    grid.  Range, LOS, target terrain, and reported target position are then
    evaluated from those cells, not from sub-cell unit coordinates.  Downstream
    direct engagements and artillery WTA consume these ``DetectionRecord``
    objects, so the whole combat chain follows the same cell-level detection
    truth instead of mixing exact-distance and grid-cell logic.

    ``grid_metric`` controls the cell range gate.  ``chebyshev`` matches the
    square viewport scan grid, while ``euclidean``/``manhattan`` are available
    for experiments; default remains ``chebyshev`` because this is what the UI
    communicates visually.
    """

    unit_list = [u for u in units if u.is_alive() and (u.can_observe_at(now_s) or u.is_detectable_at(now_s))]
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
    grid_cell_size_m = max(1.0, float(detection_config.get("grid_cell_size_m", terrain.cell_size_m)))
    grid_metric = str(detection_config.get("grid_metric", "chebyshev")).lower()
    if grid_metric not in {"chebyshev", "euclidean", "manhattan"}:
        grid_metric = "chebyshev"

    min_x, min_y, max_x, max_y = terrain.bounds
    max_col = max(0, int(math.floor((max_x - min_x) / grid_cell_size_m)))
    max_row = max(0, int(math.floor((max_y - min_y) / grid_cell_size_m)))

    def cell_for_position(pos: Point) -> tuple[int, int]:
        col = int(math.floor((pos.x - min_x) / grid_cell_size_m))
        row = int(math.floor((pos.y - min_y) / grid_cell_size_m))
        return (max(0, min(max_row, row)), max(0, min(max_col, col)))

    def center_for_cell(cell: tuple[int, int]) -> Point:
        row, col = cell
        x = min_x + (col + 0.5) * grid_cell_size_m
        y = min_y + (row + 0.5) * grid_cell_size_m
        return Point(max(min_x, min(max_x, x)), max(min_y, min(max_y, y)))

    cell_by_unit = {u.id: cell_for_position(u.position) for u in unit_list}
    center_by_unit = {unit_id: center_for_cell(cell) for unit_id, cell in cell_by_unit.items()}

    out: Dict[tuple[str, str], DetectionRecord] = {}
    for observer in unit_list:
        # Only tanks and recon scan. Artillery fires on relayed
        # recon intel through HQ; command posts are relay nodes, not detectors.
        if not observer.can_observe_at(now_s):
            continue

        observer_cell = cell_by_unit[observer.id]
        observer_center = center_by_unit[observer.id]
        detection_range_cells = max(0.0, observer.detection_range_m / grid_cell_size_m)
        base_probability = float(base_by_kind.get(observer.kind.value, base_default))

        for target in unit_list:
            if observer.id == target.id or observer.side == target.side:
                continue
            if not target.is_detectable_at(now_s):
                continue

            target_cell = cell_by_unit[target.id]
            grid_distance_cells = _grid_distance_cells(observer_cell, target_cell, grid_metric)
            if grid_distance_cells > detection_range_cells:
                continue

            target_center = center_by_unit[target.id]
            d = _euclid(observer_center, target_center)

            cell = terrain.cells[terrain.rowcol_for_position(target_center)]
            los = terrain.line_of_sight(observer_center, target_center)
            terrain_factor = float(terrain_mod.get(cell.landform_name, 1.0))
            altitude_factor = float(altitude_mod.get(terrain.elevation_band(observer_center), 0.9))
            range_ratio = grid_distance_cells / max(detection_range_cells, 1.0)
            range_factor = max(0.0, 1.0 - range_ratio) ** range_decay_power
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
            # Same/adjacent grid-cell contact is close enough to be a deterministic
            # tactical sighting.  Longer range scans keep the probabilistic model.
            if probabilistic and grid_distance_cells > 1.0 and rng.random() > confidence:
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
                detector_cell=observer_cell,
                target_cell=target_cell,
                detector_cell_center=observer_center.as_tuple(),
                target_cell_center=target_center.as_tuple(),
                grid_cell_size_m=grid_cell_size_m,
                grid_distance_cells=grid_distance_cells,
                grid_metric=grid_metric,
            )
    return out
