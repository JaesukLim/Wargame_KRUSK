from __future__ import annotations

from math import dist

from fastapi.testclient import TestClient

from wargame.api import BackendConfig, create_app


def make_client() -> TestClient:
    return TestClient(create_app(BackendConfig(host="127.0.0.1", port=8765)))


def test_health_and_state_contract() -> None:
    client = make_client()
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    state = client.get("/state")
    assert state.status_code == 200
    payload = state.json()
    assert payload["time_s"] == 0.0
    assert payload["units"]
    assert "terrain" in payload
    assert "normalized_strength" in payload["units"][0]
    assert payload["parameters"]["artillery_delay_s"] == 240.0
    assert payload["parameters"]["combat_speed_scale"] == 0.60
    assert payload["parameters"]["red_force_end_ratio"] == 0.50
    assert payload["parameters"]["blue_tank_end_count"] == 0.0
    assert payload["parameters"]["unit_removal_ratio"] == 0.20
    assert "detection_range_m" in payload["units"][0]
    assert "lanchester_range_m" in payload["units"][0]
    assert "lifecycle_state" in payload["units"][0]
    assert payload["summary"]["present_units"] > 0
    assert payload["summary"]["absent_units"] > 0
    assert payload["summary"]["red_force_end_threshold"] == payload["summary"]["red_initial_strength"] * 0.50
    assert payload["summary"]["unit_removal_ratio"] == 0.20
    assert payload["summary"]["tank_counts"]["red"]
    assert payload["summary"]["tank_counts"]["blue"]
    assert "exchange" in payload["summary"]
    assert payload["summary"]["exchange"]["red_losses"] == 0.0
    assert "reserve_status" in payload["summary"]
    assert payload["summary"]["reserve_status"]["pending_units"] > 0
    assert payload["summary"]["reserve_status"]["pending_strength"] > 0.0
    assert payload["summary"]["reserve_pending_strength"] == payload["summary"]["reserve_status"]["pending_strength"]
    assert payload["summary"]["total_frames"] == 120
    assert payload["summary"]["current_frame"] == 1
    assert payload["model"]["direct_fire"] == "Lanchester Square Law"
    assert "replay_frames" not in payload
    assert "events" not in payload
    assert payload["backend"]["transport"] == ["http", "websocket"]
    assert payload["backend"]["api_version"] == "0.2.0"
    assert payload["backend"]["schema_version"] == "2026-05-20.1"


def test_command_posts_are_exported_with_godot_kind() -> None:
    client = make_client()
    state = client.get("/state")
    assert state.status_code == 200
    kinds = {unit["kind"] for unit in state.json()["units"]}
    assert "command_post" in kinds
    assert "command" not in kinds


def test_step_advances_time_and_reset_rebuilds() -> None:
    client = make_client()
    stepped = client.post("/step", json={"dt": 0.1, "steps": 3})
    assert stepped.status_code == 200
    assert stepped.json()["time_s"] > 0.0

    before_reset_first_id = client.get("/state").json()["units"][0]["id"]
    reset = client.post("/reset", json={})
    assert reset.status_code == 200
    assert reset.json()["time_s"] == 0.0
    assert reset.json()["units"][0]["id"] == before_reset_first_id


def test_reset_rejects_path_overrides() -> None:
    client = make_client()
    response = client.post("/reset", json={"scenario_path": "C:/Windows/win.ini"})
    assert response.status_code == 422


def test_generate_replay_precomputes_without_mutating_live_state() -> None:
    client = make_client()
    before = client.get("/state").json()

    generated = client.post("/state/replay/generate", json={"dt": 30.0, "max_steps": 3, "sample_every_steps": 1})
    assert generated.status_code == 200
    payload = generated.json()

    assert payload["metadata"]["precomputed"] is True
    assert payload["metadata"]["steps_run"] == 3
    assert payload["metadata"]["frames"] == 4
    assert payload["metadata"]["final_time_s"] == before["time_s"] + 90.0
    assert "end_reason" in payload["metadata"]
    assert len(payload["replay_frames"]) == 4
    assert payload["replay_frames"][0]["time_s"] == before["time_s"]
    assert payload["replay_frames"][-1]["time_s"] == before["time_s"] + 90.0
    assert "events" not in payload["replay_frames"][0]
    assert {"contacts", "fire_missions", "pending_fire_orders", "shells"}.issubset(payload["replay_frames"][0])

    after = client.get("/state").json()
    assert after["time_s"] == before["time_s"]
    assert after["units"][0]["x"] == before["units"][0]["x"]

    replay = client.get("/state/replay")
    assert replay.status_code == 200
    assert replay.json()["metadata"]["precomputed"] is True
    assert len(replay.json()["replay_frames"]) == 4


def test_generated_replay_preserves_combat_and_artillery_overlays() -> None:
    client = make_client()

    generated = client.post(
        "/state/replay/generate",
        json={"frame_interval_s": 3600.0, "frames": 12, "integration_dt_s": 300.0},
    )
    assert generated.status_code == 200
    payload = generated.json()
    frames = payload["replay_frames"]

    assert payload["metadata"]["frames_requested"] == 12
    assert payload["metadata"]["frames_returned"] == 12
    assert payload["metadata"]["includes_initial_frame"] is True
    assert any(frame["contacts"] for frame in frames)
    assert any(frame["fire_missions"] for frame in frames)
    shell_frame = next(frame for frame in frames if frame["shells"])
    assert "launch_time" in shell_frame["shells"][0]
    assert "impact_time" in shell_frame["shells"][0]
    assert "ballistic_travel_s" in shell_frame["shells"][0]
    assert shell_frame["shells"][0]["impact_time"] > shell_frame["shells"][0]["launch_time"]


def test_default_replay_timeline_contract_includes_initial_frame() -> None:
    client = make_client()

    generated = client.post("/state/replay/generate", json={"stop_on_terminal": False})
    assert generated.status_code == 200
    payload = generated.json()
    meta = payload["metadata"]

    assert meta["frames_requested"] == 120
    assert meta["frames_returned"] == 120
    assert meta["includes_initial_frame"] is True
    assert abs(meta["frame_interval_s"] - (86400.0 / 119.0)) < 1e-6
    assert payload["replay_frames"][0]["time_s"] == 0.0
    assert abs(payload["replay_frames"][-1]["time_s"] - 86400.0) < 1e-6


def test_replay_terminal_stop_does_not_append_duplicate_terminal_frames() -> None:
    client = make_client()
    state = client.get("/state").json()
    for unit in state["units"]:
        if unit["side"] == "blue" and unit["kind"] == "tank":
            unit["strength"] = 0.0
    loaded = client.post("/state/load", json={"state": state})
    assert loaded.status_code == 200
    assert loaded.json()["summary"]["ended"] is True

    generated = client.post("/state/replay/generate", json={})
    assert generated.status_code == 200
    payload = generated.json()

    assert payload["metadata"]["ended"] is True
    assert payload["metadata"]["end_reason"] == "blue_tanks_destroyed"
    assert payload["metadata"]["frames_requested"] == 120
    assert payload["metadata"]["frames_returned"] == 1
    assert len(payload["replay_frames"]) == 1


def test_runtime_parameters_are_customizable_and_survive_reset() -> None:
    client = make_client()

    current = client.get("/parameters")
    assert current.status_code == 200
    assert current.json()["values"]["direct_fire_scale"] == 1.0
    assert current.json()["values"]["combat_speed_scale"] == 0.60
    assert current.json()["schema_version"] == "2026-05-20.1"
    assert current.json()["lanchester_matrix"]["matrix"]
    assert current.json()["schema"]["artillery_delay_s"]["max"] == 600.0
    assert current.json()["schema"]["combat_speed_scale"]["max"] == 2.0
    assert current.json()["schema"]["red_force_end_ratio"]["step"] == 0.05
    assert current.json()["schema"]["blue_tank_end_count"]["step"] == 1.0
    assert current.json()["schema"]["unit_removal_ratio"]["max"] == 0.90

    updated = client.patch(
        "/parameters",
        json={
            "direct_fire_scale": 1.4,
            "combat_speed_scale": 0.75,
            "artillery_delay_s": 300.0,
            "target_area_scale": 1.5,
            "red_force_end_ratio": 0.55,
            "blue_tank_end_count": 1.0,
            "unit_removal_ratio": 0.25,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["parameters"]["direct_fire_scale"] == 1.4
    assert updated.json()["parameters"]["combat_speed_scale"] == 0.75
    assert updated.json()["parameters"]["artillery_delay_s"] == 300.0
    assert updated.json()["parameters"]["target_area_scale"] == 1.5
    assert updated.json()["parameters"]["red_force_end_ratio"] == 0.55
    assert updated.json()["parameters"]["blue_tank_end_count"] == 1.0
    assert updated.json()["parameters"]["unit_removal_ratio"] == 0.25

    reset = client.post("/reset", json={})
    assert reset.status_code == 200
    assert reset.json()["parameters"]["direct_fire_scale"] == 1.4
    assert reset.json()["parameters"]["combat_speed_scale"] == 0.75
    assert reset.json()["parameters"]["artillery_delay_s"] == 300.0
    assert reset.json()["parameters"]["red_force_end_ratio"] == 0.55
    assert reset.json()["parameters"]["unit_removal_ratio"] == 0.25

    rejected = client.patch("/parameters", json={"direct_fire_scale": 100.0})
    assert rejected.status_code == 422


def test_red_force_threshold_ends_battle_from_initial_strength_ratio() -> None:
    client = make_client()
    state = client.get("/state").json()
    initial_red = state["summary"]["red_initial_strength"]
    patched = client.patch("/parameters", json={"red_force_end_ratio": 0.95})
    assert patched.status_code == 200
    for unit in state["units"]:
        if unit["side"] == "red":
            unit["strength"] = unit["max_strength"] * 0.90

    loaded = client.post("/state/load", json={"state": state})
    assert loaded.status_code == 200
    summary = loaded.json()["summary"]
    assert summary["ended"] is True
    assert summary["winner"] == "blue"
    assert summary["end_reason"] == "red_force_threshold"
    assert summary["red_force_end_threshold"] == initial_red * 0.95


def test_units_are_removed_at_runtime_configurable_strength_ratio() -> None:
    client = make_client()
    state = client.get("/state").json()
    target = next(unit for unit in state["units"] if unit["side"] == "red" and unit["kind"] == "recon")
    target["max_strength"] = 10.0
    target["strength"] = 2.0

    loaded = client.post("/state/load", json={"state": state})
    assert loaded.status_code == 200
    stepped = client.post("/step", json={"dt": 1.0, "steps": 1})
    assert stepped.status_code == 200
    assert all(unit["id"] != target["id"] for unit in stepped.json()["units"])
    events = client.get("/events")
    assert events.status_code == 200
    assert any(event["category"] == "combat_ineffective" and event["unit_id"] == target["id"] for event in events.json()["events"])


def test_red_reserves_activate_after_first_wave_tank_losses() -> None:
    client = make_client()
    state = client.get("/state").json()
    reserve_ids = [
        unit["id"]
        for unit in state["units"]
        if unit["side"] == "red" and unit["kind"] == "tank" and unit.get("reserve_trigger_loss_ratio") is not None
    ]
    assert reserve_ids
    assert all(not unit["present"] for unit in state["units"] if unit["id"] in reserve_ids)
    reserve_strength = sum(unit["strength"] for unit in state["units"] if unit["id"] in reserve_ids)
    assert state["summary"]["reserve_pending_strength"] == reserve_strength
    assert state["summary"]["red_strength"] >= reserve_strength

    for unit in state["units"]:
        if unit["side"] == "red" and unit["kind"] == "tank" and unit.get("reserve_trigger_loss_ratio") is None:
            unit["strength"] = unit["max_strength"] * 0.60

    loaded = client.post("/state/load", json={"state": state})
    assert loaded.status_code == 200
    stepped = client.post("/step", json={"dt": 1.0, "steps": 1})
    assert stepped.status_code == 200
    summary = stepped.json()["summary"]
    assert summary["red_tank_loss_ratio"] >= 0.30
    assert summary["reserve_triggered_units"] == len(reserve_ids)
    triggered = [unit for unit in stepped.json()["units"] if unit["id"] in reserve_ids]
    assert triggered
    assert all(unit["reserve_triggered"] and unit["present"] for unit in triggered)


def test_unit_command_updates_waypoint() -> None:
    client = make_client()
    state = client.get("/state").json()
    unit_id = state["units"][0]["id"]
    response = client.post(
        f"/command/unit/{unit_id}",
        json={"waypoints": [[1234.0, 5678.0]], "intent": "move", "priority": "normal"},
    )
    assert response.status_code == 200
    updated = next(unit for unit in response.json()["units"] if unit["id"] == unit_id)
    assert updated["waypoints"] == [[1234.0, 5678.0]]
    assert updated["order"]["intent"] == "move"


def test_unit_command_edits_position_and_waypoint_stack() -> None:
    client = make_client()
    state = client.get("/state").json()
    unit_id = state["units"][0]["id"]

    moved = client.post(
        f"/command/unit/{unit_id}",
        json={"position": [2222.0, 3333.0], "waypoints": [], "intent": "edit_position"},
    )
    assert moved.status_code == 200
    unit = next(unit for unit in moved.json()["units"] if unit["id"] == unit_id)
    assert unit["x"] == 2222.0
    assert unit["y"] == 3333.0

    appended = client.post(
        f"/command/unit/{unit_id}",
        json={"append_waypoint": [2444.0, 3555.0], "intent": "move", "priority": "normal"},
    )
    assert appended.status_code == 200
    unit = next(unit for unit in appended.json()["units"] if unit["id"] == unit_id)
    assert unit["waypoints"][-1] == [2444.0, 3555.0]

    removed = client.post(
        f"/command/unit/{unit_id}",
        json={"remove_last_waypoint": True, "intent": "move"},
    )
    assert removed.status_code == 200
    unit = next(unit for unit in removed.json()["units"] if unit["id"] == unit_id)
    assert [2444.0, 3555.0] not in unit["waypoints"]


def test_terrain_and_dump_load_contracts() -> None:
    client = make_client()
    terrain = client.get("/terrain")
    assert terrain.status_code == 200
    payload = terrain.json()
    assert payload["rows"] > 0
    assert payload["cols"] > 0
    assert payload["cells"]
    assert "elevation_m" in payload["cells"][0]

    dump = client.get("/state/dump")
    assert dump.status_code == 200
    dumped = dump.json()
    assert dumped["schema_version"] == "2026-05-20.1"

    moved_state = dumped["state"]
    first = moved_state["units"][0]
    first["x"] += 10.0
    load = client.post("/state/load", json={"state": moved_state})
    assert load.status_code == 200
    loaded_first = next(unit for unit in load.json()["units"] if unit["id"] == first["id"])
    assert loaded_first["x"] == first["x"]


def test_config_dump_load_and_add_unit() -> None:
    client = make_client()
    config = client.get("/config/dump")
    assert config.status_code == 200
    assert config.json()["parameters"]["target_area_scale"] == 1.0
    original_matrix = config.json()["lanchester_matrix"]
    tuned_alpha = float(original_matrix["Tiger_I"]["T-34"]) + 0.0002

    loaded = client.post(
        "/config/load",
        json={
            "parameters": {"target_area_scale": 2.0},
            "lanchester_matrix": {"Tiger_I": {"T-34": tuned_alpha}},
        },
    )
    assert loaded.status_code == 200
    assert loaded.json()["parameters"]["target_area_scale"] == 2.0
    assert loaded.json()["lanchester_matrix"]["Tiger_I"]["T-34"] == tuned_alpha

    count_before = len(loaded.json()["units"])
    added = client.post(
        "/units",
        json={
            "name": "Operator Added Battery",
            "side": "blue",
            "kind": "artillery",
            "type": "M-30",
            "position": [1100.0, 1200.0],
            "strength": 4.0,
            "shell_damage": 1.2,
            "shell_range_m": 9000.0,
            "shell_speed_mps": 420.0,
            "shell_dispersion_m": 120.0,
            "fire_rate_per_min": 2.0,
            "ammo_remaining": 12,
            "echelon": "III",
            "reserve_trigger_side": "blue",
            "reserve_trigger_kind": "tank",
            "reserve_trigger_loss_ratio": 0.3,
            "active_after_s": 999999.0,
            "present_after_s": 999999.0,
            "detectable_after_s": 999999.0,
            "targetable_after_s": 999999.0,
            "maneuver_after_s": 999999.0,
            "engage_after_s": 999999.0,
        },
    )
    assert added.status_code == 200
    assert len(added.json()["units"]) == count_before + 1
    added_unit = next(unit for unit in added.json()["units"] if unit["name"] == "Operator Added Battery")
    assert added_unit["echelon"] == "III"
    assert added_unit["reserve_trigger_loss_ratio"] == 0.3
    assert added_unit["present"] is False


def test_scenario_has_three_axis_waypoints_and_echelon_markers() -> None:
    client = make_client()
    state = client.get("/state").json()
    units = state["units"]
    bounds = state["terrain"]["bounds"]
    min_x, min_y, max_x, max_y = map(float, bounds)

    def normalized(point: list[float]) -> tuple[float, float]:
        x, y = float(point[0]), float(point[1])
        return ((x - min_x) / (max_x - min_x), (y - min_y) / (max_y - min_y))

    bands = {
        "left_river_west": (0.04, 0.34, 0.28, 0.70),
        "center": (0.40, 0.66, 0.34, 0.75),
        "lower_right": (0.68, 0.96, 0.32, 0.78),
    }
    hits = {name: 0 for name in bands}
    deep_waypoint_units = 0
    blue_tank_starts: list[tuple[float, float]] = []
    red_tank_starts: list[tuple[float, float]] = []
    for unit in units:
        assert "echelon" in unit
        if unit["kind"] != "tank":
            continue
        start = (float(unit["x"]), float(unit["y"]))
        if unit["side"] == "blue":
            blue_tank_starts.append(start)
        elif unit["side"] == "red":
            red_tank_starts.append(start)
        waypoints = unit.get("waypoints", [])
        if len(waypoints) >= 4:
            deep_waypoint_units += 1
            final_x, final_y = float(waypoints[-1][0]), float(waypoints[-1][1])
            if unit["side"] == "blue":
                assert final_x > start[0]
                assert final_y > start[1]
            elif unit["side"] == "red":
                assert final_x < start[0]
                assert final_y < start[1]
        for waypoint in waypoints[:3]:
            nx, ny = normalized(waypoint)
            for name, (x0, x1, y0, y1) in bands.items():
                if x0 <= nx <= x1 and y0 <= ny <= y1:
                    hits[name] += 1

    assert all(count > 0 for count in hits.values())
    assert deep_waypoint_units >= 20
    assert blue_tank_starts
    assert red_tank_starts
    assert sum(x for x, _ in blue_tank_starts) / len(blue_tank_starts) < sum(
        x for x, _ in red_tank_starts
    ) / len(red_tank_starts)
    assert sum(y for _, y in blue_tank_starts) / len(blue_tank_starts) < sum(
        y for _, y in red_tank_starts
    ) / len(red_tank_starts)
    assert min(x for x, _ in blue_tank_starts) < min_x + (max_x - min_x) * 0.12
    assert any(
        float(unit["waypoints"][-1][0]) < min_x + (max_x - min_x) * 0.18
        for unit in units
        if unit["side"] == "red" and unit["kind"] == "tank" and unit["waypoints"]
    )

    for starts in [blue_tank_starts, red_tank_starts]:
        nearest = [
            min(dist(point, other) for j, other in enumerate(starts) if i != j)
            for i, point in enumerate(starts)
        ]
        assert sum(nearest) / len(nearest) > 750.0


def test_lanchester_matrix_can_be_tuned_per_pair() -> None:
    client = make_client()
    matrix = client.get("/lanchester/matrix")
    assert matrix.status_code == 200
    payload = matrix.json()
    assert "Tiger_I" in payload["matrix"]
    original = float(payload["matrix"]["Tiger_I"]["T-34"])

    updated = client.patch("/lanchester/matrix", json={"matrix": {"Tiger_I": {"T-34": original + 0.0003}}})
    assert updated.status_code == 200
    assert updated.json()["matrix"]["Tiger_I"]["T-34"] == original + 0.0003

    state = client.get("/state").json()
    assert state["lanchester_matrix"]["Tiger_I"]["T-34"] == original + 0.0003


def test_engagements_and_artillery_area_outputs() -> None:
    client = make_client()
    state = client.get("/state").json()
    bounds = state["terrain"]["bounds"]
    x = (bounds[0] + bounds[2]) / 2.0
    y = (bounds[1] + bounds[3]) / 2.0
    blue = client.post(
        "/units",
        json={
            "name": "Blue Close Tank",
            "side": "blue",
            "kind": "tank",
            "type": "t34",
            "position": [x, y],
            "strength": 12.0,
            "max_strength": 12.0,
            "detection_range_m": 5000.0,
            "lanchester_range_m": 3000.0,
        },
    )
    assert blue.status_code == 200
    red = client.post(
        "/units",
        json={
            "name": "Red Close Tank",
            "side": "red",
            "kind": "tank",
            "type": "panzer_iv",
            "position": [x + 100.0, y + 100.0],
            "strength": 12.0,
            "max_strength": 12.0,
            "detection_range_m": 5000.0,
            "lanchester_range_m": 3000.0,
        },
    )
    assert red.status_code == 200
    recon = client.post(
        "/units",
        json={
            "name": "Red Forward Observer",
            "side": "red",
            "kind": "recon",
            "type": "Recon",
            "position": [x - 150.0, y],
            "strength": 4.0,
            "max_strength": 4.0,
            "speed_mps": 13.0,
            "detection_range_m": 6000.0,
            "command_range_m": 20000.0,
            "lanchester_range_m": 0.0,
        },
    )
    assert recon.status_code == 200
    stepped = client.post("/step", json={"dt": 1.0, "steps": 5})
    assert stepped.status_code == 200
    engagements = client.get("/engagements")
    assert engagements.status_code == 200
    assert "engagements" in engagements.json()
    assert any("last_k" in contact for contact in engagements.json()["engagements"])

    artillery_payload = {}
    for _ in range(10):
        artillery = client.post("/step", json={"dt": 30.0, "steps": 1})
        assert artillery.status_code == 200
        artillery_payload = artillery.json()
        if any(mission.get("detector_name") == "Red Forward Observer" for mission in artillery_payload["fire_missions"]):
            break
    assert any(mission.get("detector_name") == "Red Forward Observer" for mission in artillery_payload["fire_missions"])
    assert any(shell.get("radius_m", 0.0) > 0.0 for shell in artillery_payload["shells"])


def test_artillery_wta_requires_recon_report_chain() -> None:
    client = make_client()
    state = client.get("/state").json()
    for unit in state["units"]:
        if unit["kind"] == "recon":
            deleted = client.post(f"/units/{unit['id']}/delete")
            assert deleted.status_code == 200

    red_artillery = next(unit for unit in client.get("/state").json()["units"] if unit["side"] == "red" and unit["kind"] == "artillery")
    blue_target = client.post(
        "/units",
        json={
            "name": "Blue WTA Target",
            "side": "blue",
            "kind": "tank",
            "type": "PzIV",
            "position": [red_artillery["x"] - 1200.0, red_artillery["y"]],
            "strength": 10.0,
            "max_strength": 10.0,
            "detection_range_m": 3000.0,
            "lanchester_range_m": 0.0,
        },
    )
    assert blue_target.status_code == 200

    without_recon = client.post("/step", json={"dt": 30.0, "steps": 1})
    assert without_recon.status_code == 200
    assert not any(mission.get("target_name") == "Blue WTA Target" for mission in without_recon.json()["fire_missions"])

    recon = client.post(
        "/units",
        json={
            "name": "Red WTA Recon",
            "side": "red",
            "kind": "recon",
            "type": "Recon",
            "position": [red_artillery["x"] - 1350.0, red_artillery["y"]],
            "strength": 4.0,
            "max_strength": 4.0,
            "speed_mps": 13.0,
            "detection_range_m": 4500.0,
            "command_range_m": 20000.0,
            "lanchester_range_m": 0.0,
        },
    )
    assert recon.status_code == 200
    recon_id = next(unit["id"] for unit in recon.json()["units"] if unit["name"] == "Red WTA Recon")

    with_recon_payload = {}
    for _ in range(60):
        with_recon = client.post("/step", json={"dt": 5.0, "steps": 1})
        assert with_recon.status_code == 200
        with_recon_payload = with_recon.json()
        if any(mission.get("target_name") == "Blue WTA Target" for mission in with_recon_payload["fire_missions"]):
            break
    missions = [mission for mission in with_recon_payload["fire_missions"] if mission.get("target_name") == "Blue WTA Target"]
    assert missions
    assert missions[0]["detector_name"] == "Red WTA Recon"
    events = client.get("/events").json()["events"]
    assert any(event["category"] == "intel_relay" and event["unit_id"] == recon_id for event in events)
    assert any(event["category"] == "artillery_target" and event["data"].get("wta") for event in events)


def test_unit_holds_waypoint_movement_while_engaged() -> None:
    client = make_client()
    state = client.get("/state").json()
    bounds = state["terrain"]["bounds"]
    x = (bounds[0] + bounds[2]) / 2.0
    y = (bounds[1] + bounds[3]) / 2.0

    blue = client.post(
        "/units",
        json={
            "name": "Blue Moving Contact",
            "side": "blue",
            "kind": "tank",
            "type": "PzIV",
            "position": [x, y],
            "strength": 30.0,
            "max_strength": 30.0,
            "speed_mps": 10.0,
            "detection_range_m": 5000.0,
            "lanchester_range_m": 3000.0,
        },
    )
    assert blue.status_code == 200
    red = client.post(
        "/units",
        json={
            "name": "Red Blocking Contact",
            "side": "red",
            "kind": "tank",
            "type": "T-34",
            "position": [x + 80.0, y + 80.0],
            "strength": 30.0,
            "max_strength": 30.0,
            "speed_mps": 10.0,
            "detection_range_m": 5000.0,
            "lanchester_range_m": 3000.0,
        },
    )
    assert red.status_code == 200

    blue_id = next(unit["id"] for unit in blue.json()["units"] if unit["name"] == "Blue Moving Contact")
    commanded = client.post(
        f"/command/unit/{blue_id}",
        json={"waypoints": [[x + 1200.0, y]], "intent": "move", "priority": "normal"},
    )
    assert commanded.status_code == 200

    first_step = client.post("/step", json={"dt": 1.0, "steps": 1})
    assert first_step.status_code == 200
    assert client.get("/engagements").json()["engagements"]
    before = next(unit for unit in first_step.json()["units"] if unit["id"] == blue_id)

    second_step = client.post("/step", json={"dt": 10.0, "steps": 1})
    assert second_step.status_code == 200
    after = next(unit for unit in second_step.json()["units"] if unit["id"] == blue_id)
    assert after["x"] == before["x"]
    assert after["y"] == before["y"]
    assert after["waypoints"] == before["waypoints"]


def test_websocket_state_step_roundtrip() -> None:
    client = make_client()
    with client.websocket_connect("/ws/state") as websocket:
        initial = websocket.receive_json()
        assert initial["type"] == "state"
        websocket.send_json({"type": "step", "dt": 0.1, "steps": 2})
        update = websocket.receive_json()
        assert update["type"] == "state"
        assert update["payload"]["time_s"] > initial["payload"]["time_s"]


def test_websocket_reports_invalid_messages_without_closing() -> None:
    client = make_client()
    with client.websocket_connect("/ws/state") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "step", "dt": -1, "steps": 1})
        error = websocket.receive_json()
        assert error["type"] == "error"

        websocket.send_json({"type": "command_unit", "unit_id": "missing", "payload": {"waypoints": [[1, 2]]}})
        error = websocket.receive_json()
        assert error["type"] == "error"

        websocket.send_json({"type": "state"})
        state = websocket.receive_json()
        assert state["type"] == "state"


def test_websocket_updates_runtime_parameters() -> None:
    client = make_client()
    with client.websocket_connect("/ws/state") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "set_parameters", "payload": {"artillery_damage_scale": 1.7}})
        update = websocket.receive_json()
        assert update["type"] == "state"
        assert update["payload"]["parameters"]["artillery_damage_scale"] == 1.7

        websocket.send_json({"type": "set_parameters", "payload": {"target_area_scale": 99.0}})
        error = websocket.receive_json()
        assert error["type"] == "error"


def test_delete_unit_and_state_load_replace_unit_set() -> None:
    client = make_client()
    state = client.get("/state").json()
    removed_id = state["units"][0]["id"]

    deleted = client.post(f"/units/{removed_id}/delete")
    assert deleted.status_code == 200
    assert all(unit["id"] != removed_id for unit in deleted.json()["units"])

    restored_state = state.copy()
    restored_state["units"] = state["units"][:2]
    restored_state["units"][0]["waypoints"] = [[1111.0, 2222.0]]
    restored_state["units"][0]["order"] = {"intent": "move"}
    loaded = client.post("/state/load", json={"state": restored_state})
    assert loaded.status_code == 200
    units = loaded.json()["units"]
    assert len(units) == 2
    assert units[0]["id"] == restored_state["units"][0]["id"]
    assert units[0]["waypoints"] == [[1111.0, 2222.0]]
    assert units[0]["order"]["intent"] == "move"


def test_lanchester_matrix_is_directional_and_locks_same_side_pairs() -> None:
    client = make_client()
    payload = client.get("/lanchester/matrix").json()
    assert "red_unit_types" in payload and "blue_unit_types" in payload
    assert "T-34" in payload["red_unit_types"]
    assert "PzIV" in payload["blue_unit_types"]
    assert payload["unit_type_sides"]["T-34"] == "red"
    assert payload["unit_type_sides"]["Tiger_I"] == "blue"
    assert payload["symmetric"] is False

    original = float(payload["matrix"]["Tiger_I"]["T-34"])
    reverse_original = float(payload["matrix"]["T-34"]["Tiger_I"])
    same_side_original = float(payload["matrix"]["Tiger_I"]["PzIII"])
    tuned = original + 0.00031
    updated = client.patch(
        "/lanchester/matrix",
        json={"matrix": {"Tiger_I": {"T-34": tuned, "PzIII": same_side_original + 0.01}}},
    )
    assert updated.status_code == 200
    assert updated.json()["matrix"]["Tiger_I"]["T-34"] == tuned
    assert updated.json()["matrix"]["T-34"]["Tiger_I"] == reverse_original
    assert updated.json()["matrix"]["Tiger_I"]["PzIII"] == same_side_original


def test_step_stops_when_one_side_has_no_tanks() -> None:
    client = make_client()
    state = client.get("/state").json()
    for unit in state["units"]:
        if unit["side"] == "blue" and unit["kind"] == "tank":
            unit["strength"] = 0.0
    loaded = client.post("/state/load", json={"state": state})
    assert loaded.status_code == 200
    assert loaded.json()["summary"]["ended"] is True
    assert loaded.json()["summary"]["winner"] == "red"
    before = loaded.json()["time_s"]
    stepped = client.post("/step", json={"dt": 30.0, "steps": 20})
    assert stepped.status_code == 200
    assert stepped.json()["time_s"] == before
    assert stepped.json()["summary"]["progress_ratio"] == 1.0
