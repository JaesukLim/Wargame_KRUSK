"""Rewrite the default Prokhorovka scenario into the historical deployment.

Layout based on the user's referenced briefing slide:
- Red (Soviet, 5GTA) splits into three groups in the *northern* third of the
  new 14 x 17 km playbox: NW (3-series), N-center (2-series), NE around
  Prokhorovka (1-series + 4-series + 5-series). Artillery and HQ sit further
  north behind each group; R-TOC (HQ) is at the extreme NE corner.
- Blue (German, II.SS-Pz.Korps) starts in the south-west quadrant with three
  tank rows behind a recon screen, artillery deeper SW, HQ at the SW corner.

Both sides receive new waypoints pointing toward a central battle area
(~(7000, 9500)) so the existing pre-set waypoints from the old smaller box do
not strand them at irrelevant coordinates.

The script preserves every other per-unit field (strength, ranges, morale,
shell parameters, etc.) and only overwrites `position` and `path`.
"""

from __future__ import annotations

import json
from pathlib import Path

SCENARIO_PATH = Path("src/wargame/scenarios/prokhorovka_default.json")

# Per-unit (position, [waypoints]) overrides.  Coordinates are in metres in the
# scenario's local frame (x east, y north), matching what /terrain exposes.
DEPLOYMENT: dict[str, tuple[tuple[float, float], list[tuple[float, float]]]] = {
    # ---------- Red NW group (3-series, around Hill 226.6) ----------
    "R-TK-3A": ((2500, 14800), [(4500, 12000), (6500, 9800)]),
    "R-TK-3B": ((3300, 14800), [(4500, 12000), (6500, 9800)]),
    "R-TK-3C": ((4100, 14800), [(5000, 12000), (6800, 9800)]),
    "R-TK-3D": ((2500, 14000), [(4500, 11500), (6500, 9800)]),
    "R-TK-3E": ((3300, 14000), [(4800, 11500), (6700, 9800)]),
    "R-TK-3F": ((4100, 14000), [(5000, 11500), (6800, 9800)]),
    # ---------- Red N-center group (2-series, between hills) ----------
    "R-TK-2A": ((5800, 14500), [(6200, 12000), (6900, 9700)]),
    "R-TK-2B": ((6600, 14500), [(6800, 12000), (7000, 9600)]),
    "R-TK-2C": ((7400, 14500), [(7400, 12000), (7200, 9600)]),
    "R-TK-2D": ((5800, 13700), [(6200, 11500), (6900, 9700)]),
    "R-TK-2E": ((6600, 13700), [(6800, 11500), (7000, 9600)]),
    "R-TK-2F": ((7400, 13700), [(7400, 11500), (7200, 9600)]),
    # ---------- Red NE group (1-series, front row near Prokhorovka) ----------
    "R-TK-1A": ((9200, 14800), [(8600, 12000), (7600, 9700)]),
    "R-TK-1B": ((10000, 14800), [(9000, 12000), (7800, 9700)]),
    "R-TK-1C": ((10800, 14800), [(9400, 12000), (8000, 9700)]),
    "R-TK-1D": ((11600, 14800), [(10000, 12000), (8400, 9800)]),
    "R-TK-1E": ((12400, 14800), [(10600, 12000), (8800, 9900)]),
    "R-TK-1F": ((13200, 14800), [(11200, 12000), (9200, 10000)]),
    # ---------- Red NE group (4-series, middle row) ----------
    "R-TK-4A": ((9200, 13800), [(8600, 11500), (7600, 9700)]),
    "R-TK-4B": ((10000, 13800), [(9000, 11500), (7800, 9700)]),
    "R-TK-4C": ((10800, 13800), [(9400, 11500), (8000, 9700)]),
    "R-TK-4D": ((11600, 13800), [(10000, 11500), (8400, 9800)]),
    "R-TK-4E": ((12400, 13800), [(10600, 11500), (8800, 9900)]),
    "R-TK-4F": ((13200, 13800), [(11200, 11500), (9200, 10000)]),
    "R-TK-4G": ((9200, 13000), [(8600, 11000), (7600, 9700)]),
    # ---------- Red NE group (5-series, rear row + east flank) ----------
    "R-TK-5A": ((10000, 13000), [(9000, 11000), (7800, 9700)]),
    "R-TK-5B": ((10800, 13000), [(9400, 11000), (8000, 9700)]),
    "R-TK-5C": ((11600, 13000), [(10000, 11000), (8400, 9800)]),
    "R-TK-5D": ((12400, 13000), [(10600, 11000), (8800, 9900)]),
    "R-TK-5E": ((13200, 13000), [(11200, 11000), (9200, 10000)]),
    "R-TK-5F": ((12200, 12000), [(10800, 10500), (9000, 9900)]),
    "R-TK-5G": ((13000, 12000), [(11400, 10500), (9400, 10000)]),
    # ---------- Red artillery (rear of each group) ----------
    "R-ART-1": ((2500, 16000), []),
    "R-ART-2": ((6500, 16000), []),
    "R-ART-3": ((11000, 16000), []),
    "R-ART-4": ((12800, 11000), []),
    # ---------- Red HQ + Recon ----------
    "R-HQ-5GTA": ((13500, 16500), []),
    "R-REC-5GTA": ((8000, 11500), [(7500, 10000), (7200, 9500)]),
    # ---------- Blue (German) main battle line, SW quadrant ----------
    # Row 1 (forward, NE-facing): Tiger + heavy company in front
    "B-TK-1A": ((4500, 5500), [(5800, 7000), (7000, 8500)]),  # Tiger
    "B-TK-1B": ((3700, 5500), [(5400, 7000), (6800, 8500)]),
    "B-TK-1C": ((4500, 4700), [(5800, 6500), (7000, 8400)]),
    "B-TK-1D": ((3700, 4700), [(5400, 6500), (6800, 8400)]),
    "B-TK-1E": ((4500, 3900), [(5800, 6000), (7000, 8300)]),
    # Row 2 (middle)
    "B-TK-2A": ((3000, 5500), [(4800, 7000), (6600, 8500)]),
    "B-TK-2B": ((3000, 4700), [(4800, 6500), (6600, 8400)]),
    "B-TK-2C": ((3700, 3900), [(5400, 6000), (6800, 8300)]),
    "B-TK-2D": ((3000, 3900), [(4800, 6000), (6600, 8300)]),
    "B-TK-2E": ((3700, 3100), [(5400, 5500), (6800, 8200)]),
    # Row 3 (rearmost tank line)
    "B-TK-3A": ((2300, 4700), [(4200, 6500), (6400, 8400)]),
    "B-TK-3B": ((2300, 3900), [(4200, 6000), (6400, 8300)]),
    "B-TK-3C": ((3000, 3100), [(4800, 5500), (6600, 8200)]),
    "B-TK-3D": ((2300, 3100), [(4200, 5500), (6400, 8200)]),
    # ---------- Blue artillery (deep SW, behind tanks) ----------
    "B-ART-1": ((1200, 5500), []),
    "B-ART-2": ((800, 4500), []),
    "B-ART-3": ((1200, 3500), []),
    "B-ART-4": ((800, 2500), []),
    "B-ART-5": ((1500, 1800), []),
    "B-ART-6": ((500, 1500), []),
    # ---------- Blue HQ + Recon ----------
    "B-HQ-SSPz": ((600, 900), []),
    "B-REC-SSPz": ((5500, 6500), [(6500, 7500), (7200, 8500)]),
}


def main() -> None:
    data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    units = data["units"]

    seen: set[str] = set()
    missing: list[str] = []

    for unit in units:
        name = unit.get("name")
        if name in DEPLOYMENT:
            pos, path = DEPLOYMENT[name]
            unit["position"] = [float(pos[0]), float(pos[1])]
            unit["path"] = [[float(p[0]), float(p[1])] for p in path]
            seen.add(name)
        else:
            missing.append(name)

    unused = set(DEPLOYMENT) - seen
    if unused:
        print(f"WARNING: deployment entries with no matching unit: {sorted(unused)}")
    if missing:
        print(f"WARNING: units left untouched (no deployment entry): {missing}")

    SCENARIO_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {len(seen)} / {len(units)} units in {SCENARIO_PATH}")


if __name__ == "__main__":
    main()
