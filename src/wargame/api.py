"""FastAPI localhost backend for the Wargame KRUSK simulation.

The backend owns simulation state and exposes a small HTTP/WebSocket contract
for the Godot 4 client. It intentionally keeps rendering concerns out of
Python so Godot can be the only presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import __version__
from .core.loader import parse_unit_definition
from .core.sim_runner import build_battlefield
from .core.types import MovementPath, Point


API_SCHEMA_VERSION = "2026-05-20.1"


class StepRequest(BaseModel):
    dt: float = Field(default=30.0, gt=0.0, le=600.0)
    steps: int = Field(default=1, ge=1, le=600)


class ResetRequest(BaseModel):
    """Public reset accepts no path overrides."""

    model_config = ConfigDict(extra="forbid")


class UnitCommand(BaseModel):
    """Intent-level unit command accepted from the Godot client."""

    model_config = ConfigDict(extra="forbid")

    waypoints: list[list[float]] | None = None
    position: list[float] | None = Field(default=None, min_length=2, max_length=2)
    append_waypoint: list[float] | None = Field(default=None, min_length=2, max_length=2)
    remove_last_waypoint: bool = False
    intent: str | None = Field(default=None, max_length=32)
    target_id: str | None = Field(default=None, max_length=64)
    priority: str | None = Field(default=None, max_length=32)
    execute_at_s: float | None = Field(default=None, ge=0.0)


class RuntimeParameters(BaseModel):
    """Runtime-tunable model controls exposed to the Godot operator UI."""

    model_config = ConfigDict(extra="forbid")

    direct_fire_scale: float = Field(default=1.0, ge=0.1, le=3.0)
    combat_speed_scale: float = Field(default=0.60, ge=0.25, le=2.0)
    artillery_delay_s: float = Field(default=240.0, ge=25.0, le=600.0)
    artillery_damage_scale: float = Field(default=1.0, ge=0.1, le=3.0)
    target_area_scale: float = Field(default=1.0, ge=0.25, le=4.0)


class RuntimeParameterPatch(BaseModel):
    """Partial runtime parameter update."""

    model_config = ConfigDict(extra="forbid")

    direct_fire_scale: float | None = Field(default=None, ge=0.1, le=3.0)
    combat_speed_scale: float | None = Field(default=None, ge=0.25, le=2.0)
    artillery_delay_s: float | None = Field(default=None, ge=25.0, le=600.0)
    artillery_damage_scale: float | None = Field(default=None, ge=0.1, le=3.0)
    target_area_scale: float | None = Field(default=None, ge=0.25, le=4.0)


class LanchesterMatrixPatch(BaseModel):
    """Partial runtime update for attacker-vs-defender Lanchester k values."""

    model_config = ConfigDict(extra="forbid")

    matrix: dict[str, dict[str, float]]
    replace: bool = False


class AddUnitRequest(BaseModel):
    """Create a new aggregate unit from the operator UI."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    side: str = Field(pattern="^(red|blue)$")
    kind: str = Field(default="tank", max_length=32)
    type: str = Field(default="custom_tank", max_length=64)
    position: list[float] = Field(min_length=2, max_length=2)
    strength: float = Field(default=10.0, gt=0.0, le=10000.0)
    max_strength: float | None = Field(default=None, gt=0.0, le=10000.0)
    speed_mps: float = Field(default=8.0, ge=0.0, le=80.0)
    detection_range_m: float = Field(default=2400.0, ge=0.0, le=100000.0)
    command_range_m: float = Field(default=5000.0, ge=0.0, le=100000.0)
    lanchester_range_m: float = Field(default=1800.0, ge=0.0, le=100000.0)
    armor: float = Field(default=1.0, ge=0.05, le=20.0)
    morale: float = Field(default=1.0, ge=0.05, le=2.0)
    color: str = Field(default="#ffffff", max_length=16)
    fire_rate_per_min: float | None = Field(default=None, ge=0.0, le=120.0)
    shell_damage: float | None = Field(default=None, ge=0.0, le=1000.0)
    shell_range_m: float | None = Field(default=None, ge=0.0, le=200000.0)
    shell_speed_mps: float | None = Field(default=None, ge=0.0, le=3000.0)
    shell_dispersion_m: float | None = Field(default=None, ge=0.0, le=5000.0)
    ammo_remaining: int | None = Field(default=None, ge=0, le=100000)


class StateLoadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: dict[str, Any]


class ConfigLoadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: RuntimeParameterPatch | None = None
    lanchester_matrix: dict[str, dict[str, float]] | None = None
    state: dict[str, Any] | None = None


@dataclass(frozen=True)
class BackendConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    config_path: str | None = None
    scenario_path: str | None = None


class SimulationSession:
    """Thread-safe wrapper around one mutable BattleField instance."""

    def __init__(self, config: BackendConfig):
        self.config = config
        self._lock = RLock()
        self._config_path = config.config_path
        self._scenario_path = config.scenario_path
        self._parameters = RuntimeParameters()
        self._battlefield = build_battlefield(self._config_path, self._scenario_path)
        self._apply_parameters()

    def _apply_parameters(self) -> None:
        self._battlefield.set_runtime_parameters(self._parameters.model_dump())

    def reset(self, _request: ResetRequest | None = None) -> dict[str, Any]:
        with self._lock:
            self._battlefield = build_battlefield(self._config_path, self._scenario_path)
            self._apply_parameters()
            return self.state()

    def step(self, request: StepRequest) -> dict[str, Any]:
        with self._lock:
            for _ in range(request.steps):
                if not self._battlefield.alive_units() or self._battlefield.is_terminal():
                    break
                self._battlefield.update(request.dt)
                if self._battlefield.is_terminal():
                    break
            return self.state()

    def parameters(self) -> dict[str, Any]:
        values = self._parameters.model_dump()
        return {
            "values": values,
            "lanchester_matrix": self._battlefield.lanchester_matrix_payload(),
            "schema_version": API_SCHEMA_VERSION,
            "schema": {
                "direct_fire_scale": {"min": 0.1, "max": 3.0, "step": 0.1, "label": "Direct fire scale"},
                "combat_speed_scale": {"min": 0.25, "max": 2.0, "step": 0.05, "label": "Combat attrition speed"},
                "artillery_delay_s": {"min": 25.0, "max": 600.0, "step": 15.0, "label": "Indirect-fire DES delay"},
                "artillery_damage_scale": {"min": 0.1, "max": 3.0, "step": 0.1, "label": "Artillery damage scale"},
                "target_area_scale": {"min": 0.25, "max": 4.0, "step": 0.25, "label": "Target area scale"},
            },
        }

    def update_parameters(self, patch: RuntimeParameterPatch) -> dict[str, Any]:
        with self._lock:
            values = self._parameters.model_dump()
            values.update(patch.model_dump(exclude_none=True))
            self._parameters = RuntimeParameters.model_validate(values)
            self._apply_parameters()
            return self.state()

    def state(self, *, include_logs: bool = False) -> dict[str, Any]:
        with self._lock:
            payload = self._battlefield.export_state(include_logs=include_logs)
            payload["backend"] = {
                "host": self.config.host,
                "port": self.config.port,
                "transport": ["http", "websocket"],
                "api_version": __version__,
                "schema_version": API_SCHEMA_VERSION,
            }
            return payload

    def terrain(self) -> dict[str, Any]:
        with self._lock:
            return self._battlefield.terrain_payload()

    def engagements(self) -> dict[str, Any]:
        with self._lock:
            return self._battlefield.engagements_payload()

    def dump_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": API_SCHEMA_VERSION,
                "parameters": self._parameters.model_dump(),
                "lanchester_matrix": self._battlefield.lanchester_matrix_payload()["matrix"],
                "state": self.state(include_logs=True),
            }

    def load_state(self, request: StateLoadRequest) -> dict[str, Any]:
        with self._lock:
            self._replace_units_from_state(request.state)
            self._battlefield.load_state(request.state)
            return self.state()

    def dump_config(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema_version": API_SCHEMA_VERSION,
                "parameters": self._parameters.model_dump(),
                "lanchester_matrix": self._battlefield.lanchester_matrix_payload()["matrix"],
                "config_path": self._config_path,
                "scenario_path": self._scenario_path,
            }

    def load_config(self, request: ConfigLoadRequest) -> dict[str, Any]:
        with self._lock:
            if request.parameters is not None:
                values = self._parameters.model_dump()
                values.update(request.parameters.model_dump(exclude_none=True))
                self._parameters = RuntimeParameters.model_validate(values)
                self._apply_parameters()
            if request.lanchester_matrix is not None:
                self._battlefield.set_lanchester_matrix(request.lanchester_matrix)
            if request.state is not None:
                self._replace_units_from_state(request.state)
                self._battlefield.load_state(request.state)
            return self.state()

    def lanchester_matrix(self) -> dict[str, Any]:
        with self._lock:
            return self._battlefield.lanchester_matrix_payload()

    def update_lanchester_matrix(self, request: LanchesterMatrixPatch) -> dict[str, Any]:
        with self._lock:
            self._battlefield.set_lanchester_matrix(request.matrix, replace=request.replace)
            return self._battlefield.lanchester_matrix_payload()

    def add_unit(self, request: AddUnitRequest) -> dict[str, Any]:
        with self._lock:
            data = request.model_dump(exclude_none=True)
            data["max_strength"] = data.get("max_strength") or data["strength"]
            if "ammo_remaining" in data:
                data["ammo_limit"] = data.pop("ammo_remaining")
            unit = parse_unit_definition(data)
            self._battlefield.add_unit(unit)
            return self.state()


    def _replace_units_from_state(self, state: dict[str, Any]) -> None:
        units_payload = state.get("units")
        if not isinstance(units_payload, list):
            return
        units = []
        for item in units_payload:
            if not isinstance(item, dict):
                continue
            data = {
                "name": item.get("name", "unit"),
                "side": item.get("side", "red"),
                "kind": item.get("kind", "tank"),
                "type": item.get("type", item.get("unit_type", "default_tank")),
                "position": [item.get("x", 0.0), item.get("y", 0.0)],
                "strength": item.get("strength", item.get("max_strength", 1.0)),
                "max_strength": item.get("max_strength", item.get("strength", 1.0)),
                "speed_mps": item.get("speed_mps", 0.0),
                "detection_range_m": item.get("detection_range_m", 0.0),
                "command_range_m": item.get("command_range_m", 0.0),
                "lanchester_range_m": item.get("lanchester_range_m", 0.0),
                "armor": item.get("armor", 1.0),
                "morale": item.get("morale", 1.0),
                "path": item.get("waypoints", []),
                "ammo_remaining": item.get("ammo_remaining"),
            }
            unit = parse_unit_definition(data)
            if item.get("id"):
                unit.id = str(item.get("id"))
            order = item.get("order")
            if isinstance(order, dict):
                unit.current_order = dict(order)
            units.append(unit)
        self._battlefield.replace_units(units)

    def delete_unit(self, unit_id: str) -> dict[str, Any]:
        with self._lock:
            if not self._battlefield.remove_unit(unit_id):
                raise KeyError(unit_id)
            return self.state()

    def command_unit(self, unit_id: str, command: UnitCommand) -> dict[str, Any]:
        with self._lock:
            unit = self._battlefield.units.get(unit_id)
            if unit is None:
                raise KeyError(unit_id)

            if command.position is not None:
                unit.position = Point(float(command.position[0]), float(command.position[1]))
            if command.waypoints is not None:
                unit.movement_path = MovementPath(
                    waypoints=[Point(float(p[0]), float(p[1])) for p in command.waypoints if len(p) >= 2]
                )
            if command.append_waypoint is not None:
                unit.movement_path.waypoints.append(
                    Point(float(command.append_waypoint[0]), float(command.append_waypoint[1]))
                )
            if command.remove_last_waypoint and unit.movement_path.waypoints:
                unit.movement_path.waypoints.pop()
            unit.current_order = command.model_dump(exclude_none=True)

            self._battlefield.log_event(
                "unit_command",
                f"Command updated for {unit.name}",
                unit_id=unit.id,
                side=unit.side,
                data=command.model_dump(exclude_none=True),
            )
            return self.state()


def create_app(config: BackendConfig | None = None) -> FastAPI:
    backend_config = config or BackendConfig()
    session = SimulationSession(backend_config)

    app = FastAPI(
        title="Wargame KRUSK Backend",
        version=__version__,
        description="Localhost simulation API for the Godot 4 client.",
    )
    app.state.session = session

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://127.0.0.1",
            "http://localhost:8765",
            "http://127.0.0.1:8765",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        state = session.state()
        return {
            "status": "ok",
            "service": "wargame-krusk-backend",
            "host": backend_config.host,
            "port": backend_config.port,
            "time_s": state["time_s"],
            "units": len(state["units"]),
        }

    @app.get("/state")
    def get_state() -> dict[str, Any]:
        return session.state()

    @app.get("/terrain")
    def get_terrain() -> dict[str, Any]:
        return session.terrain()

    @app.get("/engagements")
    def get_engagements() -> dict[str, Any]:
        return session.engagements()

    @app.get("/state/replay")
    def get_replay() -> dict[str, Any]:
        return {"replay_frames": session.state(include_logs=True).get("replay_frames", [])}

    @app.get("/state/dump")
    def dump_state() -> dict[str, Any]:
        return session.dump_state()

    @app.post("/state/load")
    def load_state(request: StateLoadRequest) -> dict[str, Any]:
        return session.load_state(request)

    @app.get("/events")
    def get_events() -> dict[str, Any]:
        return {"events": session.state(include_logs=True).get("events", [])}

    @app.get("/parameters")
    def get_parameters() -> dict[str, Any]:
        return session.parameters()

    @app.patch("/parameters")
    def patch_parameters(request: RuntimeParameterPatch) -> dict[str, Any]:
        return session.update_parameters(request)

    @app.get("/lanchester/matrix")
    def get_lanchester_matrix() -> dict[str, Any]:
        return session.lanchester_matrix()

    @app.patch("/lanchester/matrix")
    def patch_lanchester_matrix(request: LanchesterMatrixPatch) -> dict[str, Any]:
        return session.update_lanchester_matrix(request)

    @app.get("/config/dump")
    def dump_config() -> dict[str, Any]:
        return session.dump_config()

    @app.post("/config/load")
    def load_config(request: ConfigLoadRequest) -> dict[str, Any]:
        return session.load_config(request)

    @app.post("/reset")
    def reset(request: ResetRequest | None = None) -> dict[str, Any]:
        return session.reset(request)

    @app.post("/step")
    def step(request: StepRequest) -> dict[str, Any]:
        return session.step(request)

    @app.post("/units")
    def add_unit(request: AddUnitRequest) -> dict[str, Any]:
        return session.add_unit(request)

    @app.post("/units/{unit_id}/delete")
    def delete_unit(unit_id: str) -> dict[str, Any]:
        try:
            return session.delete_unit(unit_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown unit id: {unit_id}") from exc

    @app.post("/command/unit/{unit_id}")
    def command_unit(unit_id: str, command: UnitCommand) -> dict[str, Any]:
        try:
            return session.command_unit(unit_id, command)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown unit id: {unit_id}") from exc

    @app.websocket("/ws/state")
    async def websocket_state(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"type": "state", "payload": session.state()})
        try:
            while True:
                message = await websocket.receive_json()
                try:
                    payload = _handle_ws_message(session, message)
                except (KeyError, TypeError, ValueError, ValidationError) as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue
                await websocket.send_json({"type": "state", "payload": payload})
        except WebSocketDisconnect:
            return

    return app


def _handle_ws_message(session: SimulationSession, message: dict[str, Any]) -> dict[str, Any]:
    message_type = str(message.get("type", "state"))
    if message_type == "step":
        return session.step(StepRequest.model_validate(message))
    if message_type == "reset":
        return session.reset(ResetRequest.model_validate(message.get("payload", {})))
    if message_type == "set_parameters":
        return session.update_parameters(RuntimeParameterPatch.model_validate(message.get("payload", {})))
    if message_type == "set_lanchester_matrix":
        session.update_lanchester_matrix(LanchesterMatrixPatch.model_validate(message.get("payload", {})))
        return session.state()
    if message_type == "add_unit":
        return session.add_unit(AddUnitRequest.model_validate(message.get("payload", {})))
    if message_type == "load_state":
        return session.load_state(StateLoadRequest.model_validate(message.get("payload", {})))
    if message_type == "load_config":
        return session.load_config(ConfigLoadRequest.model_validate(message.get("payload", {})))
    if message_type == "delete_unit":
        unit_id = str(message.get("unit_id", ""))
        return session.delete_unit(unit_id)
    if message_type == "command_unit":
        unit_id = str(message.get("unit_id", ""))
        return session.command_unit(unit_id, UnitCommand.model_validate(message.get("payload", {})))
    return session.state()


def run_server(config: BackendConfig) -> None:
    import uvicorn

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port)
