#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geographic_data16_load_existing_npz_keep_preview.py

목적
----
이미 생성된 Prokhorovka 지형 NPZ 파일을 불러와서, 추가 다운로드 없이
이동논리 모델 입력용 NPZ와 기존 스타일의 검토 그림을 다시 생성합니다.

핵심 변경점
----------
1) DEM / ESA WorldCover / OSM Overpass를 새로 다운로드하지 않음
2) 하천의 전차 통과 가능/불가능 판단은 이동논리 모델에서 처리하도록,
   최종 모델 입력에는 allWaterwayMask와 OSM 원본 vector만 중심으로 저장
3) 다만 그림에서는 기존처럼 하천을 빠뜨리지 않기 위해 OSM vector line을 그대로 그림
   - major/display waterway: 진한 파란색
   - minor/other waterway: 옅은 파란색
4) 기존 raster mask만 그려서 하천이 계단형/누락처럼 보이는 문제를 피함

입력 후보
---------
- data9/prokhorovka_terrain/prokhorovka_geographic_data.npz
- data9/prokhorovka_terrain/prokhorovka_geographic_data_50m_dem_forest_waterways.npz
- data9/prokhorovka_terrain/prokhorovka_terrain_teamshare_50m_dem_forest_waterways.npz
- 현재 폴더 또는 /mnt/data의 동일 파일명

출력
----
data9/prokhorovka_terrain/
    prokhorovka_geographic_data_model_input.npz
    prokhorovka_geographic_data_model_input_summary.txt
    prokhorovka_geographic_data_model_input_preview.png

사용 예
------
python geographic_data16_load_existing_npz_keep_preview.py --input prokhorovka_geographic_data.npz
python geographic_data16_load_existing_npz_keep_preview.py --input prokhorovka_geographic_data.npz --forest-threshold 0.80 --copy-canonical
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

R_EARTH = 6_371_008.8
DEFAULT_OUT_DIR = Path("data9") / "prokhorovka_terrain"


def _candidate_files() -> list[Path]:
    return [
        Path("data9") / "prokhorovka_terrain" / "prokhorovka_geographic_data.npz",
        Path("data9") / "prokhorovka_terrain" / "prokhorovka_geographic_data_50m_dem_forest_waterways.npz",
        Path("data9") / "prokhorovka_terrain" / "prokhorovka_terrain_teamshare_50m_dem_forest_waterways.npz",
        Path("prokhorovka_geographic_data.npz"),
        Path("prokhorovka_geographic_data_50m_dem_forest_waterways.npz"),
        Path("prokhorovka_terrain_teamshare_50m_dem_forest_waterways.npz"),
        Path("/mnt/data/prokhorovka_geographic_data.npz"),
        Path("/mnt/data/prokhorovka_terrain_teamshare_50m_dem_forest_waterways.npz"),
    ]


def find_input_file(user_input: str | None) -> Path:
    if user_input:
        p = Path(user_input)
        if p.is_dir():
            for name in [
                "prokhorovka_geographic_data.npz",
                "prokhorovka_geographic_data_50m_dem_forest_waterways.npz",
                "prokhorovka_terrain_teamshare_50m_dem_forest_waterways.npz",
            ]:
                cand = p / name
                if cand.is_file():
                    return cand
            raise FileNotFoundError(f"입력 폴더 안에서 지형 NPZ 파일을 찾지 못했습니다: {p}")
        if p.is_file():
            return p
        raise FileNotFoundError(f"입력 파일을 찾지 못했습니다: {p}")

    for cand in _candidate_files():
        if cand.is_file():
            return cand
    raise FileNotFoundError(
        "지형 NPZ 파일을 자동으로 찾지 못했습니다. --input으로 직접 지정해 주세요."
    )


def read_npz(input_file: Path) -> Dict[str, np.ndarray]:
    with np.load(input_file, allow_pickle=False) as d:
        return {k: d[k] for k in d.files}


def json_from_scalar_array(value: np.ndarray | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def required_array(data: Dict[str, np.ndarray], key: str) -> np.ndarray:
    if key not in data:
        raise KeyError(f"입력 NPZ에 필요한 key가 없습니다: {key}")
    return np.asarray(data[key])


def first_available(data: Dict[str, np.ndarray], keys: Iterable[str], fallback: np.ndarray) -> np.ndarray:
    for key in keys:
        if key in data:
            return np.asarray(data[key])
    return fallback


def infer_grid_cell_m(x_m: np.ndarray, y_m: np.ndarray, metadata_old: dict) -> int:
    if isinstance(metadata_old, dict):
        for key in ["grid_cell_m", "gridCellM"]:
            try:
                val = int(metadata_old.get(key, 0))
                if val > 0:
                    return val
            except Exception:
                pass
    if x_m.ndim == 2 and x_m.shape[1] > 1:
        return int(round(float(np.nanmedian(np.diff(x_m[0, :])))))
    if y_m.ndim == 2 and y_m.shape[0] > 1:
        return int(round(float(np.nanmedian(np.diff(y_m[:, 0])))))
    return -1


def build_dataset(data: Dict[str, np.ndarray], input_file: Path, forest_threshold: float) -> Dict[str, np.ndarray]:
    x_m = required_array(data, "x_m")
    y_m = required_array(data, "y_m")
    lat = required_array(data, "lat")
    lon = required_array(data, "lon")
    elev_m = required_array(data, "elev_m")
    forest_ratio = required_array(data, "forestRatio").astype(float)
    all_waterway = required_array(data, "allWaterwayMask").astype(bool)

    if elev_m.shape != forest_ratio.shape or elev_m.shape != all_waterway.shape:
        raise ValueError(
            "elev_m, forestRatio, allWaterwayMask의 shape이 서로 다릅니다.\n"
            f"elev_m={elev_m.shape}, forestRatio={forest_ratio.shape}, allWaterwayMask={all_waterway.shape}"
        )

    forest_dense = forest_ratio >= forest_threshold

    # 그림 재현용 display layer. 이동논리에는 강제 사용하지 않습니다.
    # 기존 파일에 major/minor 분리 mask가 있으면 이름을 바꿔 visualization-only로 보존합니다.
    major_display = first_available(
        data,
        ["majorWaterwayDisplayMask", "tankImpassableWaterwayMask"],
        np.zeros_like(all_waterway, dtype=bool),
    ).astype(bool)
    minor_display = first_available(
        data,
        ["minorWaterwayDisplayMask", "smallWaterwayMask"],
        all_waterway & ~major_display,
    ).astype(bool)
    # 전체 하천과 모순되지 않게 정리
    major_display = major_display & all_waterway
    minor_display = minor_display & all_waterway & ~major_display

    metadata_old = json_from_scalar_array(data.get("metadata_json"), default={})
    bounds = metadata_old.get("bounds", {}) if isinstance(metadata_old, dict) else {}
    grid_cell_m = infer_grid_cell_m(x_m, y_m, metadata_old if isinstance(metadata_old, dict) else {})

    metadata = {
        "name": "Prokhorovka geographic data for movement/model input",
        "source_file": str(input_file),
        "description": (
            "Loaded from an existing NPZ file. No DEM/WorldCover/OSM download was performed. "
            "Waterway passability is not classified in the movement-input fields. "
            "Major/minor waterway display masks, when present, are kept only for plotting/QA."
        ),
        "bounds": bounds,
        "grid_cell_m": grid_cell_m,
        "n_rows": int(elev_m.shape[0]),
        "n_cols": int(elev_m.shape[1]),
        "forest_source": metadata_old.get("forest_source", "ESA WorldCover class 10 Tree cover") if isinstance(metadata_old, dict) else "ESA WorldCover class 10 Tree cover",
        "forest_dense_rule": f"forestRatio >= {forest_threshold:.3f}",
        "waterway_note": "allWaterwayMask stores waterway existence. Movement/passability effects must be handled by the movement-logic model.",
        "display_layer_note": "majorWaterwayDisplayMask/minorWaterwayDisplayMask are retained only to reproduce the previous review figure style.",
        "primary_model_arrays": [
            "x_m", "y_m", "lat", "lon", "elev_m", "slope_deg", "roughness_m", "localReliefM",
            "forestRatio", "forestDenseMask", "allWaterwayMask", "osm_all_waterway_features_json"
        ],
    }

    osm_all_json = str(data.get("osm_all_waterway_features_json", np.array("[]")))
    # 입력에 이전 major feature json이 있으면 figure 재현용으로만 보존합니다.
    osm_major_json = str(data.get("osm_impassable_waterway_features_json", np.array("[]")))

    return {
        "metadata_json": np.array(json.dumps(metadata, ensure_ascii=False, indent=2)),
        "osm_all_waterway_features_json": np.array(osm_all_json),
        "osm_major_waterway_display_features_json": np.array(osm_major_json),
        "x_m": x_m,
        "y_m": y_m,
        "lat": lat,
        "lon": lon,
        "elev_m": elev_m,
        "slope_deg": first_available(data, ["slope_deg"], np.full_like(elev_m, np.nan, dtype=float)),
        "aspect_rad": first_available(data, ["aspect_rad"], np.full_like(elev_m, np.nan, dtype=float)),
        "roughness_m": first_available(data, ["roughness_m"], np.full_like(elev_m, np.nan, dtype=float)),
        "localReliefM": first_available(data, ["localReliefM", "local_relief_m"], np.full_like(elev_m, np.nan, dtype=float)),
        "worldcoverCode": first_available(data, ["worldcoverCode"], np.zeros_like(elev_m, dtype=np.uint8)),
        "forestRatio": forest_ratio,
        "forestDenseMask": forest_dense,
        "forestPixelCount10m": first_available(data, ["forestPixelCount10m"], np.zeros_like(elev_m, dtype=np.int32)),
        "validPixelCount10m": first_available(data, ["validPixelCount10m"], np.zeros_like(elev_m, dtype=np.int32)),
        "allWaterwayMask": all_waterway,
        # 아래 두 개는 이동판정용이 아니라 기존 그림 재현/검토용입니다.
        "majorWaterwayDisplayMask": major_display,
        "minorWaterwayDisplayMask": minor_display,
    }


def save_dataset(dataset: Dict[str, np.ndarray], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_file, **dataset)
    print(f"Saved model-input NPZ: {output_file}")


def write_summary(dataset: Dict[str, np.ndarray], output_file: Path, input_file: Path) -> None:
    meta = json.loads(str(dataset["metadata_json"]))
    elev = dataset["elev_m"]
    forest_ratio = dataset["forestRatio"]
    forest_dense = dataset["forestDenseMask"]
    all_water = dataset["allWaterwayMask"]
    major_display = dataset["majorWaterwayDisplayMask"]
    minor_display = dataset["minorWaterwayDisplayMask"]

    lines = [
        "Prokhorovka geographic model-input data summary",
        "=" * 72,
        f"Input file        : {input_file}",
        f"Output grid       : {meta['n_rows']} rows x {meta['n_cols']} cols",
        f"Grid cell         : {meta['grid_cell_m']} m",
        f"Forest rule       : {meta['forest_dense_rule']}",
        "Waterway rule     : allWaterwayMask only; passability is not classified here",
        "Display note      : major/minor waterway display masks are for figure reproduction only",
        "",
        f"Elevation min/mean/max [m] : {np.nanmin(elev):.2f} / {np.nanmean(elev):.2f} / {np.nanmax(elev):.2f}",
        f"Forest ratio mean/max      : {np.nanmean(forest_ratio):.3f} / {np.nanmax(forest_ratio):.3f}",
        f"Dense forest cells         : {int(np.sum(forest_dense))}",
        f"All waterway cells         : {int(np.sum(all_water))}",
        f"Major display water cells  : {int(np.sum(major_display))}",
        f"Minor display water cells  : {int(np.sum(minor_display))}",
        "",
        "Stored arrays",
        "-------------",
    ]
    for key, arr in dataset.items():
        lines.append(f"{key:42s} shape={arr.shape!s:12s} dtype={arr.dtype}")
    output_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved summary: {output_file}")


def latlon_to_xy_m(lat: np.ndarray, lon: np.ndarray, dataset: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    lat_grid = dataset["lat"]
    lon_grid = dataset["lon"]
    lat0 = float(np.nanmean(lat_grid))
    west = float(np.nanmin(lon_grid))
    south = float(np.nanmin(lat_grid))
    x = R_EARTH * np.cos(np.deg2rad(lat0)) * np.deg2rad(lon - west)
    y = R_EARTH * np.deg2rad(lat - south)
    return x, y


def is_psel_like(feature: dict) -> bool:
    text = " ".join(str(v).lower() for v in feature.values() if not isinstance(v, (list, dict)))
    tags = feature.get("tags", {})
    if isinstance(tags, dict):
        text += " " + " ".join(str(v).lower() for v in tags.values())
    return any(k in text for k in ["psel", "псел", "псёл", "psiol", "psyol"])


def parse_feature_json(value: np.ndarray | str | None) -> List[dict]:
    if value is None:
        return []
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def make_preview(dataset: Dict[str, np.ndarray], output_file: Path) -> None:
    x_km = dataset["x_m"] / 1000.0
    y_km = dataset["y_m"] / 1000.0
    elev = dataset["elev_m"].astype(float)
    forest = dataset["forestDenseMask"].astype(float)

    fig, ax = plt.subplots(figsize=(10, 8))
    cs = ax.contour(x_km, y_km, elev, levels=15, colors="0.35", linewidths=0.75, alpha=0.85)
    ax.clabel(cs, inline=True, fontsize=8, fmt="%.0f m")

    extent = [float(np.nanmin(x_km)), float(np.nanmax(x_km)), float(np.nanmin(y_km)), float(np.nanmax(y_km))]
    forest_img = np.where(forest > 0.5, 1.0, np.nan)
    ax.imshow(
        forest_img,
        origin="lower",
        extent=extent,
        cmap="Greens",
        vmin=0,
        vmax=1,
        alpha=0.50,
        interpolation="nearest",
        zorder=3,
    )

    # 우선 OSM vector JSON을 사용해 기존 그림처럼 선형 하천을 그림.
    all_features = parse_feature_json(dataset.get("osm_all_waterway_features_json"))
    major_features = parse_feature_json(dataset.get("osm_major_waterway_display_features_json"))
    major_ids = {str(f.get("id")) for f in major_features}

    plotted_vector = False
    if all_features:
        # minor 먼저, major 나중에 그림
        for draw_major in [False, True]:
            for feat in all_features:
                fid = str(feat.get("id"))
                is_major = fid in major_ids
                if is_major != draw_major:
                    continue
                lat = np.asarray(feat.get("lat", []), dtype=float)
                lon = np.asarray(feat.get("lon", []), dtype=float)
                if lat.size < 2 or lon.size < 2:
                    continue
                x_m, y_m = latlon_to_xy_m(lat, lon, dataset)
                if is_major:
                    color = "#003B7A" if is_psel_like(feat) else "#0057B8"
                    lw = 3.2 if is_psel_like(feat) else 2.6
                    alpha = 0.96
                    zorder = 8
                else:
                    color = "#7CCCF2"
                    lw = 1.15
                    alpha = 0.62
                    zorder = 6
                ax.plot(x_m / 1000.0, y_m / 1000.0, color=color, linewidth=lw, alpha=alpha, solid_capstyle="round", zorder=zorder)
                plotted_vector = True

    # vector가 없으면 raster display mask로 fallback.
    if not plotted_vector:
        minor = np.where(dataset["minorWaterwayDisplayMask"].astype(bool), 1.0, np.nan)
        major = np.where(dataset["majorWaterwayDisplayMask"].astype(bool), 1.0, np.nan)
        if np.all(np.isnan(minor)) and np.all(np.isnan(major)):
            major = np.where(dataset["allWaterwayMask"].astype(bool), 1.0, np.nan)
        ax.imshow(minor, origin="lower", extent=extent, cmap="Blues", vmin=0, vmax=1, alpha=0.35, interpolation="nearest", zorder=4)
        ax.imshow(major, origin="lower", extent=extent, cmap="Blues", vmin=0, vmax=1, alpha=0.75, interpolation="nearest", zorder=5)

    ax.set_title(
        "Loaded Geographic Data Preview\nDEM contours + dense forest mask + OSM waterway vectors",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("East from SW corner [km]")
    ax.set_ylabel("North from SW corner [km]")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.35)
    ax.legend(
        handles=[
            Patch(facecolor="#2f6b3f", edgecolor="#1b5e20", alpha=0.50, label="Dense forest mask"),
            Patch(facecolor="none", edgecolor="#0057B8", label="Major waterway display line"),
            Patch(facecolor="none", edgecolor="#7CCCF2", label="Minor / other waterway display line"),
        ],
        loc="upper right",
        frameon=True,
        fontsize=9,
    )

    fig.tight_layout()
    fig.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"Saved preview figure: {output_file}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load existing Prokhorovka geographic NPZ and create model input without downloads, preserving preview style.")
    p.add_argument("--input", type=str, default=None, help="Existing NPZ file or folder. Default: auto-detect.")
    p.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR), help="Output folder. Default: data9/prokhorovka_terrain")
    p.add_argument("--forest-threshold", type=float, default=0.8, help="Dense forest threshold applied to forestRatio. Default: 0.80")
    p.add_argument("--output-name", type=str, default="prokhorovka_geographic_data_model_input.npz", help="Output NPZ file name.")
    p.add_argument("--no-preview", action="store_true", help="Do not create a PNG preview figure.")
    p.add_argument("--copy-canonical", action="store_true", help="Also copy output to prokhorovka_geographic_data.npz in the output folder.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not (0.0 <= args.forest_threshold <= 1.0):
        raise ValueError("--forest-threshold must be between 0 and 1.")

    input_file = find_input_file(args.input)
    out_dir = Path(args.out_dir)
    output_file = out_dir / args.output_name

    print("Loading existing geographic NPZ only. No download/query will be performed.")
    print(f"Input file       : {input_file}")
    print(f"Output directory : {out_dir}")
    print(f"Forest threshold : {args.forest_threshold:.2f}")

    data = read_npz(input_file)
    dataset = build_dataset(data, input_file=input_file, forest_threshold=args.forest_threshold)
    save_dataset(dataset, output_file)

    summary_file = output_file.with_suffix(".summary.txt")
    write_summary(dataset, summary_file, input_file=input_file)

    if args.copy_canonical:
        canonical = out_dir / "prokhorovka_geographic_data.npz"
        if canonical.resolve() != output_file.resolve():
            shutil.copy2(output_file, canonical)
            print(f"Copied model-input NPZ to canonical name: {canonical}")

    if not args.no_preview:
        preview_file = output_file.with_suffix(".preview.png")
        make_preview(dataset, preview_file)

    print("Done.")


if __name__ == "__main__":
    main()
