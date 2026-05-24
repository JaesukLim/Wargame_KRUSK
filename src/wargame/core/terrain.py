"""Terrain loading and terrain-aware movement utilities."""

from __future__ import annotations

import csv
import bisect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .types import Point


# Speed multiplier applied to a unit's base speed when traversing a cell.
# Effective movement cost (the divisor used in battlefield.py) is 1 / multiplier.
SPEED_MULT_BY_LANDFORM: Dict[str, float] = {
    "plain": 1.0,
    "hill": 0.8,
    "forest": 0.7,
    "water": 0.2,
    "urban": 1.0,
    "mountain": 0.5,
}
RIVER_SPEED_MULT = 0.2


@dataclass(frozen=True)
class TerrainCell:
    row: int
    col: int
    x: float
    y: float
    lat: float
    lon: float
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
    _min_elevation_m: float = field(default=0.0, repr=False)
    _max_elevation_m: float = field(default=0.0, repr=False)

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
                    lat=float(row.get("lat", 0.0)),
                    lon=float(row.get("lon", 0.0)),
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
        elevations = [cell.elevation_m for cell in rows.values()]
        return cls(
            cells=rows,
            n_rows=max_row,
            n_cols=max_col,
            cell_size_m=cell_size,
            x0=min_x,
            y0=min_y,
            _x_values=x_values,
            _y_values=y_values,
            _min_elevation_m=min(elevations),
            _max_elevation_m=max(elevations),
        )

    @classmethod
    def from_npz(cls, path: str | Path) -> "TerrainGrid":
        """Load terrain from a packaged DEM + ESA WorldCover + OSM waterway NPZ.

        The NPZ stores 2D arrays (rows x cols) for x_m, y_m, elev_m, slope_deg,
        roughness_m, localReliefM, plus boolean masks (forestTankObstacleMask,
        allWaterwayMask, tankImpassableWaterwayMask, smallWaterwayMask) and a
        per-cell ESA WorldCover class code.  We collapse these layers into the
        existing TerrainCell schema so the rest of the simulation does not need
        to change.
        """

        import numpy as np

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)

        with np.load(p, allow_pickle=False) as d:
            x_m = np.asarray(d["x_m"], dtype=float)
            y_m = np.asarray(d["y_m"], dtype=float)
            lat = np.asarray(d["lat"], dtype=float) if "lat" in d.files else np.zeros_like(x_m)
            lon = np.asarray(d["lon"], dtype=float) if "lon" in d.files else np.zeros_like(x_m)
            elev = np.asarray(d["elev_m"], dtype=float)
            slope = np.asarray(d["slope_deg"], dtype=float) if "slope_deg" in d.files else np.zeros_like(x_m)
            roughness = np.asarray(d["roughness_m"], dtype=float) if "roughness_m" in d.files else np.zeros_like(x_m)
            relief = (
                np.asarray(d["localReliefM"], dtype=float)
                if "localReliefM" in d.files
                else np.asarray(d["local_relief_m"], dtype=float)
                if "local_relief_m" in d.files
                else np.zeros_like(x_m)
            )
            worldcover = (
                np.asarray(d["worldcoverCode"], dtype=int)
                if "worldcoverCode" in d.files
                else np.zeros(x_m.shape, dtype=int)
            )
            forest_mask = (
                np.asarray(d["forestTankObstacleMask"], dtype=bool)
                if "forestTankObstacleMask" in d.files
                else np.asarray(d.get("forestDenseMask", np.zeros(x_m.shape, dtype=bool)), dtype=bool)
            )
            water_all = (
                np.asarray(d["allWaterwayMask"], dtype=bool)
                if "allWaterwayMask" in d.files
                else np.zeros(x_m.shape, dtype=bool)
            )
            water_impass = (
                np.asarray(d["tankImpassableWaterwayMask"], dtype=bool)
                if "tankImpassableWaterwayMask" in d.files
                else water_all
            )

        if elev.ndim != 2:
            raise ValueError(f"NPZ elev_m must be 2D, got shape {elev.shape}")
        n_rows, n_cols = elev.shape

        # Fill NaNs in DEM-derived arrays with safe defaults so units that
        # happen to step into edge cells do not break elevation/slope lookups.
        elev_mean = float(np.nanmean(elev)) if np.isfinite(np.nanmean(elev)) else 0.0
        elev = np.where(np.isnan(elev), elev_mean, elev)
        slope = np.where(np.isnan(slope), 0.0, slope)
        roughness = np.where(np.isnan(roughness), 0.0, roughness)
        relief = np.where(np.isnan(relief), 0.0, relief)

        # Infer cell size from the first-row x spacing; fall back to 50m.
        if n_cols >= 2:
            cell_size = float(abs(x_m[0, 1] - x_m[0, 0]))
        elif n_rows >= 2:
            cell_size = float(abs(y_m[1, 0] - y_m[0, 0]))
        else:
            cell_size = 50.0

        landform_name_for_code = {
            0: "plain",
            1: "hill",
            2: "mountain",
            3: "water",
            4: "forest",
            5: "urban",
        }
        # Reverse map used when we need to assign a code from the chosen name.
        code_for_name = {v: k for k, v in landform_name_for_code.items()}

        def classify(r: int, c: int) -> tuple[str, int]:
            if bool(water_impass[r, c]) or bool(water_all[r, c]):
                name = "water"
            elif bool(forest_mask[r, c]):
                name = "forest"
            else:
                wc = int(worldcover[r, c])
                if wc == 50:
                    name = "urban"
                elif wc == 80 or wc == 90:
                    name = "water"
                else:
                    s = float(slope[r, c])
                    if s > 20.0:
                        name = "mountain"
                    elif s > 8.0:
                        name = "hill"
                    else:
                        name = "plain"
            return name, code_for_name[name]

        def move_cost_vehicle(r: int, c: int, name: str) -> float:
            if bool(water_impass[r, c]):
                return float("inf")
            if name == "water":
                base = 3.0
            elif name == "forest":
                base = 4.0
            elif name == "urban":
                base = 1.4
            elif name == "mountain":
                base = 2.5
            elif name == "hill":
                base = 1.4
            else:
                base = 1.0
            s = float(slope[r, c])
            slope_mult = 1.0 + max(0.0, s - 5.0) * 0.05
            return base * slope_mult

        def move_cost_infantry(r: int, c: int, name: str) -> float:
            if bool(water_impass[r, c]):
                return 5.0
            if name == "water":
                base = 2.0
            elif name == "forest":
                base = 1.5
            elif name == "urban":
                base = 1.1
            elif name == "mountain":
                base = 1.8
            elif name == "hill":
                base = 1.2
            else:
                base = 1.0
            s = float(slope[r, c])
            slope_mult = 1.0 + max(0.0, s - 5.0) * 0.025
            return base * slope_mult

        cells: Dict[tuple[int, int], TerrainCell] = {}
        for r in range(n_rows):
            for c in range(n_cols):
                name, code = classify(r, c)
                cell = TerrainCell(
                    row=r + 1,
                    col=c + 1,
                    x=float(x_m[r, c]),
                    y=float(y_m[r, c]),
                    lat=float(lat[r, c]),
                    lon=float(lon[r, c]),
                    elevation_m=float(elev[r, c]),
                    slope_deg=float(slope[r, c]),
                    roughness_m=float(roughness[r, c]),
                    local_relief_m=float(relief[r, c]),
                    landform_code=code,
                    landform_name=name,
                    move_cost_infantry=max(0.0001, move_cost_infantry(r, c, name)),
                    move_cost_vehicle=max(0.0001, move_cost_vehicle(r, c, name)),
                    water=bool(water_impass[r, c]),
                    road=False,
                    rail=False,
                    antitank_ditch=False,
                )
                cells[(r, c)] = cell

        # Unique sorted axis values — used by rowcol_for_position bisect lookup.
        x_values = sorted({float(v) for v in np.unique(x_m).tolist()})
        y_values = sorted({float(v) for v in np.unique(y_m).tolist()})

        return cls(
            cells=cells,
            n_rows=n_rows,
            n_cols=n_cols,
            cell_size_m=cell_size,
            x0=float(x_m.min()),
            y0=float(y_m.min()),
            _x_values=x_values,
            _y_values=y_values,
            _min_elevation_m=float(elev.min()),
            _max_elevation_m=float(elev.max()),
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
            return 1.0 / RIVER_SPEED_MULT
        mult = SPEED_MULT_BY_LANDFORM.get(cell.landform_name, 1.0)
        return 1.0 / max(mult, 0.0001)

    def elevation_band(self, pos: Point) -> str:
        """Classify elevation as low/mid/high for detection modifiers."""

        cell = self.cells[self.rowcol_for_position(pos)]
        lo = self._min_elevation_m
        hi = self._max_elevation_m
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

    def export_payload(self) -> dict:
        """Return compact terrain data for Godot 3D mesh generation.

        The CSV has only ~2k cells, so a full localhost payload keeps the Godot
        client independent from Python file paths and allows standalone UI
        packaging to request terrain from the backend at runtime.
        """

        slopes = [cell.slope_deg for cell in self.cells.values()]
        min_elev = self._min_elevation_m
        max_elev = self._max_elevation_m
        cells = [
            {
                "row": cell.row,
                "col": cell.col,
                "x": cell.x,
                "y": cell.y,
                "elevation_m": cell.elevation_m,
                "slope_deg": cell.slope_deg,
                "roughness_m": cell.roughness_m,
                "local_relief_m": cell.local_relief_m,
                "landform": cell.landform_name,
                "water": cell.water,
                "road": cell.road,
                "rail": cell.rail,
                "antitank_ditch": cell.antitank_ditch,
                "move_cost_vehicle": cell.move_cost_vehicle,
            }
            for cell in sorted(self.cells.values(), key=lambda c: (c.row, c.col))
        ]
        return {
            "bounds": list(self.bounds),
            "width_m": self.width_m(),
            "height_m": self.height_m(),
            "rows": self.n_rows,
            "cols": self.n_cols,
            "cell_size_m": self.cell_size_m,
            "min_elevation_m": min_elev,
            "max_elevation_m": max_elev,
            "min_slope_deg": min(slopes),
            "max_slope_deg": max(slopes),
            "cells": cells,
        }
