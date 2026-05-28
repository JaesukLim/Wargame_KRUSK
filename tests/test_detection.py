import random

from wargame.core.battlefield import BattleField
from wargame.core.config_loader import SimulationConfig
from wargame.core.detection import detect_unit_targets
from wargame.core.terrain import TerrainCell, TerrainGrid
from wargame.core.types import Point, Side, UnitKind
from wargame.core.unit import Unit


def _plain_terrain(size: int = 4, cell_size: float = 100.0) -> TerrainGrid:
    cells = {}
    for row in range(size):
        for col in range(size):
            cells[(row, col)] = TerrainCell(
                row=row + 1,
                col=col + 1,
                x=col * cell_size,
                y=row * cell_size,
                lat=0.0,
                lon=0.0,
                elevation_m=0.0,
                slope_deg=0.0,
                roughness_m=0.0,
                local_relief_m=0.0,
                landform_code=1,
                landform_name="plain",
                move_cost_infantry=1.0,
                move_cost_vehicle=1.0,
                water=False,
            )
    return TerrainGrid(
        cells=cells,
        n_rows=size,
        n_cols=size,
        cell_size_m=cell_size,
        x0=0.0,
        y0=0.0,
        _x_values=[i * cell_size for i in range(size)],
        _y_values=[i * cell_size for i in range(size)],
        _min_elevation_m=0.0,
        _max_elevation_m=0.0,
    )


def _tank(unit_id: str, side: Side, x: float, y: float, detection_range_m: float) -> Unit:
    return Unit(
        id=unit_id,
        name=unit_id,
        side=side,
        kind=UnitKind.TANK,
        unit_type="T-34" if side == Side.RED else "Panzer IV",
        position=Point(x, y),
        strength=10.0,
        max_strength=10.0,
        speed_mps=0.0,
        detection_range_m=detection_range_m,
        command_range_m=1000.0,
        lanchester_range_m=1000.0,
    )


def test_detection_uses_grid_cells_not_exact_unit_distance() -> None:
    terrain = _plain_terrain()
    observer = _tank("observer", Side.BLUE, 10.0, 10.0, detection_range_m=150.0)
    # Exact unit distance is 180m, outside the observer's nominal 150m range,
    # but both units are only one 100m detection-grid cell apart.
    target = _tank("target", Side.RED, 190.0, 10.0, detection_range_m=0.0)

    detections = detect_unit_targets(
        [observer, target],
        terrain,
        {
            "grid_cell_size_m": 100.0,
            "grid_metric": "chebyshev",
            "probabilistic": False,
            "base_probability": 1.0,
            "min_confidence_to_report": 0.01,
        },
        now_s=0.0,
        rng=random.Random(1),
    )

    rec = detections[("observer", "target")]
    assert rec.detector_cell == (0, 0)
    assert rec.target_cell == (0, 1)
    assert rec.target_cell_center == (150.0, 50.0)
    assert rec.grid_distance_cells == 1.0


def test_detection_rejects_targets_outside_grid_cell_range() -> None:
    terrain = _plain_terrain()
    observer = _tank("observer", Side.BLUE, 10.0, 10.0, detection_range_m=150.0)
    target = _tank("target", Side.RED, 290.0, 10.0, detection_range_m=0.0)

    detections = detect_unit_targets(
        [observer, target],
        terrain,
        {
            "grid_cell_size_m": 100.0,
            "grid_metric": "chebyshev",
            "probabilistic": False,
            "base_probability": 1.0,
            "min_confidence_to_report": 0.01,
        },
        now_s=0.0,
        rng=random.Random(1),
    )

    assert ("observer", "target") not in detections


def test_direct_engagement_consumes_grid_cell_detection_record() -> None:
    terrain = _plain_terrain()
    blue = _tank("blue", Side.BLUE, 10.0, 10.0, detection_range_m=150.0)
    red = _tank("red", Side.RED, 190.0, 10.0, detection_range_m=0.0)
    blue.lanchester_kills = 0.001
    red.lanchester_kills = 0.001

    battlefield = BattleField(
        terrain=terrain,
        config=SimulationConfig(
            {
                "simulation": {
                    "random_seed": 1,
                    "detection": {
                        "grid_cell_size_m": 100.0,
                        "grid_metric": "chebyshev",
                        "probabilistic": False,
                        "base_probability": 1.0,
                        "min_confidence_to_report": 0.01,
                    },
                    "combat": {
                        "lanchester_range_m": 1000.0,
                        "default_k_attacker": 0.001,
                        "default_k_defender": 0.001,
                    },
                    "command": {},
                    "lanchester": {"kill_matrix": {}},
                }
            }
        ),
    )
    battlefield.seed_units([blue, red])

    result = battlefield.update(1.0)
    payload = battlefield.export_state(include_logs=False)

    assert result.active_contacts == 1
    assert payload["contacts"]
    assert payload["detections"][0]["target_cell"] == [0, 1]
    assert payload["detections"][0]["x"] == 150.0
    assert payload["detections"][0]["unit_x"] == 190.0


def test_tank_attacks_artillery_in_direct_contact() -> None:
    terrain = _plain_terrain()
    blue = _tank("blue", Side.BLUE, 10.0, 10.0, detection_range_m=250.0)
    blue.unit_type = "PzIV"
    red_artillery = Unit(
        id="red_gun",
        name="red_gun",
        side=Side.RED,
        kind=UnitKind.ARTILLERY,
        unit_type="M-30",
        position=Point(190.0, 10.0),
        strength=8.0,
        max_strength=8.0,
        speed_mps=0.0,
        detection_range_m=0.0,
        command_range_m=1000.0,
        lanchester_range_m=1000.0,
    )
    battlefield = BattleField(
        terrain=terrain,
        config=SimulationConfig(
            {
                "simulation": {
                    "random_seed": 1,
                    "detection": {
                        "grid_cell_size_m": 100.0,
                        "grid_metric": "chebyshev",
                        "probabilistic": False,
                        "base_probability": 1.0,
                        "min_confidence_to_report": 0.01,
                    },
                    "combat": {
                        "lanchester_range_m": 1000.0,
                        "default_k_attacker": 0.01,
                        "default_k_defender": 0.001,
                    },
                    "command": {},
                    "lanchester": {"kill_matrix": {}},
                }
            }
        ),
    )
    battlefield.seed_units([blue, red_artillery])

    battlefield.update(10.0)
    payload = battlefield.export_state(include_logs=False)

    artillery = next(unit for unit in payload["units"] if unit["id"] == "red_gun")
    assert payload["contacts"]
    assert artillery["strength"] < 8.0


def test_artillery_wta_aims_at_reported_detection_cell_center() -> None:
    terrain = _plain_terrain()
    artillery = Unit(
        id="artillery",
        name="artillery",
        side=Side.RED,
        kind=UnitKind.ARTILLERY,
        unit_type="gun",
        position=Point(0.0, 0.0),
        strength=1.0,
        max_strength=1.0,
        speed_mps=0.0,
        detection_range_m=0.0,
        command_range_m=1000.0,
        shell_range_m=2000.0,
        shell_speed_mps=500.0,
        shell_damage=1.0,
        shell_dispersion_m=50.0,
        fire_rate_per_min=6.0,
        ammo_remaining=10,
    )
    recon = Unit(
        id="recon",
        name="recon",
        side=Side.RED,
        kind=UnitKind.RECON,
        unit_type="Recon",
        position=Point(10.0, 10.0),
        strength=1.0,
        max_strength=1.0,
        speed_mps=0.0,
        detection_range_m=150.0,
        command_range_m=1000.0,
    )
    target = _tank("target", Side.BLUE, 190.0, 10.0, detection_range_m=0.0)
    battlefield = BattleField(
        terrain=terrain,
        config=SimulationConfig(
            {
                "simulation": {
                    "random_seed": 1,
                    "detection": {
                        "grid_cell_size_m": 100.0,
                        "grid_metric": "chebyshev",
                        "probabilistic": False,
                        "base_probability": 1.0,
                        "min_confidence_to_report": 0.01,
                    },
                    "combat": {"lanchester_range_m": 0.0},
                    "command": {"require_hq_for_artillery_tasking": False},
                    "lanchester": {"kill_matrix": {}},
                }
            }
        ),
    )
    battlefield.seed_units([artillery, recon, target])

    battlefield.update(1.0)
    payload = battlefield.export_state(include_logs=False)

    assert payload["fire_missions"][0]["target"] == (150.0, 50.0)
    assert payload["fire_missions"][0]["target_cell"] == [0, 1]
    assert payload["shells"][0]["target"] == (150.0, 50.0)
