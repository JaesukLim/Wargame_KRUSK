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
    active_after_s = float(defn.get("active_after_s", 0.0))

    def lifecycle_gate(name: str) -> float:
        return float(defn.get(name, active_after_s))

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
        echelon=str(defn.get("echelon", defn.get("echelon_label", ""))),
        active_after_s=active_after_s,
        present_after_s=lifecycle_gate("present_after_s"),
        detectable_after_s=lifecycle_gate("detectable_after_s"),
        targetable_after_s=lifecycle_gate("targetable_after_s"),
        maneuver_after_s=lifecycle_gate("maneuver_after_s"),
        engage_after_s=lifecycle_gate("engage_after_s"),
        activation_phase=str(defn.get("activation_phase", "initial")),
        activation_label=str(defn.get("activation_label", "")),
        visible_before_activation=bool(defn.get("visible_before_activation", True)),
        reserve_trigger_side=str(defn.get("reserve_trigger_side", "")),
        reserve_trigger_kind=str(defn.get("reserve_trigger_kind", "tank")),
        reserve_trigger_loss_ratio=(
            float(defn["reserve_trigger_loss_ratio"])
            if defn.get("reserve_trigger_loss_ratio") is not None
            else None
        ),
        reserve_triggered=bool(defn.get("reserve_triggered", False)),
        reserve_triggered_at_s=(
            float(defn["reserve_triggered_at_s"])
            if defn.get("reserve_triggered_at_s") is not None
            else None
        ),
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
