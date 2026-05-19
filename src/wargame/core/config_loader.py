"""Configuration loader.

All simulation parameters are externalized here so behavior can be tuned without code changes.
"""

from __future__ import annotations

import json
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback without dependency
    yaml = None


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config" / "default.yaml"
DEFAULT_SCENARIO_PATH = PACKAGE_ROOT / "scenarios" / "prokhorovka_default.json"


def _load_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() in {".yml", ".yaml"} and yaml is not None:
        return yaml.safe_load(text) or {}
    if path.suffix.lower() in {".yml", ".yaml"} and yaml is None:
        raise RuntimeError(
            "PyYAML not installed. Install dependency with: pip install pyyaml"
        )
    return json.loads(text)


def _deep_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in right.items():
        if (
            isinstance(value, dict)
            and key in left
            and isinstance(left[key], dict)
        ):
            left[key] = _deep_merge(left[key], value)
        else:
            left[key] = value
    return left


@dataclass(frozen=True)
class SimulationConfig:
    raw: Dict[str, Any]

    def get(self, *path: str, default=None):
        node: Any = self.raw
        for part in path:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def load_config(
    config_path: str | None = None,
    scenario_path: str | None = None,
) -> SimulationConfig:
    base = _load_file(DEFAULT_CONFIG_PATH)
    if config_path:
        override = _load_file(Path(config_path))
        base = _deep_merge(base, override)
    scenario = _load_file(Path(scenario_path)) if scenario_path else _load_file(DEFAULT_SCENARIO_PATH)

    merged = _deep_merge(copy.deepcopy(base), {"scenario": scenario})
    return SimulationConfig(merged)


def flatten_scenario(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return scenario block with fallback to defaults."""
    return config.get("scenario", {})
