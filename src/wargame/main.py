"""Entrypoint for Wargame KRUSK simulation/backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wargame.api import BackendConfig, run_server
from wargame.core.sim_runner import build_battlefield, run_headless_step


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wargame KRUSK simulator backend")
    parser.add_argument("--config", default=None, help="override config file path")
    parser.add_argument("--scenario", default=None, help="override scenario file path")
    parser.add_argument("--mode", choices=["serve", "headless", "tune"], default="serve")
    parser.add_argument("--duration", type=float, default=None, help="headless duration seconds")
    parser.add_argument("--dt", type=float, default=0.2, help="simulation timestep")
    parser.add_argument("--out", default=None, help="export json path for headless mode")
    parser.add_argument("--host", default="127.0.0.1", help="backend bind host for serve mode")
    parser.add_argument("--port", type=int, default=8765, help="backend port for serve mode")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "tune":
        print("Tune mode is implemented via wargame/tools/grid_search.py")
        return

    if args.mode == "serve":
        run_server(
            BackendConfig(
                host=args.host,
                port=args.port,
                config_path=args.config,
                scenario_path=args.scenario,
            )
        )
        return

    bf = build_battlefield(config_path=args.config, scenario_path=args.scenario)
    history = run_headless_step(bf, duration_s=args.duration or 120.0, dt=args.dt)
    payload = {
        "config": {"duration_s": args.duration or 120.0, "dt": args.dt},
        "scenario": "custom" if args.scenario else "default",
        "history": history,
    }
    if args.out:
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote history to {args.out}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
