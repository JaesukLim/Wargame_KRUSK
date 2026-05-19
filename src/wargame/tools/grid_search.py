"""Simple grid search helper for scenario tuning.

The script tries combinations of parameters and returns CSV-like result rows.
"""

from __future__ import annotations

import argparse
import copy
import csv
import itertools
from pathlib import Path

from wargame.core.config_loader import SimulationConfig, load_config
from wargame.core.sim_runner import build_battlefield_from_config, run_headless_step


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="base config file")
    p.add_argument("--scenario", required=False)
    p.add_argument("--duration", type=float, default=180.0)
    p.add_argument("--dt", type=float, default=0.2)
    p.add_argument(
        "--sweep",
        nargs="*",
        default=[
            "simulation.combat.default_k_attacker=0.0015,0.0025,0.004",
            "simulation.combat.default_k_defender=0.0015,0.0025,0.004",
        ],
        help="Sweep specs: path.to.value=v1,v2,v3",
    )
    p.add_argument("--out", default="grid_search_results.csv")
    return p.parse_args()


def _parse_entry(spec: str) -> tuple[list[str], list[float]]:
    lhs, rhs = spec.split("=", 1)
    vals = [float(x) for x in rhs.split(",")]
    path = lhs.split(".")
    return path, vals


def _set_nested(cfg: dict, path: list[str], value: float):
    node = cfg
    for p in path[:-1]:
        node = node.setdefault(p, {})
    node[path[-1]] = value


def run_sweep(args: argparse.Namespace) -> None:
    specs = [_parse_entry(s) for s in args.sweep]

    # brute-force cartesian combinations
    keys = [p for p, _ in specs]
    grids = [vals for _, vals in specs]
    rows = []

    for combo in itertools.product(*grids):
        cfg = load_config(args.config, args.scenario)
        cfg_raw = copy.deepcopy(cfg.raw)
        for path, value in zip(keys, combo):
            _set_nested(cfg_raw, path, value)

        # quick simulate
        bf = build_battlefield_from_config(SimulationConfig(cfg_raw))

        history = run_headless_step(bf, duration_s=args.duration, dt=args.dt)
        red = history[-1]["red_strength"] if history else 0
        blue = history[-1]["blue_strength"] if history else 0

        row = {"red": red, "blue": blue}
        for k, v in zip(keys, combo):
            row[".".join(k)] = v
        row["remaining_diff"] = red - blue
        rows.append(row)

    out = Path(args.out)
    fieldnames = sorted({k for r in rows for k in r})
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")


def main() -> None:
    args = parse_args()
    run_sweep(args)


if __name__ == "__main__":
    main()
