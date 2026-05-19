"""Terrain loading and terrain-aware movement utilities."""

from __future__ import annotations

import csv
import bisect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .types import Point


@dataclass(frozen=True)
class TerrainCell:
    row: int
    col: int
    x: float
    y: float
    elevation_m: float
    slope_deg: float
    roughness_m: float
    local_relief_m: float
    landform_code: int
    landform_name: str
    move_cost_infantry: float
    move_cost_vehicle: float
    water: bool
    road: bool = False
    rail: bool = False
    antitank_ditch: bool = False


@dataclass
class TerrainGrid:
    cells: Dict[tuple[int, int], TerrainCell]
    n_rows: int
    n_cols: int
    cell_size_m: float
    x0: float
    y0: float
    _x_values: List[float] = field(default_factory=list, repr=False)
    _y_values: List[float] = field(default_factory=list, repr=False)

    @classmethod
    def from_csv(cls, path: str | Path) -> "TerrainGrid":
        rows: Dict[tuple[int, int], TerrainCell] = {}
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)

        # utf-8-sig strips the BOM found in the provided DEM CSV header.
        with p.open("r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            required = {
                "row",
                "col",
                "x_m",
                "y_m",
                "elev_m",
                "slope_deg",
                "roughness_m",
                "local_relief_m",
                "landform_code",
                "landform_name",
                "move_cost_infantry",
                "move_cost_vehicle",
                "water",
                "rail",
                "road",
                "antitank_ditch",
            }
            if set(reader.fieldnames or {}) < required:
                raise ValueError(
                    f"Terrain csv missing required columns. Found: {reader.fieldnames}"
                )

            first_row = None
            last_row = None
            max_col = max_row = 0

            for row in reader:
                r = int(row["row"])
                c = int(row["col"])
                cell = TerrainCell(
                    row=r,
                    col=c,
                    x=float(row["x_m"]),
                    y=float(row["y_m"]),
                    elevation_m=float(row["elev_m"]),
                    slope_deg=float(row["slope_deg"]),
                    roughness_m=float(row["roughness_m"]),
                    local_relief_m=float(row["local_relief_m"]),
                    landform_code=int(row["landform_code"]),
                    landform_name=row["landform_name"],
                    move_cost_infantry=float(row["move_cost_infantry"]),
                    move_cost_vehicle=float(row["move_cost_vehicle"]),
                    water=row["water"].strip().lower() == "true",
                    rail=row["rail"].strip().lower() == "true",
                    road=row["road"].strip().lower() == "true",
                    antitank_ditch=row["antitank_ditch"].strip().lower() == "true",
                )
                rows[(r - 1, c - 1)] = cell
                first_row = first_row or (r, c)
                last_row = (r, c)
                max_row = max(max_row, r)
                max_col = max(max_col, c)

            if not rows:
                raise ValueError("Terrain csv is empty")

        # derive cell size by spacing in x values from first row
        # fallback to 250m if uncertain.
        cell_size = 250.0
        if first_row and last_row:
            sample_coords = [v for (k, v) in rows.items() if k[0] == 0]
            if len(sample_coords) >= 2:
                sample_coords.sort(key=lambda cv: cv.col)
                cell_size = abs(sample_coords[1].x - sample_coords[0].x)

        min_x = min(cell.x for cell in rows.values())
        min_y = min(cell.y for cell in rows.values())
        x_values = sorted({cell.x for cell in rows.values()})
        y_values = sorted({cell.y for cell in rows.values()})
        return cls(
            cells=rows,
            n_rows=max_row,
            n_cols=max_col,
            cell_size_m=cell_size,
            x0=min_x,
            y0=min_y,
            _x_values=x_values,
            _y_values=y_values,
        )

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        xs = [c.x for c in self.cells.values()]
        ys = [c.y for c in self.cells.values()]
        return (min(xs), min(ys), max(xs), max(ys))

    def rowcol_for_position(self, pos: Point) -> tuple[int, int]:
        """Return the nearest terrain cell.

        The DEM is a regular grid.  Keep this lookup cheap because movement,
        LOS, detection, and rendering call it many times per frame.
        """

        if not self.cells:
            raise ValueError("Empty terrain")

        def nearest_index(values: List[float], value: float) -> int:
            idx = bisect.bisect_left(values, value)
            if idx <= 0:
                return 0
            if idx >= len(values):
                return len(values) - 1
            before = values[idx - 1]
            after = values[idx]
            return idx - 1 if abs(value - before) <= abs(value - after) else idx

        col = nearest_index(self._x_values, pos.x)
        row = nearest_index(self._y_values, pos.y)
        return (row, col)

    def movement_cost(self, pos: Point, unit_class: str = "vehicle") -> float:
        r, c = self.rowcol_for_position(pos)
        cell = self.cells[(r, c)]
        if cell.water:
            return float("inf")
        if unit_class == "infantry":
            return max(0.0001, cell.move_cost_infantry)
        return max(0.0001, cell.move_cost_vehicle)

    def elevation_band(self, pos: Point) -> str:
        """Classify elevation as low/mid/high for detection modifiers."""

        cell = self.cells[self.rowcol_for_position(pos)]
        elevations = [c.elevation_m for c in self.cells.values()]
        lo = min(elevations)
        hi = max(elevations)
        if hi <= lo:
            return "mid"
        t = (cell.elevation_m - lo) / (hi - lo)
        if t < 0.33:
            return "low"
        if t < 0.66:
            return "mid"
        return "high"

    def line_of_sight(self, a: Point, b: Point, observer_height_m: float = 2.5, target_height_m: float = 2.5) -> bool:
        """Rough LOS model using sampled terrain profile.

        A sampled terrain point blocks sight if it rises above the straight line
        between observer eye height and target height.  This is intentionally
        simple, stable, and readable; it can later be swapped for a detailed
        viewshed routine without changing the simulation API.
        """

        steps = max(
            2,
            int(max(abs(a.x - b.x), abs(a.y - b.y)) / max(self.cell_size_m, 1.0) * 2),
        )
        if steps <= 1:
            return True
        a_cell = self.cells[self.rowcol_for_position(a)]
        b_cell = self.cells[self.rowcol_for_position(b)]
        h0 = a_cell.elevation_m + observer_height_m
        h1 = b_cell.elevation_m + target_height_m

        for i in range(1, steps):
            t = i / steps
            x = a.x + (b.x - a.x) * t
            y = a.y + (b.y - a.y) * t
            sample_cell = self.cells[self.rowcol_for_position(Point(x, y))]
            # A small clearance prevents tiny DEM noise from fully blocking LOS.
            expected_h = h0 + (h1 - h0) * t
            if sample_cell.elevation_m > expected_h + 1.5:
                return False
        return True

    def width_m(self) -> float:
        min_x, min_y, max_x, max_y = self.bounds
        return max_x - min_x

    def height_m(self) -> float:
        min_x, min_y, max_x, max_y = self.bounds
        return max_y - min_y

    def all_units(self) -> List[TerrainCell]:
        return list(self.cells.values())
