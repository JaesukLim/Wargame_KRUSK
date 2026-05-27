"""High-level construction of battlefield and scenario loading utilities."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any

from .battlefield import BattleField
from .config_loader import SimulationConfig, flatten_scenario, load_config
from .loader import parse_unit_definition
from .types import MovementPath, Point, Side, UnitKind
from .unit import Unit, reset_unit_ids
from .terrain import TerrainGrid


# Hardcoded objectives. RED attacks toward the center of the BLUE spawn
# (southwest), BLUE attacks toward the top-right of the playbox (northeast).
RED_DESTINATION = Point(2700.0, 3950.0)
BLUE_DESTINATION = Point(12000.0, 15000.0)

# Lateral spread (perpendicular to advance) and along-axis jitter applied to
# the single midway waypoint. Tuned to ~10% of the playbox width so units form
# a visible flanking arc without leaving the map.
WAYPOINT_LATERAL_SCATTER_M = 1500.0
WAYPOINT_ALONG_SCATTER_M = 500.0


def _assign_team_route(unit: Unit, rng: random.Random) -> None:
    """Replace a tank's waypoint list with [scattered_midpoint, team_destination].

    The midpoint is offset perpendicular to the line of advance so units fan
    out across the front instead of converging on a single attack axis.
    """

    dest = RED_DESTINATION if unit.side == Side.RED else BLUE_DESTINATION
    dx = dest.x - unit.position.x
    dy = dest.y - unit.position.y
    norm = math.hypot(dx, dy) or 1.0
    perp_x, perp_y = -dy / norm, dx / norm
    lateral = rng.uniform(-WAYPOINT_LATERAL_SCATTER_M, WAYPOINT_LATERAL_SCATTER_M)
    along = rng.uniform(-WAYPOINT_ALONG_SCATTER_M, WAYPOINT_ALONG_SCATTER_M)
    mx = (unit.position.x + dest.x) / 2.0 + perp_x * lateral + (dx / norm) * along
    my = (unit.position.y + dest.y) / 2.0 + perp_y * lateral + (dy / norm) * along
    unit.movement_path = MovementPath(waypoints=[Point(mx, my), dest], loop=False)


def build_battlefield(config_path: str | None = None, scenario_path: str | None = None) -> BattleField:
    cfg = load_config(config_path=config_path, scenario_path=scenario_path)
    return build_battlefield_from_config(cfg)


def build_battlefield_from_config(cfg: SimulationConfig) -> BattleField:
    scenario = flatten_scenario(cfg.raw)

    terrain_cfg = scenario.get("terrain", {})
    terrain_path = (
        terrain_cfg.get("npz")
        or terrain_cfg.get("csv")
        or "DEM_data_1/prokhorovka_terrain_250m.csv"
    )
    terrain_path_obj = Path(terrain_path)
    if not terrain_path_obj.is_absolute() and not terrain_path_obj.exists():
        # PyInstaller extracts --add-data files under sys._MEIPASS.
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            bundled = Path(bundle_root) / terrain_path_obj
            if bundled.exists():
                terrain_path_obj = bundled
        if not terrain_path_obj.exists():
            repo_root = Path(__file__).resolve().parents[3]
            terrain_path_obj = repo_root / terrain_path_obj
    if terrain_path_obj.suffix.lower() == ".npz":
        terrain = TerrainGrid.from_npz(terrain_path_obj)
    else:
        terrain = TerrainGrid.from_csv(terrain_path_obj)

    reset_unit_ids()
    bf = BattleField(terrain=terrain, config=cfg)
    units = [parse_unit_definition(u) for u in scenario.get("units", [])]

    route_seed = int(cfg.get("simulation", "random_seed", default=19430712))
    route_rng = random.Random(route_seed)

    auto_assign_tank_routes = bool(
        cfg.get("simulation", "scenario", "auto_assign_tank_routes", default=True)
    )

    for unit in units:
        if unit.kind != UnitKind.TANK:
            continue

        # If the scenario file already provides a path, preserve it.
        # This is required for historical scenarios where unit routes are part of the scenario.
        has_scenario_path = bool(unit.movement_path.waypoints)

        # Only generate a synthetic route when the scenario does not provide one.
        if auto_assign_tank_routes and not has_scenario_path:
            _assign_team_route(unit, route_rng)

    # Override detection ranges from the cell-based config table.
    # detection_range_m = cells * grid_cell_size_m, keyed by (kind, side).
    # Kinds absent from the table (artillery/command) keep their scenario meters.
    det_cfg = cfg.get("simulation", "detection", default={}) or {}
    range_cells = det_cfg.get("detection_range_cells", {})
    cell_size = float(det_cfg.get("grid_cell_size_m", 250.0))
    for unit in units:
        by_side = range_cells.get(unit.kind.value)
        if not by_side:
            continue
        cells = by_side.get(unit.side.value)
        if cells is not None:
            unit.detection_range_m = float(cells) * cell_size

    bf.seed_units(units)
    return bf


def run_headless_step(
    bf: BattleField,
    duration_s: float,
    dt: float,
) -> list[dict[str, Any]]:
    history = []
    t = 0.0
    while t < duration_s and bf.alive_units():
        result = bf.update(dt)
        t += dt
        if int(t * 10) != int((t - dt) * 10):
            history.append(
                {
                    "time_s": result.time_s,
                    "red_strength": result.red_strength,
                    "blue_strength": result.blue_strength,
                    "active_units": result.active_units,
                    "active_contacts": result.active_contacts,
                }
            )
    return history
