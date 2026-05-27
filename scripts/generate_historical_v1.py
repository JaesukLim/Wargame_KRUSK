#!/usr/bin/env python3
"""
Generate prokhorovka_historical_v1.json from prokhorovka_default.json.

Responsibility:
- Keep the default scenario's unit list and initial positions.
- Regenerate tank/recon movement paths using a hand-defined target front contour.
- Spread unit groups along front-line segments instead of collapsing each group
  into a single target point.
- Keep artillery and command posts stationary.
- Write a new scenario JSON file for Godot/backend testing.

Input:
- src/wargame/scenarios/prokhorovka_default.json

Output:
- src/wargame/scenarios/prokhorovka_historical_v1.json
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_SCENARIO = PROJECT_ROOT / "src/wargame/scenarios/prokhorovka_default.json"
OUTPUT_SCENARIO = PROJECT_ROOT / "src/wargame/scenarios/prokhorovka_historical_v1.json"


# ---------------------------------------------------------------------------
# Target front contour
# ---------------------------------------------------------------------------
# Simulator coordinates are in meters.
#
# This polyline is a first-order hand-digitized target line based on the PPT
# Prokhorovka situation map. It is not meant to be a final historical truth.
# It is a tunable control curve:
#
#   west / Hill 226.6
#       -> Hill 241.6
#       -> Hill 252.2
#       -> west of Prokhorovka
#
# Increase/decrease or move these points after checking the result in Godot.
FRONTLINE_POINTS: list[list[float]] = [
    [2600.0, 7200.0],   # 0: far-left / western contact area
    [3200.0, 7500.0],   # 1: Hill 226.6 western approach
    [3800.0, 7800.0],   # 2
    [4500.0, 8050.0],   # 3
    [5200.0, 8250.0],   # 4
    [5900.0, 8450.0],   # 5: Hill 241.6 approach
    [6500.0, 8650.0],   # 6: Hill 241.6 / central low ridge
    [7100.0, 9000.0],   # 7: central bend
    [7700.0, 9400.0],   # 8: Hill 252.2
    [8300.0, 9400.0],   # 9: east of Hill 252.2
    [8900.0, 9100.0],   # 10: west of Prokhorovka
    [9500.0, 8800.0],   # 11: Prokhorovka western road area
]


# ---------------------------------------------------------------------------
# Unit group -> front-line segment assignment
# ---------------------------------------------------------------------------
# Values are inclusive-ish index ranges on FRONTLINE_POINTS.
# The target is sampled continuously between FRONTLINE_POINTS[i0] and
# FRONTLINE_POINTS[i1], so units in the same group are spread along a segment.
#
# Examples:
#   "B-TK-1": (5, 8)
#       B-TK-1A/B/C... are distributed between Hill 241.6 and Hill 252.2.
#
#   "R-TK-4": (8, 11)
#       R-TK-4A/B/C... are distributed near Hill 252.2 -> Prokhorovka west.
GROUP_FRONTLINE_RANGES: dict[str, tuple[int, int]] = {
    # Blue / II SS-PzC-style groups.
    # B-TK-1 appears in the central-right attack axis in the PPT.
    "B-TK-1": (5, 8),

    # B-TK-2 occupies the central/lower-central approach.
    "B-TK-2": (3, 6),

    # B-TK-3 is more western / left contact sector.
    "B-TK-3": (1, 4),

    # Red / 5 GTA-style groups.
    # R-TK-3 is the western red group pressing toward Hill 226.6.
    "R-TK-3": (1, 4),

    # R-TK-2 and R-TK-1 pressure the center.
    "R-TK-2": (3, 6),
    "R-TK-1": (5, 8),

    # R-TK-4 and R-TK-5 are toward the Prokhorovka / eastern side.
    "R-TK-4": (8, 11),
    "R-TK-5": (7, 10),

    # Recon units move toward observation positions near the center, not
    # exactly into the tank collision line. Additional recon offsets are applied
    # later.
    "B-REC": (5, 7),
    "R-REC": (6, 8),
}


# Per-side offset from the same front contour.
# This prevents both sides from getting exactly identical target points.
# Blue stays slightly southwest of the contour; Red stays slightly northeast.
SIDE_TARGET_OFFSET: dict[str, list[float]] = {
    "blue": [-220.0, -220.0],
    "red": [220.0, 220.0],
}


# Extra side-specific offsets for recon units.
# Recon should observe the fight, not necessarily collide with tank units.
RECON_TARGET_EXTRA_OFFSET: dict[str, list[float]] = {
    "blue": [-350.0, -450.0],
    "red": [350.0, 450.0],
}


TERRAIN_X_MIN = 50.0
TERRAIN_X_MAX = 13950.0
TERRAIN_Y_MIN = 50.0
TERRAIN_Y_MAX = 17150.0


def distance(a: list[float], b: list[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def clamp_point(point: list[float]) -> list[float]:
    return [
        clamp(point[0], TERRAIN_X_MIN, TERRAIN_X_MAX),
        clamp(point[1], TERRAIN_Y_MIN, TERRAIN_Y_MAX),
    ]


def get_group_key(unit_name: str) -> str | None:
    """Return the prefix key used for group-level path assignment."""

    # Longer prefixes should be checked first, just in case future names overlap.
    for prefix in sorted(GROUP_FRONTLINE_RANGES, key=len, reverse=True):
        if unit_name.startswith(prefix):
            return prefix
    return None


def interpolate_frontline(i0: int, i1: int, t: float) -> list[float]:
    """Sample a continuous target point from the assigned front-line range."""

    n = len(FRONTLINE_POINTS)
    i0 = max(0, min(i0, n - 1))
    i1 = max(0, min(i1, n - 1))

    if i1 < i0:
        i0, i1 = i1, i0

    if i0 == i1:
        return FRONTLINE_POINTS[i0][:]

    # raw index in [i0, i1]
    raw = i0 + t * (i1 - i0)
    j = int(math.floor(raw))
    frac = raw - j

    if j >= n - 1:
        return FRONTLINE_POINTS[-1][:]

    p0 = FRONTLINE_POINTS[j]
    p1 = FRONTLINE_POINTS[j + 1]

    return [
        p0[0] * (1.0 - frac) + p1[0] * frac,
        p0[1] * (1.0 - frac) + p1[1] * frac,
    ]


def target_for_unit(unit: dict[str, Any]) -> list[float] | None:
    """Return a target point sampled from the assigned front-line segment."""

    name = str(unit.get("name", ""))
    side = str(unit.get("side", "")).lower()
    kind = str(unit.get("kind", "")).lower()

    group_key = get_group_key(name)
    if group_key is None:
        return None

    i0, i1 = GROUP_FRONTLINE_RANGES[group_key]

    # Deterministically spread units from the same group along the range.
    rng = random.Random(f"{name}-front-target-historical-v1")
    t = rng.random()
    base = interpolate_frontline(i0, i1, t)

    side_offset = SIDE_TARGET_OFFSET.get(side, [0.0, 0.0])
    target = [
        base[0] + side_offset[0],
        base[1] + side_offset[1],
    ]

    if kind == "recon":
        recon_offset = RECON_TARGET_EXTRA_OFFSET.get(side, [0.0, 0.0])
        target = [
            target[0] + recon_offset[0],
            target[1] + recon_offset[1],
        ]

    return clamp_point(target)


def lateral_offset_vector(start: list[float], end: list[float]) -> list[float]:
    """Return a unit perpendicular vector to the start->end direction."""

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    norm = math.hypot(dx, dy)

    if norm <= 1e-9:
        return [0.0, 0.0]

    return [-dy / norm, dx / norm]


def make_two_point_path(
    start: list[float],
    target: list[float],
    unit_name: str,
    side: str,
    jitter_scale: float = 180.0,
) -> list[list[float]]:
    """Build a simple [midpoint, target] path with deterministic lateral jitter."""

    rng = random.Random(f"{unit_name}-{side}-path-historical-v1")
    perp = lateral_offset_vector(start, target)
    jitter = rng.uniform(-jitter_scale, jitter_scale)

    mid = [
        0.52 * start[0] + 0.48 * target[0] + perp[0] * jitter,
        0.52 * start[1] + 0.48 * target[1] + perp[1] * jitter,
    ]

    mid = clamp_point(mid)
    target = clamp_point(target)

    return [
        [round(mid[0], 1), round(mid[1], 1)],
        [round(target[0], 1), round(target[1], 1)],
    ]


def should_keep_stationary(unit: dict[str, Any]) -> bool:
    """Return True for units that should not receive generated paths."""

    kind = str(unit.get("kind", "")).lower()
    name = str(unit.get("name", ""))

    # Artillery and HQ should stay fixed in this first scenario version.
    if kind in {"artillery", "command", "command_post"}:
        return True

    # Some command posts are written as kind="command" in JSON and become
    # command_post internally. Keep both cases stationary.
    if "HQ" in name or "TOC" in name:
        return True

    return False


def regenerate_paths(data: dict[str, Any]) -> dict[str, Any]:
    """Regenerate paths in-place and return the modified scenario data."""

    data["name"] = "prokhorovka_historical_v1"
    data["description"] = (
        "Semi-automated historical-style scenario generated from "
        "prokhorovka_default.json. Initial unit positions are preserved. "
        "Tank and recon movement paths are regenerated from a multi-point "
        "front-line contour based on the 1943-07-12 Prokhorovka situation map."
    )

    data["terrain"] = {
        "csv": "DEM_data_1/prokhorovka_geographic_data_100m.csv",
        "cell_size_m": 100,
    }

    changed = 0
    stationary = 0
    unchanged = 0

    for unit in data.get("units", []):
        name = str(unit.get("name", ""))
        side = str(unit.get("side", "")).lower()
        kind = str(unit.get("kind", "")).lower()
        pos = unit.get("position")

        if not isinstance(pos, list) or len(pos) != 2:
            unchanged += 1
            continue

        if should_keep_stationary(unit):
            unit["path"] = []
            stationary += 1
            continue

        if kind not in {"tank", "recon"}:
            unchanged += 1
            continue

        target = target_for_unit(unit)
        if target is None:
            unchanged += 1
            continue

        start = [float(pos[0]), float(pos[1])]

        unit["path"] = make_two_point_path(
            start=start,
            target=[float(target[0]), float(target[1])],
            unit_name=name,
            side=side,
        )

        changed += 1

    data["_generation_note"] = {
        "generator": "scripts/generate_historical_v1.py",
        "path_policy": (
            "preserve initial positions; regenerate tank/recon paths from "
            "front-line ranges; keep artillery/HQ stationary"
        ),
        "changed_paths": changed,
        "stationary_units": stationary,
        "unchanged_units": unchanged,
        "frontline_points": FRONTLINE_POINTS,
        "group_frontline_ranges": GROUP_FRONTLINE_RANGES,
        "side_target_offset": SIDE_TARGET_OFFSET,
        "recon_target_extra_offset": RECON_TARGET_EXTRA_OFFSET,
    }

    return data


def main() -> None:
    if not INPUT_SCENARIO.exists():
        raise FileNotFoundError(f"Input scenario not found: {INPUT_SCENARIO}")

    data = json.loads(INPUT_SCENARIO.read_text(encoding="utf-8"))
    data = regenerate_paths(data)

    OUTPUT_SCENARIO.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote {OUTPUT_SCENARIO}")
    print(f"Units: {len(data.get('units', []))}")
    print(json.dumps(data["_generation_note"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
