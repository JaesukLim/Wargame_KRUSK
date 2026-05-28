extends Node

signal state_received(state: Dictionary)
signal events_received(events_payload: Dictionary)
signal parameters_received(parameters_payload: Dictionary)
signal matrix_received(matrix_payload: Dictionary)
signal replay_received(replay_payload: Dictionary)
signal terrain_received(terrain_payload: Dictionary)
signal engagements_received(engagements_payload: Dictionary)
signal config_dump_received(config_payload: Dictionary)
signal state_dump_received(state_payload: Dictionary)
signal backend_error(message: String)

@export var http_base_url: String = "http://127.0.0.1:8765"
@export var websocket_url: String = "ws://127.0.0.1:8765/ws/state"
@export var packaged_backend_name: String = "WargameKRUSKBackend.exe"
@export var packaged_backend_unix_name: String = "WargameKRUSKBackend"

var _socket := WebSocketPeer.new()
var _socket_connected := false
var _packaged_backend_pid := -1

func _ready() -> void:
    _start_packaged_backend_if_available()
    set_process(true)

func _notification(what: int) -> void:
    if what == NOTIFICATION_PREDELETE or what == NOTIFICATION_WM_CLOSE_REQUEST:
        _stop_packaged_backend()

func connect_websocket() -> void:
    var err := _socket.connect_to_url(websocket_url)
    if err != OK:
        backend_error.emit("WebSocket 연결 실패: %s" % err)
        return
    _socket_connected = true

func close_websocket() -> void:
    _socket.close()
    _socket_connected = false

func _start_packaged_backend_if_available() -> void:
    if OS.has_feature("editor"):
        return
    if not http_base_url.begins_with("http://127.0.0.1:8765") and not http_base_url.begins_with("http://localhost:8765"):
        return
    var exe_dir := OS.get_executable_path().get_base_dir()
    var backend_names := PackedStringArray([packaged_backend_name, packaged_backend_unix_name])
    var candidates := PackedStringArray()
    for backend_name in backend_names:
        candidates.append(exe_dir.path_join(backend_name))
        candidates.append(exe_dir.path_join("backend").path_join(backend_name))
    for backend_path in candidates:
        if not FileAccess.file_exists(backend_path):
            continue
        var log_dir := backend_path.get_base_dir().path_join("logs")
        DirAccess.make_dir_recursive_absolute(log_dir)
        var args := PackedStringArray(["--mode", "serve", "--host", "127.0.0.1", "--port", "8765", "--log-dir", log_dir])
        print("Starting packaged backend: ", backend_path)
        var pid := OS.create_process(backend_path, args, false)
        if pid > 0:
            _packaged_backend_pid = pid
            print("Packaged backend process started: ", pid)
        else:
            backend_error.emit("Packaged backend start failed: %s" % backend_path)
            push_error("Packaged backend start failed: %s" % backend_path)
        return
    backend_error.emit("Packaged backend executable not found next to WargameKRUSK.exe")
    push_warning("Packaged backend executable not found next to WargameKRUSK.exe")

func _stop_packaged_backend() -> void:
    if _packaged_backend_pid <= 0:
        return
    OS.kill(_packaged_backend_pid)
    _packaged_backend_pid = -1

func request_state() -> void:
    _request("GET", "/state", {}, "state")

func request_events() -> void:
    _request("GET", "/events", {}, "events")

func request_parameters() -> void:
    _request("GET", "/parameters", {}, "parameters")

func request_lanchester_matrix() -> void:
    _request("GET", "/lanchester/matrix", {}, "matrix")

func request_replay() -> void:
    _request("GET", "/state/replay", {}, "replay")

func generate_replay(dt: float = 30.0, max_steps: int = 120, sample_every_steps: int = 1) -> void:
    _request("POST", "/state/replay/generate", {"dt": dt, "max_steps": max_steps, "sample_every_steps": sample_every_steps}, "replay")

func generate_replay_timeline(frame_interval_s: float = 3600.0, frames: int = 120, integration_dt_s: float = 300.0) -> void:
    _request("POST", "/state/replay/generate", {"frame_interval_s": frame_interval_s, "frames": frames, "integration_dt_s": integration_dt_s, "stop_on_terminal": true}, "replay")

func request_terrain() -> void:
    _request("GET", "/terrain", {}, "terrain")

func request_engagements() -> void:
    _request("GET", "/engagements", {}, "engagements")

func dump_config() -> void:
    _request("GET", "/config/dump", {}, "config_dump")

func load_config(payload: Dictionary) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "load_config", "payload": payload}))
    else:
        _request("POST", "/config/load", payload, "config_load")

func dump_state() -> void:
    _request("GET", "/state/dump", {}, "state_dump")

func load_state(payload: Dictionary) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "load_state", "payload": payload}))
    else:
        _request("POST", "/state/load", payload, "state_load")

func add_unit(payload: Dictionary) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "add_unit", "payload": payload}))
    else:
        _request("POST", "/units", payload, "add_unit")

func delete_unit(unit_id: String) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "delete_unit", "unit_id": unit_id}))
    else:
        _request("POST", "/units/%s/delete" % unit_id, {}, "delete_unit")

func update_parameters(payload: Dictionary) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "set_parameters", "payload": payload}))
    else:
        _request("PATCH", "/parameters", payload, "set_parameters")

func update_lanchester_matrix(payload: Dictionary) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "set_lanchester_matrix", "payload": payload}))
    else:
        _request("PATCH", "/lanchester/matrix", payload, "matrix")

func reset() -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "reset", "payload": {}}))
    else:
        _request("POST", "/reset", {}, "reset")

func step(dt: float = 30.0, steps: int = 1) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "step", "dt": dt, "steps": steps}))
    else:
        _request("POST", "/step", {"dt": dt, "steps": steps}, "step")

func command_unit(unit_id: String, payload: Dictionary) -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"type": "command_unit", "unit_id": unit_id, "payload": payload}))
    else:
        _request("POST", "/command/unit/%s" % unit_id, payload, "command")

func _process(_delta: float) -> void:
    if not _socket_connected:
        return
    _socket.poll()
    var state := _socket.get_ready_state()
    if state == WebSocketPeer.STATE_OPEN:
        while _socket.get_available_packet_count() > 0:
            var text := _socket.get_packet().get_string_from_utf8()
            var parsed = JSON.parse_string(text)
            if typeof(parsed) == TYPE_DICTIONARY:
                if parsed.get("type", "") == "error":
                    backend_error.emit(str(parsed.get("message", "WebSocket error")))
                elif parsed.has("payload"):
                    state_received.emit(parsed["payload"])
    elif state == WebSocketPeer.STATE_CLOSED:
        _socket_connected = false

func _request(method: String, path: String, payload: Dictionary, label: String) -> void:
    var req := HTTPRequest.new()
    var parent: Node = get_tree().root if get_tree() != null else self
    req.request_completed.connect(_on_request_completed.bind(req, label))
    var headers := PackedStringArray(["Content-Type: application/json"])
    var body := ""
    var http_method := HTTPClient.METHOD_GET
    if method == "POST":
        http_method = HTTPClient.METHOD_POST
        body = JSON.stringify(payload)
    elif method == "PATCH":
        http_method = HTTPClient.METHOD_PATCH
        body = JSON.stringify(payload)
    parent.add_child.call_deferred(req)
    _start_request.call_deferred(req, http_base_url + path, headers, http_method, body, label)

func _start_request(req: HTTPRequest, url: String, headers: PackedStringArray, http_method: int, body: String, label: String) -> void:
    if not is_instance_valid(req):
        return
    var err := req.request(url, headers, http_method, body)
    if err != OK:
        req.queue_free()
        backend_error.emit("HTTP 요청 실패(%s): %s" % [label, err])

func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray, req: HTTPRequest, label: String) -> void:
    req.queue_free()
    if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
        backend_error.emit("Backend 응답 오류(%s): result=%s code=%s" % [label, result, response_code])
        return
    var parsed = JSON.parse_string(body.get_string_from_utf8())
    if typeof(parsed) != TYPE_DICTIONARY:
        backend_error.emit("Backend JSON 파싱 실패(%s)" % label)
        return
    if label == "events":
        events_received.emit(parsed)
    elif label == "parameters":
        parameters_received.emit(parsed)
        if parsed.has("lanchester_matrix"):
            matrix_received.emit(parsed["lanchester_matrix"])
    elif label == "matrix":
        matrix_received.emit(parsed)
    elif label == "replay":
        replay_received.emit(parsed)
    elif label == "terrain":
        terrain_received.emit(parsed)
    elif label == "engagements":
        engagements_received.emit(parsed)
    elif label == "config_dump":
        config_dump_received.emit(parsed)
    elif label == "state_dump":
        state_dump_received.emit(parsed)
    else:
        state_received.emit(parsed)
