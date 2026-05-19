"""Helpers to build simulation objects from configuration dictionaries."""

from __future__ import annotations

from typing import Any, Dict, List

from .types import MovementPath, Point, Side, UnitKind
from .unit import Unit


def _normalize_side(value: str) -> Side:
    value = value.lower().strip()
    if value in ("red", "a", "side_a"):
        return Side.RED
    return Side.BLUE


def _normalize_kind(value: str) -> UnitKind:
    value = value.lower()
    if "recon" in value or "scout" in value or "observe" in value or "observer" in value:
        return UnitKind.RECON
    if "cmd" in value or "command" in value or "hq" in value:
        return UnitKind.COMMAND
    if "art" in value:
        return UnitKind.ARTILLERY
    return UnitKind.TANK


def parse_unit_definition(defn: Dict[str, Any]) -> Unit:
    side = _normalize_side(defn.get("side", "red"))
    kind = _normalize_kind(defn.get("kind", "tank"))
    position = Point(*defn.get("position", [0.0, 0.0]))

    path_points: List[Point] = [Point(*pt) for pt in defn.get("path", []) if len(pt) >= 2]
    movement_path = MovementPath(waypoints=path_points, loop=bool(defn.get("path_loop", False)))

    return Unit(
        name=defn.get("name", "unit"),
        side=side,
        kind=kind,
        unit_type=defn.get("type", defn.get("unit_type", "default_tank")),
        position=position,
        strength=float(defn.get("strength", 100.0)),
        max_strength=float(defn.get("max_strength", defn.get("strength", 100.0))),
        speed_mps=float(defn.get("speed_mps", 18.0)),
        detection_range_m=float(defn.get("detection_range_m", 2200.0)),
        command_range_m=float(defn.get("command_range_m", 3000.0)),
        lanchester_range_m=float(defn.get("lanchester_range_m", 1500.0)),
        lanchester_kills=float(defn.get("lanchester_kill_rate", 0.0)),
        armor=float(defn.get("armor", 1.0)),
        morale=float(defn.get("morale", 1.0)),
        movement_path=movement_path,
        color=defn.get("color", "#ffffff"),
        # tank-specific
        fire_range_m=defn.get("fire_range_m"),
        # artillery-specific
        fire_rate_per_min=defn.get("fire_rate_per_min"),
        shell_damage=defn.get("shell_damage"),
        shell_range_m=defn.get("shell_range_m"),
        shell_speed_mps=defn.get("shell_speed_mps"),
        shell_dispersion_m=defn.get("shell_dispersion_m"),
        ammo_remaining=defn.get("ammo_limit", defn.get("ammo_remaining")),
    )
