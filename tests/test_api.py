from __future__ import annotations

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
    assert "detection_range_m" in payload["units"][0]
    assert "lanchester_range_m" in payload["units"][0]
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

    updated = client.patch(
        "/parameters",
        json={"direct_fire_scale": 1.4, "combat_speed_scale": 0.75, "artillery_delay_s": 300.0, "target_area_scale": 1.5},
    )
    assert updated.status_code == 200
    assert updated.json()["parameters"]["direct_fire_scale"] == 1.4
    assert updated.json()["parameters"]["combat_speed_scale"] == 0.75
    assert updated.json()["parameters"]["artillery_delay_s"] == 300.0
    assert updated.json()["parameters"]["target_area_scale"] == 1.5

    reset = client.post("/reset", json={})
    assert reset.status_code == 200
    assert reset.json()["parameters"]["direct_fire_scale"] == 1.4
    assert reset.json()["parameters"]["combat_speed_scale"] == 0.75
    assert reset.json()["parameters"]["artillery_delay_s"] == 300.0

    rejected = client.patch("/parameters", json={"direct_fire_scale": 100.0})
    assert rejected.status_code == 422


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
        },
    )
    assert added.status_code == 200
    assert len(added.json()["units"]) == count_before + 1
    assert any(unit["name"] == "Operator Added Battery" for unit in added.json()["units"])


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
    for _ in range(4):
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
    for _ in range(6):
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
