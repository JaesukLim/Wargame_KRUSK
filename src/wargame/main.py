"""Entrypoint for Wargame KRUSK simulation/backend."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
import urllib.error
import urllib.request
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
    parser.add_argument("--log-dir", default=None, help="directory for backend runtime logs")
    return parser.parse_args()


def _default_log_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "logs"
    return Path.cwd() / ".omx" / "artifacts"


def _setup_logging(log_dir: str | None) -> Path:
    resolved_log_dir = Path(log_dir).resolve() if log_dir else _default_log_dir()
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = resolved_log_dir / "wargame_backend.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    return log_path


def _existing_backend_is_healthy(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=0.75) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return False
    return payload.get("status") == "ok" and payload.get("service") == "wargame-krusk-backend"


def main() -> None:
    args = parse_args()
    log_path = _setup_logging(args.log_dir)
    logging.info("Wargame KRUSK backend starting; log=%s", log_path)

    if args.mode == "tune":
        print("Tune mode is implemented via wargame/tools/grid_search.py")
        return

    if args.mode == "serve":
        if _existing_backend_is_healthy(args.host, args.port):
            message = f"Backend already running on {args.host}:{args.port}; reusing existing service."
            logging.info(message)
            print(message)
            return
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
    try:
        main()
    except Exception:
        log_path = _default_log_dir() / "wargame_backend.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write("\nUnhandled backend startup error:\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise
