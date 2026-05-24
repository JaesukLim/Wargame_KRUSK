"""Downsample the Prokhorovka geographic NPZ into a CSV at a coarser cell size.

The simulator's TerrainGrid.from_csv expects these columns:
    row, col, x_m, y_m, lat, lon, elev_m, slope_deg, roughness_m,
    local_relief_m, landform_code, landform_name, move_cost_infantry,
    move_cost_vehicle, water, rail, road, antitank_ditch

We aggregate B x B source cells (B=2 -> 100 m from 50 m) by:
- mean for continuous fields (elev/slope/roughness/relief/x/y/lat/lon)
- "any" for obstacle masks (forest dense, all waterway, tank-impassable waterway)
- mode for ESA WorldCover code

then derive landform_name and movement costs the same way TerrainGrid.from_npz
does, so behaviour matches the previous NPZ-backed run aside from resolution.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


CODE_FOR_NAME = {"plain": 0, "hill": 1, "mountain": 2, "water": 3, "forest": 4, "urban": 5}


def block_mean(arr: np.ndarray, new_rows: int, new_cols: int, b: int) -> np.ndarray:
    a = arr[: new_rows * b, : new_cols * b].astype(float)
    a = a.reshape(new_rows, b, new_cols, b)
    return np.nanmean(a, axis=(1, 3))


def block_any(arr: np.ndarray, new_rows: int, new_cols: int, b: int) -> np.ndarray:
    a = arr[: new_rows * b, : new_cols * b]
    a = a.reshape(new_rows, b, new_cols, b)
    return a.any(axis=(1, 3))


def block_mode_int(arr: np.ndarray, new_rows: int, new_cols: int, b: int) -> np.ndarray:
    a = arr[: new_rows * b, : new_cols * b]
    a = a.reshape(new_rows, b, new_cols, b)
    out = np.zeros((new_rows, new_cols), dtype=arr.dtype)
    for r in range(new_rows):
        for c in range(new_cols):
            block = a[r, :, c, :].ravel()
            vals, counts = np.unique(block, return_counts=True)
            out[r, c] = vals[int(np.argmax(counts))]
    return out


def classify(name_inputs: dict, r: int, c: int) -> tuple[str, int]:
    if name_inputs["water_impass"][r, c] or name_inputs["water_all"][r, c]:
        name = "water"
    elif name_inputs["forest"][r, c]:
        name = "forest"
    else:
        wc = int(name_inputs["worldcover"][r, c])
        if wc == 50:
            name = "urban"
        elif wc in (80, 90):
            name = "water"
        else:
            s = float(name_inputs["slope"][r, c])
            if s > 20.0:
                name = "mountain"
            elif s > 8.0:
                name = "hill"
            else:
                name = "plain"
    return name, CODE_FOR_NAME[name]


def move_cost_vehicle(name: str, slope_deg: float, water_impass: bool) -> float:
    if water_impass:
        # `water=True` in the CSV row already forces movement_cost -> inf; this
        # value is a sentinel that should never actually be used at runtime.
        return 99.0
    base = {
        "water": 3.0,
        "forest": 4.0,
        "urban": 1.4,
        "mountain": 2.5,
        "hill": 1.4,
        "plain": 1.0,
    }[name]
    return base * (1.0 + max(0.0, slope_deg - 5.0) * 0.05)


def move_cost_infantry(name: str, slope_deg: float, water_impass: bool) -> float:
    if water_impass:
        return 5.0
    base = {
        "water": 2.0,
        "forest": 1.5,
        "urban": 1.1,
        "mountain": 1.8,
        "hill": 1.2,
        "plain": 1.0,
    }[name]
    return base * (1.0 + max(0.0, slope_deg - 5.0) * 0.025)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="DEM_data_1/prokhorovka_geographic_data.npz")
    parser.add_argument("--output", default="DEM_data_1/prokhorovka_geographic_data_100m.csv")
    parser.add_argument(
        "--block-size",
        type=int,
        default=2,
        help="Aggregation block size in source cells. 2 -> 100 m from a 50 m grid.",
    )
    args = parser.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise FileNotFoundError(src)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    with np.load(src, allow_pickle=False) as d:
        x_m = np.asarray(d["x_m"], dtype=float)
        y_m = np.asarray(d["y_m"], dtype=float)
        lat = np.asarray(d["lat"], dtype=float)
        lon = np.asarray(d["lon"], dtype=float)
        elev = np.asarray(d["elev_m"], dtype=float)
        slope = np.asarray(d["slope_deg"], dtype=float)
        roughness = np.asarray(d["roughness_m"], dtype=float)
        relief = np.asarray(d["localReliefM"], dtype=float)
        worldcover = np.asarray(d["worldcoverCode"], dtype=np.int32)
        forest_mask = np.asarray(d["forestTankObstacleMask"], dtype=bool)
        water_all = np.asarray(d["allWaterwayMask"], dtype=bool)
        water_impass = np.asarray(d["tankImpassableWaterwayMask"], dtype=bool)

    b = max(1, args.block_size)
    n_rows, n_cols = elev.shape
    new_rows = n_rows // b
    new_cols = n_cols // b

    x_d = block_mean(x_m, new_rows, new_cols, b)
    y_d = block_mean(y_m, new_rows, new_cols, b)
    lat_d = block_mean(lat, new_rows, new_cols, b)
    lon_d = block_mean(lon, new_rows, new_cols, b)
    elev_d = block_mean(elev, new_rows, new_cols, b)
    slope_d = block_mean(slope, new_rows, new_cols, b)
    rough_d = block_mean(roughness, new_rows, new_cols, b)
    relief_d = block_mean(relief, new_rows, new_cols, b)
    wc_d = block_mode_int(worldcover, new_rows, new_cols, b)
    forest_d = block_any(forest_mask, new_rows, new_cols, b)
    water_all_d = block_any(water_all, new_rows, new_cols, b)
    water_impass_d = block_any(water_impass, new_rows, new_cols, b)

    # Fill NaN with safe defaults so the CSV does not contain 'nan'.
    elev_mean = float(np.nanmean(elev_d)) if np.isfinite(np.nanmean(elev_d)) else 0.0
    elev_d = np.where(np.isnan(elev_d), elev_mean, elev_d)
    slope_d = np.where(np.isnan(slope_d), 0.0, slope_d)
    rough_d = np.where(np.isnan(rough_d), 0.0, rough_d)
    relief_d = np.where(np.isnan(relief_d), 0.0, relief_d)
    lat_d = np.where(np.isnan(lat_d), 0.0, lat_d)
    lon_d = np.where(np.isnan(lon_d), 0.0, lon_d)

    name_inputs = {
        "worldcover": wc_d,
        "slope": slope_d,
        "forest": forest_d,
        "water_all": water_all_d,
        "water_impass": water_impass_d,
    }

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "row",
                "col",
                "x_m",
                "y_m",
                "lat",
                "lon",
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
            ]
        )
        for r in range(new_rows):
            for c in range(new_cols):
                name, code = classify(name_inputs, r, c)
                s_deg = float(slope_d[r, c])
                wi = bool(water_impass_d[r, c])
                w.writerow(
                    [
                        r + 1,
                        c + 1,
                        f"{float(x_d[r, c]):.3f}",
                        f"{float(y_d[r, c]):.3f}",
                        f"{float(lat_d[r, c]):.6f}",
                        f"{float(lon_d[r, c]):.6f}",
                        f"{float(elev_d[r, c]):.3f}",
                        f"{s_deg:.3f}",
                        f"{float(rough_d[r, c]):.3f}",
                        f"{float(relief_d[r, c]):.3f}",
                        code,
                        name,
                        f"{move_cost_infantry(name, s_deg, wi):.3f}",
                        f"{move_cost_vehicle(name, s_deg, wi):.3f}",
                        "true" if wi else "false",
                        "false",
                        "false",
                        "false",
                    ]
                )

    print(
        f"Wrote {out} : {new_rows} rows x {new_cols} cols = {new_rows * new_cols} cells, "
        f"block_size={b} (source {n_rows}x{n_cols})"
    )


if __name__ == "__main__":
    main()
