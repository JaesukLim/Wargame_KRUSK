"""High-level construction of battlefield and scenario loading utilities."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .battlefield import BattleField
from .config_loader import SimulationConfig, flatten_scenario, load_config
from .loader import parse_unit_definition
from .unit import reset_unit_ids
from .terrain import TerrainGrid


def build_battlefield(config_path: str | None = None, scenario_path: str | None = None) -> BattleField:
    cfg = load_config(config_path=config_path, scenario_path=scenario_path)
    return build_battlefield_from_config(cfg)


def build_battlefield_from_config(cfg: SimulationConfig) -> BattleField:
    scenario = flatten_scenario(cfg.raw)

    terrain_cfg = scenario.get("terrain", {})
    terrain_path = terrain_cfg.get("csv") or "DEM_data_1/prokhorovka_terrain_250m.csv"
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
    terrain = TerrainGrid.from_csv(terrain_path_obj)

    reset_unit_ids()
    bf = BattleField(terrain=terrain, config=cfg)
    units = [parse_unit_definition(u) for u in scenario.get("units", [])]
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
