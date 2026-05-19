"""Entrypoint for Wargame KRUSK simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wargame.core.sim_runner import build_battlefield, run_headless_step
from wargame.render.panda3d_renderer import Panda3DRenderer, Panda3DConfig
from wargame.render.pygame_renderer import PygameRenderer, RenderConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wargame KRUSK simulator")
    parser.add_argument("--config", default=None, help="override config file path")
    parser.add_argument("--scenario", default=None, help="override scenario file path")
    parser.add_argument("--mode", choices=["play", "headless", "tune"], default="play")
    parser.add_argument("--renderer", choices=["pygame", "panda3d"], default="pygame")
    parser.add_argument("--duration", type=float, default=None, help="headless duration seconds")
    parser.add_argument("--dt", type=float, default=0.2, help="simulation timestep")
    parser.add_argument("--out", default=None, help="export json path for headless mode")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "tune":
        # simple invocation placeholder for future grid-search pipeline
        print("Tune mode is implemented via wargame/tools/grid_search.py")
        return

    bf = build_battlefield(config_path=args.config, scenario_path=args.scenario)

    if args.mode == "headless":
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
        return

    # play mode
    if args.renderer == "pygame":
        pygame_cfg = bf.config.get("simulation", "graphics", "pygame", default={}) or {}
        renderer = PygameRenderer(
            bf,
            RenderConfig(
                width=int(pygame_cfg.get("width", 1400)),
                height=int(pygame_cfg.get("height", 900)),
                fps=int(pygame_cfg.get("fps", 60)),
                show_grid=bool(pygame_cfg.get("show_grid", False)),
                show_paths=bool(pygame_cfg.get("show_paths", True)),
            ),
        )
        renderer.run()
    else:
        panda_cfg = bf.config.get("simulation", "graphics", "panda3d", default={}) or {}
        renderer = Panda3DRenderer(
            bf,
            Panda3DConfig(
                free_cam_speed=float(panda_cfg.get("free_cam_speed", 60)),
                target_cam_speed=float(panda_cfg.get("target_cam_speed", 120)),
            ),
        )
        renderer.run()


if __name__ == "__main__":
    main()
