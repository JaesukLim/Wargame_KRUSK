extends Control

const RED := Color(0.86, 0.18, 0.14)
const BLUE := Color(0.38, 0.60, 0.92)
const GOLD := Color(0.94, 0.76, 0.25)
const GREEN := Color(0.38, 0.74, 0.34)
const BG := Color(0.025, 0.030, 0.032)
const PANEL := Color(0.045, 0.055, 0.058, 1.0)
const PANEL_DARK := Color(0.030, 0.037, 0.039, 1.0)
const LINE := Color(0.22, 0.27, 0.27)
const TEXT := Color(0.94, 0.95, 0.90)
const MUTED := Color(0.66, 0.70, 0.67)
const TEXT_SHADOW := Color(0.0, 0.0, 0.0, 0.72)
const MAP_TAN := Color(0.45, 0.42, 0.28)
const BASE_VIEWPORT := Vector2(1920.0, 1080.0)
const MIN_UI_SCALE := 1.15
const MAX_UI_SCALE := 1.45

const STEP_SECONDS := 300.0
const REPLAY_SCENARIO_FRAME_INTERVAL_S := 726.050420168
const REPLAY_SCENARIO_FRAMES := 120
const REPLAY_SCENARIO_INTEGRATION_DT_S := 300.0
const LIVE_STEP_REAL_INTERVAL := 0.75
const REPLAY_FRAME_INTERVAL := 0.08
const REPLAY_MAX_FRAMES_PER_TICK := 10
const TERRAIN_XZ_SCALE := 0.018
const TERRAIN_ELEV_SCALE := 0.42
const INITIAL_RED_STRENGTH := 990.0
const INITIAL_BLUE_STRENGTH := 470.0
const ACTUAL_MAP_PATH := "res://data/actual_map.png"
const KOREAN_FONT_PATH := "res://fonts/NotoSansKR.ttf"
var _state: Dictionary = {}
var _ui_font: Font = null
var _events: Array = []
var _history: Array = []
var _selected_unit_id := ""
var _status := "Waiting for Python backend"
var _active_oob_side := "red"
var _parameters: Dictionary = {
    "direct_fire_scale": 1.0,
    "artillery_delay_s": 240.0,
    "artillery_damage_scale": 1.0,
    "target_area_scale": 1.0,
    "combat_speed_scale": 0.60,
    "red_force_end_ratio": 0.50,
    "blue_tank_end_count": 0.0,
    "unit_removal_ratio": 0.20,
}
var _parameter_schema: Dictionary = {
    "direct_fire_scale": {"min": 0.1, "max": 3.0, "step": 0.1, "label": "Direct alpha"},
    "artillery_delay_s": {"min": 25.0, "max": 600.0, "step": 15.0, "label": "Artillery delay"},
    "artillery_damage_scale": {"min": 0.1, "max": 3.0, "step": 0.1, "label": "Artillery damage"},
    "target_area_scale": {"min": 0.25, "max": 4.0, "step": 0.25, "label": "Target area"},
    "combat_speed_scale": {"min": 0.25, "max": 2.0, "step": 0.05, "label": "Combat speed"},
    "red_force_end_ratio": {"min": 0.05, "max": 0.95, "step": 0.05, "label": "Red end ratio"},
    "blue_tank_end_count": {"min": 0.0, "max": 20.0, "step": 1.0, "label": "Blue tank end"},
    "unit_removal_ratio": {"min": 0.0, "max": 0.90, "step": 0.05, "label": "Unit removal"},
}
var _playing := false
var _speed_index := 1
var _speeds := [1.0, 2.0, 4.0, 8.0, 16.0]
var _replay_fps_index := 2
var _replay_fps_options := [2, 5, 10, 20, 30, 60]
var _step_timer := 0.0
var _backend_last_retry_ms := 0
var _backend_live := false
var _screenshot_path := ""
var _pending_screenshot := false
var _screenshot_frames := 0
var _screenshot_start_ms := 0
var _precompute_replay_on_start := false
var _precompute_replay_requested := false

var _left_rect := Rect2()
var _map_rect := Rect2()
var _right_rect := Rect2()
var _bottom_rect := Rect2()
var _buttons: Array = []
var _scroll_left_oob := 0.0
var _left_dragging := false
var _left_drag_last := Vector2.ZERO
var _input_smoke_path := ""
var _input_smoke_started := false
var _input_smoke_clicked := false
var _input_smoke_start_time := -1.0
var _input_smoke_real_start_ms := 0
var _input_smoke_frames := 0
var _input_smoke_actions := ["state", "oob_blue", "oob_red", "view_3d", "cam_forward", "cam_zoom_in", "cam_rotate_right", "cam_reset", "tool_move", "tool_fire", "order_attack", "order_defend", "order_retreat", "order_move", "queue_add", "add_reserve_toggle", "add_reserve_ratio", "add_echelon", "add_unit", "queue_clear", "dialog_params", "config_dump", "file_save_confirm", "dialog_params", "state_dump", "file_save_confirm", "file_unitset_save", "file_save_confirm", "unit_type_next", "unit_type_prev", "edit_position", "waypoint_append", "waypoint_remove_last", "waypoint_clear", "dialog_params", "param_commit", "dialog_close", "dialog_help", "dialog_close", "dialog_stats", "dialog_close", "view_2d", "step"]
var _input_smoke_action_index := 0
var _input_smoke_executed: Array = []
var _view_mode := "2d"
var _battle_view_expanded := false
var _tool_mode := "select"
var _show_detection_ranges := false
var _grid_size_input: LineEdit = null
var _grid_cell_size_override := 0.0   # 0 = use backend value
var _grid_input_rect := Rect2()
var _order_mode := "move"
var _unit_orders: Dictionary = {}
var _manual_queue: Array = []
var _replay_frames: Array = []
var _replay_index := -1
var _replay_playing := false
var _replay_timer := 0.0
var _replay_autoplay_after_generate := false
var _pending_replay_back := false
var _replay_calculating := false
var _last_replay_meta: Dictionary = {}
var _history_from_replay := false
var _last_detection_redraw_ms := 0
var _terrain_payload: Dictionary = {}
var _terrain_cells: Array = []
var _actual_map_texture: Texture2D = null
var _engagements: Array = []
var _last_dump: Dictionary = {}
var _lanchester_payload: Dictionary = {}
var _lanchester_matrix: Dictionary = {}
var _active_dialog := ""
var _camera_pan := Vector2.ZERO
var _camera_yaw := 0.0
var _camera_distance := 230.0
var _camera_height := 92.0
var _camera_pitch := 24.0
var _camera_dragging := false
var _camera_drag_last := Vector2.ZERO
var _map_zoom := 1.0
var _map_pan := Vector2.ZERO
var _map_dragging := false
var _map_drag_last := Vector2.ZERO
var _viewport_container_3d: SubViewportContainer
var _viewport_3d: SubViewport
var _terrain_root_3d: Node3D
var _combat_root_3d: Node3D
var _camera_3d: Camera3D
var _unit_meshes_3d: Dictionary = {}
var _last_3d_view_rect := Rect2()
var _units_3d_dirty := true
var _effects_3d_dirty := true
var _terrain_mesh_ready := false
var _known_tank_type_max_by_side := {"red": {}, "blue": {}}
var _editing_parameter_key := ""
var _parameter_input_buffer := ""
var _editing_matrix_key := ""
var _matrix_input_buffer := ""
var _selected_unit_type_index := 0
var _pending_added_unit_name := ""
var _file_dialog_mode := ""
var _file_name_buffer := "default"
var _editing_file_name := false
var _file_dialog_items: Array = []
var _file_dialog_scroll := 0.0
var _pending_named_dump_kind := ""
var _pending_named_dump_name := ""
var _oob_scroll_track := Rect2()
var _oob_scroll_knob := Rect2()
var _oob_scroll_max := 0.0
var _file_scroll_track := Rect2()
var _file_scroll_knob := Rect2()
var _file_scroll_max := 0.0
var _event_log_rect := Rect2()
var _event_log_scroll := 0
var _event_log_max_scroll := 0
var _scroll_drag_target := ""
var _scroll_drag_offset := 0.0
var _timeline_seek_rect := Rect2()
var _timeline_seek_dragging := false
var _add_unit_as_reserve := false
var _add_unit_reserve_ratio_options := [0.10, 0.20, 0.30, 0.40, 0.50]
var _add_unit_reserve_ratio_index := 2
var _add_unit_echelon_options := ["I", "II", "III", "XX", "XXX", "XXXX"]
var _add_unit_echelon_index := 0
const SAVE_ROOT := "user://wargame_saves"
var _unit_type_options := [
    {"label": "Red T-34 tank", "side": "red", "kind": "tank", "type": "T-34", "echelon": "I", "strength": 18.0, "speed_mps": 10.0, "armor": 1.0, "detection_range_m": 2450.0, "lanchester_range_m": 1800.0},
    {"label": "Red T-70 light tank", "side": "red", "kind": "tank", "type": "T-70", "echelon": "I", "strength": 14.0, "speed_mps": 12.0, "armor": 0.72, "detection_range_m": 2450.0, "lanchester_range_m": 1700.0},
    {"label": "Red SU-76 assault gun", "side": "red", "kind": "tank", "type": "SU-76", "echelon": "I", "strength": 10.0, "speed_mps": 8.0, "armor": 0.7, "detection_range_m": 2200.0, "lanchester_range_m": 1700.0},
    {"label": "Red recon platoon", "side": "red", "kind": "recon", "type": "Recon", "echelon": "I", "strength": 6.0, "speed_mps": 13.0, "armor": 0.35, "detection_range_m": 6800.0, "command_range_m": 10000.0, "lanchester_range_m": 0.0},
    {"label": "Blue PzIII tank", "side": "blue", "kind": "tank", "type": "PzIII", "echelon": "I", "strength": 16.0, "speed_mps": 9.5, "armor": 1.0, "detection_range_m": 1850.0, "lanchester_range_m": 1800.0},
    {"label": "Blue PzIV tank", "side": "blue", "kind": "tank", "type": "PzIV", "echelon": "I", "strength": 14.0, "speed_mps": 9.5, "armor": 1.18, "detection_range_m": 1850.0, "lanchester_range_m": 1900.0},
    {"label": "Blue Tiger I heavy tank", "side": "blue", "kind": "tank", "type": "Tiger_I", "echelon": "I", "strength": 9.0, "speed_mps": 7.5, "armor": 1.9, "detection_range_m": 2200.0, "lanchester_range_m": 2300.0},
    {"label": "Red M-30 122mm artillery", "side": "red", "kind": "artillery", "type": "M-30", "echelon": "III", "strength": 6.0, "speed_mps": 4.0, "armor": 0.45, "detection_range_m": 1600.0, "command_range_m": 6500.0, "lanchester_range_m": 900.0, "shell_damage": 1.2, "shell_range_m": 9000.0, "shell_speed_mps": 420.0, "shell_dispersion_m": 140.0, "fire_rate_per_min": 2.0, "ammo_remaining": 24},
    {"label": "Blue Wespe SP artillery", "side": "blue", "kind": "artillery", "type": "Wespe", "echelon": "III", "strength": 5.0, "speed_mps": 5.5, "armor": 0.45, "detection_range_m": 1600.0, "command_range_m": 6500.0, "lanchester_range_m": 900.0, "shell_damage": 1.0, "shell_range_m": 8400.0, "shell_speed_mps": 390.0, "shell_dispersion_m": 150.0, "fire_rate_per_min": 2.2, "ammo_remaining": 22},
    {"label": "Blue Wespe SP artillery", "side": "blue", "kind": "artillery", "type": "Wespe", "echelon": "III", "strength": 5.0, "speed_mps": 5.5, "armor": 0.45, "detection_range_m": 1600.0, "command_range_m": 6500.0, "lanchester_range_m": 850.0, "shell_damage": 1.9, "shell_range_m": 10500.0, "shell_speed_mps": 470.0, "shell_dispersion_m": 145.0, "fire_rate_per_min": 2.5, "ammo_remaining": 20},
]

func _ready() -> void:
    set_process(true)
    mouse_filter = Control.MOUSE_FILTER_STOP
    set_process_input(true)
    _parse_args()
    _load_ui_font()
    if _screenshot_path == "" and _input_smoke_path == "" and OS.has_feature("release"):
        DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
    _load_actual_map_texture()
    BackendClient.state_received.connect(_on_state_received)
    BackendClient.events_received.connect(_on_events_received)
    BackendClient.parameters_received.connect(_on_parameters_received)
    BackendClient.matrix_received.connect(_on_matrix_received)
    BackendClient.replay_received.connect(_on_replay_received)
    BackendClient.terrain_received.connect(_on_terrain_received)
    BackendClient.engagements_received.connect(_on_engagements_received)
    BackendClient.config_dump_received.connect(_on_config_dump_received)
    BackendClient.state_dump_received.connect(_on_state_dump_received)
    BackendClient.backend_error.connect(_on_backend_error)
    _setup_3d_viewport()
    _load_fallback_payloads()
    BackendClient.connect_websocket()
    _request_backend_snapshot.call_deferred()
    _status = "Backend connection complete"
    # Floating text box to set the scan-grid cell size (meters) at runtime.
    _grid_size_input = LineEdit.new()
    _grid_size_input.add_theme_font_override("font", _default_font())
    _grid_size_input.placeholder_text = "m"
    _grid_size_input.tooltip_text = "Detection grid cell size (m), Enter to apply"
    _grid_size_input.alignment = HORIZONTAL_ALIGNMENT_CENTER
    _grid_size_input.add_theme_font_size_override("font_size", 12)
    _grid_size_input.text = "250"
    _grid_size_input.visible = false
    _grid_size_input.text_submitted.connect(_on_grid_size_submitted)
    add_child(_grid_size_input)

func _load_actual_map_texture() -> void:
    if ResourceLoader.exists(ACTUAL_MAP_PATH):
        _actual_map_texture = load(ACTUAL_MAP_PATH) as Texture2D
    if _actual_map_texture == null:
        var image := Image.new()
        var err := image.load(ProjectSettings.globalize_path(ACTUAL_MAP_PATH))
        if err == OK:
            _actual_map_texture = ImageTexture.create_from_image(image)

func _load_ui_font() -> void:
    if ResourceLoader.exists(KOREAN_FONT_PATH):
        var loaded := load(KOREAN_FONT_PATH)
        if loaded is Font:
            _ui_font = loaded

func _default_font() -> Font:
    if _ui_font != null:
        return _ui_font
    return get_theme_default_font()

func _parse_args() -> void:
    var args := OS.get_cmdline_args()
    args.append_array(OS.get_cmdline_user_args())
    for i in range(args.size()):
        if args[i] == "--screenshot-path" and i + 1 < args.size():
            _screenshot_path = args[i + 1]
            _pending_screenshot = true
        elif args[i] == "--input-smoke-path" and i + 1 < args.size():
            _input_smoke_path = args[i + 1]
        elif args[i] == "--view-mode" and i + 1 < args.size():
            _view_mode = args[i + 1].to_lower()
        elif args[i] == "--tool-mode" and i + 1 < args.size():
            _tool_mode = args[i + 1].to_lower()
        elif args[i] == "--dialog" and i + 1 < args.size():
            _active_dialog = args[i + 1].to_lower()
        elif args[i] == "--precompute-replay":
            _precompute_replay_on_start = true
        elif args[i] == "--map-zoom" and i + 1 < args.size():
            _map_zoom = clamp(float(args[i + 1]), 0.65, 4.0)
        elif args[i] == "--battle-view-expanded":
            _battle_view_expanded = true
        elif args[i] == "--backend-url" and i + 1 < args.size():
            BackendClient.http_base_url = args[i + 1]
        elif args[i] == "--ws-url" and i + 1 < args.size():
            BackendClient.websocket_url = args[i + 1]
    if _pending_screenshot:
        print("Screenshot capture requested: ", _screenshot_path)

func _process(delta: float) -> void:
    var now_ms := Time.get_ticks_msec()
    if not _backend_live:
        if now_ms - _backend_last_retry_ms >= 2000:
            _backend_last_retry_ms = now_ms
            _request_backend_snapshot()
    if _playing and bool(_state.get("summary", {}).get("ended", false)):
        _playing = false
        _status = "Battle ended"
    if _replay_playing:
        _advance_replay(delta)
    if _playing and not _replay_playing:
        _step_timer -= delta
        if _step_timer <= 0.0:
            _step_timer = LIVE_STEP_REAL_INTERVAL / float(_speeds[_speed_index])
            _status = "Running - +%s tick requested" % _format_duration_log(STEP_SECONDS)
            BackendClient.step(STEP_SECONDS, 1)
    # Redraw detected enemy pulses at a fixed cadence instead of every rendered frame.
    if _view_mode == "2d" and not (_state.get("detections", []) as Array).is_empty() and now_ms - _last_detection_redraw_ms >= 125:
        _last_detection_redraw_ms = now_ms
        queue_redraw()
    # Keep the grid-size text box aligned with its toolbar slot (2D view only).
    if _grid_size_input:
        var show_input: bool = (_view_mode == "2d" and _grid_input_rect.size.x > 0.0)
        _grid_size_input.visible = show_input
        if show_input:
            _grid_size_input.position = _grid_input_rect.position
            _grid_size_input.size = _grid_input_rect.size
    if _input_smoke_path != "":
        _run_input_smoke()
    if _pending_screenshot:
        if _screenshot_start_ms == 0:
            _screenshot_start_ms = Time.get_ticks_msec()
        _screenshot_frames += 1
        var waiting_for_replay_stats := (_active_dialog == "stats" or _active_dialog == "") and _precompute_replay_on_start and (_replay_calculating or _replay_frames.is_empty())
        var screenshot_ready := _state.has("units") and (_view_mode != "3d" or _terrain_mesh_ready) and not waiting_for_replay_stats and _screenshot_frames > 35
        var screenshot_timeout := Time.get_ticks_msec() - _screenshot_start_ms > 45000
        if screenshot_ready or screenshot_timeout:
            var texture := get_viewport().get_texture()
            if texture == null:
                if screenshot_timeout:
                    print("Screenshot failed: viewport texture unavailable")
                    get_tree().quit(2)
                return
            var image := texture.get_image()
            if image == null:
                if screenshot_timeout:
                    print("Screenshot failed: viewport image unavailable")
                    get_tree().quit(2)
                return
            var err := image.save_png(_screenshot_path)
            print("Screenshot saved: ", _screenshot_path, " err=", err)
            get_tree().quit()

func _request_backend_snapshot() -> void:
    BackendClient.request_state()
    BackendClient.request_events()
    BackendClient.request_parameters()
    BackendClient.request_lanchester_matrix()
    BackendClient.request_terrain()
    BackendClient.request_engagements()

func _load_fallback_payloads() -> void:
    var terrain_file := FileAccess.open("res://data/terrain_payload.json", FileAccess.READ)
    if terrain_file:
        var terrain_parsed = JSON.parse_string(terrain_file.get_as_text())
        if typeof(terrain_parsed) == TYPE_DICTIONARY:
            _terrain_payload = terrain_parsed
            _terrain_cells = _terrain_payload.get("cells", [])
    var state_file := FileAccess.open("res://data/initial_state.json", FileAccess.READ)
    if state_file:
        var state_parsed = JSON.parse_string(state_file.get_as_text())
        if typeof(state_parsed) == TYPE_DICTIONARY:
            _state = state_parsed
            if _selected_unit_id == "" and _state.has("units") and not _state.get("units", []).is_empty():
                _selected_unit_id = str(_state.get("units", [])[0].get("id", ""))
    var matrix_file := FileAccess.open("res://data/lanchester_matrix.json", FileAccess.READ)
    if matrix_file:
        var matrix_parsed = JSON.parse_string(matrix_file.get_as_text())
        if typeof(matrix_parsed) == TYPE_DICTIONARY:
            _on_matrix_received(matrix_parsed)

func _draw() -> void:
    _buttons.clear()
    _layout()
    draw_rect(Rect2(Vector2.ZERO, size), BG, true)
    _draw_map()
    _draw_header()
    if not _battle_view_expanded:
        _draw_oob()
        _draw_right_panels()
        _draw_bottom()
    _draw_dialogs()

func _layout() -> void:
    var header_h := 56.0
    var bottom_h := 170.0
    var margin := 10.0
    if _battle_view_expanded:
        _left_rect = Rect2()
        _right_rect = Rect2()
        _bottom_rect = Rect2()
        _map_rect = Rect2(margin, header_h + margin, size.x - margin * 2.0, size.y - header_h - margin * 2.0)
        return
    var left_w: float = clamp(size.x * 0.2, 270.0, 360.0)
    var right_w: float = clamp(size.x * 0.34, 420.0, 640.0)
    _left_rect = Rect2(margin, header_h + margin, left_w, size.y - header_h - bottom_h - margin * 2.0)
    _right_rect = Rect2(size.x - right_w - margin, header_h + margin, right_w, _left_rect.size.y)
    _map_rect = Rect2(_left_rect.end.x + margin, header_h + margin, _right_rect.position.x - _left_rect.end.x - margin * 2.0, _left_rect.size.y)
    _bottom_rect = Rect2(margin, size.y - bottom_h - margin, size.x - margin * 2.0, bottom_h)

func _draw_header() -> void:
    draw_rect(Rect2(0, 0, size.x, 56), Color(0.035, 0.040, 0.040), true)
    draw_line(Vector2(0, 56), Vector2(size.x, 56), LINE, 1.5)
    _draw_star(Vector2(28, 28), RED)
    var action_w := 508.0
    var cell_start: float = clamp(size.x * 0.26, 420.0, max(420.0, size.x - action_w - 650.0))
    var title_w: float = max(250.0, cell_start - 72.0)
    _text("Customizable Lanchester + DES wargame", Vector2(58, 50), 10, MUTED, title_w)
    var x: float = cell_start
    _header_cell(Rect2(x, 6, 154, 44), "Date", "1943-07-12   %s" % _clock_text())
    x += 162
    _header_cell(Rect2(x, 6, 112, 44), "Weather", "Clear 22C")
    x += 120
    _header_cell(Rect2(x, 6, 98, 44), "Visibility", "12 km")
    x += 106
    _header_cell(Rect2(x, 6, 178, 44), "시뮬레이션", _playback_rate_label())
    _button(Rect2(size.x - 508, 10, 62, 36), "초기화", "reset")
    _button(Rect2(size.x - 440, 10, 58, 36), "상태", "state")
    _button(Rect2(size.x - 376, 10, 78, 36), "파라미터", "dialog_params")
    _button(Rect2(size.x - 292, 10, 66, 36), "도움말", "dialog_help")
    _button(Rect2(size.x - 220, 10, 64, 36), "전장", "toggle_battle_view", _battle_view_expanded)
    _button(Rect2(size.x - 150, 10, 44, 36), "전체", "fullscreen")
    _button(Rect2(size.x - 106, 8, 48, 40), "2D", "view_2d", _view_mode == "2d")
    _button(Rect2(size.x - 54, 8, 48, 40), "3D", "view_3d", _view_mode == "3d")

func _header_cell(r: Rect2, label: String, value: String) -> void:
    _panel(r, Color(0.045, 0.050, 0.052), Color(0.13, 0.16, 0.16))
    _text(label, r.position + Vector2(10, 15), 10, MUTED)
    _text(value, r.position + Vector2(10, 34), 13, TEXT)



func _draw_oob() -> void:
    _panel(_left_rect, PANEL, LINE)
    _text("Order of battle", _left_rect.position + Vector2(12, 22), 15, TEXT, _left_rect.size.x - 24)
    _text("Select a unit from the order of battle.", _left_rect.position + Vector2(12, 42), 10, MUTED, _left_rect.size.x - 24)
    var tab_w := (_left_rect.size.x - 20.0) / 2.0
    _button(Rect2(_left_rect.position + Vector2(10, 58), Vector2(tab_w, 30)), "RED", "oob_red", _active_oob_side == "red")
    _button(Rect2(_left_rect.position + Vector2(10 + tab_w, 58), Vector2(tab_w, 30)), "BLUE", "oob_blue", _active_oob_side == "blue")

    var active_units := _units_by_side(_active_oob_side)
    var active_title := "RED 5 GTA" if _active_oob_side == "red" else "BLUE II SS-PzC"
    var active_color := RED if _active_oob_side == "red" else BLUE

    var validation_h := 88.0
    var content_x := _left_rect.position.x + 10.0
    var content_w := _left_rect.size.x - 20.0
    var header_y := _left_rect.position.y + 108.0
    var add_unit_h := 148.0
    var add_rect := Rect2(content_x, header_y + 66.0, content_w, add_unit_h)
    var validation_rect := Rect2(content_x, _left_rect.end.y - validation_h - 8.0, content_w, validation_h)
    var list_top := add_rect.end.y + 10.0
    var list_bottom := validation_rect.position.y - 10.0
    var list_rect := Rect2(content_x, list_top, content_w, max(86.0, list_bottom - list_top))

    _draw_side_header(Rect2(content_x, header_y, content_w, 58.0), active_title, active_units, active_color)
    _draw_add_unit_controls(add_rect)

    var row_step := 30.0
    var available_rows := int(max(3.0, floor((list_rect.size.y - 16.0) / row_step)))
    var max_start: int = max(0, active_units.size() - available_rows)
    _scroll_left_oob = clamp(_scroll_left_oob, 0.0, float(max_start))
    var start_index := int(round(_scroll_left_oob))

    _panel(list_rect, Color(0.015, 0.020, 0.021, 1.0), Color(0.14, 0.18, 0.18))
    _side_block(list_rect, active_units, active_color, available_rows, start_index)
    _oob_scroll_track = Rect2()
    _oob_scroll_knob = Rect2()
    _oob_scroll_max = float(max_start)
    if active_units.size() > available_rows:
        _oob_scroll_track = Rect2(list_rect.end.x - 11.0, list_rect.position.y + 8.0, 7.0, list_rect.size.y - 16.0)
        draw_rect(_oob_scroll_track, Color(0.14, 0.16, 0.15), true)
        var knob_h: float = max(22.0, _oob_scroll_track.size.y * float(available_rows) / float(active_units.size()))
        var knob_y: float = _oob_scroll_track.position.y + (_oob_scroll_track.size.y - knob_h) * (float(start_index) / max(float(max_start), 1.0))
        _oob_scroll_knob = Rect2(_oob_scroll_track.position.x - 2.0, knob_y, _oob_scroll_track.size.x + 4.0, knob_h)
        draw_rect(_oob_scroll_knob, active_color, true)

    _panel(validation_rect, Color(0.020, 0.030, 0.026, 1.0), Color(0.18, 0.24, 0.20))
    _text("Validation", validation_rect.position + Vector2(10, 20), 12, TEXT, validation_rect.size.x - 20)
    var summary: Dictionary = _state.get("summary", {})
    _text("Units %s / contacts %s / t=%0.0fs" % [str(summary.get("active_units", 0)), str(summary.get("active_contacts", 0)), float(_state.get("time_s", 0.0))], validation_rect.position + Vector2(10, 42), 10, MUTED, validation_rect.size.x - 20)
    _text("화면 %s / 도구 %s / %s" % [_view_mode.to_upper(), _tool_label(), _playback_rate_label()], validation_rect.position + Vector2(10, 62), 10, GOLD, validation_rect.size.x - 20)

func _draw_side_header(r: Rect2, title: String, units: Array, color: Color) -> void:
    _panel(r, Color(0.025, 0.032, 0.033, 1.0), Color(0.15, 0.19, 0.19))
    _draw_cross(r.position + Vector2(22, 24), color)
    _text(title, r.position + Vector2(48, 25), 14, TEXT, r.size.x - 60)
    _text("Tanks %d / recon %d / artillery %d / HQ %d / strength %.0f incl reserve %.0f" % [_count_kind(units, "tank"), _count_kind(units, "recon"), _count_kind(units, "artillery"), _count_kind(units, "command_post"), _sum_strength(units), _sum_pending_reserve_strength(units)], r.position + Vector2(48, 46), 9, MUTED, r.size.x - 60)


func _side_summary(r: Rect2, title: String, units: Array, color: Color) -> void:
    _panel(r, PANEL_DARK, LINE)
    _draw_cross(r.position + Vector2(12, 16), color)
    _text(title, r.position + Vector2(30, 18), 12, TEXT, r.size.x - 42)
    _text("%d tank  %d recon  %d artillery  %d HQ  |  N %.0f" % [_count_kind(units, "tank"), _count_kind(units, "recon"), _count_kind(units, "artillery"), _count_kind(units, "command_post"), _sum_strength(units)], r.position + Vector2(30, 39), 10, MUTED, r.size.x - 42)



func _side_block(r: Rect2, units: Array, color: Color, limit: int = 10, start_index: int = 0) -> float:
    var y := r.position.y + 22.0
    var end_index: int = min(units.size(), start_index + limit)
    for idx in range(start_index, end_index):
        var unit: Dictionary = units[idx]
        var uid := str(unit.get("id", ""))
        var row_rect := Rect2(r.position.x + 8.0, y - 15.0, r.size.x - 24.0, 27.0)
        _buttons.append({"rect": row_rect.grow(3.0), "action": "select_unit|" + uid})
        if uid == _selected_unit_id:
            draw_rect(row_rect, Color(color.r, color.g, color.b, 0.24), true)
            draw_rect(row_rect, color, false, 1.0)
        elif idx % 2 == 0:
            draw_rect(row_rect, Color(0.04, 0.048, 0.048, 0.55), true)
        var alpha := _unit_display_alpha(unit)
        var row_color := _with_alpha(color, alpha)
        _unit_glyph(row_rect.position + Vector2(22, 13), str(unit.get("kind", "tank")), row_color, 0.72, _unit_strength_ratio(unit), _unit_echelon(unit))
        var current := float(unit.get("strength", 0.0))
        var max_s: float = max(float(unit.get("max_strength", 1.0)), 0.01)
        var type_label := _type_short(str(unit.get("type", "")))
        var reserve_prefix := "[R] " if _unit_is_pending_reserve(unit) else ""
        var name_color := TEXT if uid == _selected_unit_id else Color(0.74, 0.77, 0.74, max(0.46, alpha))
        _text("%s%s  %s  %.0f/%.0f" % [reserve_prefix, str(unit.get("name", "unit")), type_label, current, max_s], row_rect.position + Vector2(44, 14), 10, name_color, row_rect.size.x - 52)
        var state_label := _unit_lifecycle_label(unit)
        _text("전투력 %0.0f%% · %s · 속도 %0.1fm/s" % [100.0 * current / max_s, state_label, float(unit.get("speed_mps", 0.0))], row_rect.position + Vector2(44, 26), 8, _unit_lifecycle_color(unit), row_rect.size.x - 52)
        y += 30.0
    if units.size() == 0:
        _text("편제 없음", r.position + Vector2(18, 32), 10, MUTED, r.size.x - 36)
        y += 24.0
    elif start_index + limit < units.size():
        _text("아래에 %d개 더 있음" % (units.size() - start_index - limit), r.position + Vector2(18, r.end.y - 10), 8, MUTED, r.size.x - 36)
    return y

func _unit_lifecycle_label(unit: Dictionary) -> String:
    var state := str(unit.get("lifecycle_state", "engaged"))
    var has_reserve_trigger := unit.has("reserve_trigger_loss_ratio") and unit.get("reserve_trigger_loss_ratio") != null
    if has_reserve_trigger and not bool(unit.get("reserve_triggered", false)):
        return "예비대 대기 %.0f%%" % (100.0 * float(unit.get("reserve_trigger_loss_ratio", 0.0)))
    match state:
        "absent":
            return "비활성"
        "present_hold":
            return "대기"
        "maneuvering":
            return "기동"
        "engaged":
            return "교전가능"
        "destroyed":
            return "소멸"
    return state

func _unit_lifecycle_color(unit: Dictionary) -> Color:
    var state := str(unit.get("lifecycle_state", "engaged"))
    var has_reserve_trigger := unit.has("reserve_trigger_loss_ratio") and unit.get("reserve_trigger_loss_ratio") != null
    if has_reserve_trigger and not bool(unit.get("reserve_triggered", false)):
        return Color(0.72, 0.68, 0.48)
    if state == "absent":
        return Color(0.50, 0.52, 0.50)
    if state == "present_hold":
        return GOLD
    if state == "maneuvering":
        return Color(0.55, 0.78, 1.0)
    return MUTED

func _unit_is_pending_reserve(unit: Dictionary) -> bool:
    return unit.has("reserve_trigger_loss_ratio") and unit.get("reserve_trigger_loss_ratio") != null and not bool(unit.get("reserve_triggered", false))

func _unit_display_alpha(unit: Dictionary) -> float:
    if _unit_is_pending_reserve(unit):
        return 0.36 if not bool(unit.get("present", false)) else 0.52
    if str(unit.get("lifecycle_state", "")) == "absent":
        return 0.32
    return 1.0

func _with_alpha(color: Color, alpha: float) -> Color:
    return Color(color.r, color.g, color.b, clamp(alpha, 0.0, 1.0))

func _draw_map() -> void:
    var toolbar := Rect2(_map_rect.position, Vector2(_map_rect.size.x, 34))
    _panel(toolbar, PANEL, LINE)
    _text("지도 도구", toolbar.position + Vector2(12, 22), 12, TEXT)
    var tx := toolbar.position.x + 90
    var tools := [
        ["선택", "tool_select", "select"],
        ["이동", "tool_move", "move"],
        ["공격", "tool_fire", "fire"],
    ]
    for tool in tools:
        _button(Rect2(tx, toolbar.position.y + 5, 52, 24), str(tool[0]), str(tool[1]), _tool_mode == str(tool[2]))
        tx += 58
    _button(Rect2(tx, toolbar.position.y + 5, 72, 24), "탐지범위", "toggle_detection_ranges", _show_detection_ranges)
    tx += 78
    _text("Zoom", Vector2(tx, toolbar.position.y + 22), 10, MUTED, 44)
    tx += 40
    _grid_input_rect = Rect2(tx, toolbar.position.y + 5, 56, 24)
    tx += 62
    var zoom_label := " · 2D 배율 %d%%" % int(round(_map_zoom * 100.0)) if _view_mode == "2d" else ""
    var status_x: float = min(tx + 8.0, toolbar.end.x - 380.0)
    _text("%s / %s%s   단축키: S 선택, M 이동, F 공격, 1/2 뷰" % [_view_label(), _tool_label(), zoom_label], Vector2(status_x, toolbar.position.y + 23), 10, GOLD, max(180.0, toolbar.end.x - status_x - 12.0))
    _map_rect = Rect2(_map_rect.position.x, _map_rect.position.y + 40, _map_rect.size.x, _map_rect.size.y - 40)
    if _view_mode == "3d":
        _set_3d_update_enabled(true)
        if _map_dragging:
            _map_dragging = false
        _sync_3d_viewport(_map_rect)
        _draw_battlefield_3d(_map_rect)
        _draw_camera_controls(_map_rect)
    else:
        _set_3d_update_enabled(false)
        if _viewport_container_3d:
            _viewport_container_3d.visible = false
        _draw_map_background(_map_rect)
        _draw_map_overlays(_map_rect)
        _draw_units()
        _legend(Rect2(_map_rect.position.x + 12, _map_rect.position.y + 14, 136, 154))
        _scale_bar(_map_rect)
        _draw_2d_zoom_controls(_map_rect)

func _draw_map_background(r: Rect2) -> void:
    draw_rect(r, MAP_TAN, true)
    _draw_actual_map_layer(r)
    if _actual_map_texture == null:
        _draw_elevation_layer(r)
    for i in range(9):
        var y := r.position.y + float(i) * r.size.y / 8.0
        draw_line(Vector2(r.position.x, y), Vector2(r.end.x, y), Color(0.70, 0.66, 0.48, 0.13), 1)
    for i in range(12):
        var x2 := r.position.x + float(i) * r.size.x / 11.0
        draw_line(Vector2(x2, r.position.y), Vector2(x2, r.end.y), Color(0.16, 0.18, 0.15, 0.14), 1)
    _draw_elevation_peak_labels(r)
    draw_rect(r, Color(0.0, 0.0, 0.0, 0.16), false, 2.0)

func _draw_actual_map_layer(r: Rect2) -> void:
    if _actual_map_texture == null:
        return
    var units: Array = _state.get("units", [])
    var full_bounds: Array = _terrain_payload.get("bounds", _state.get("terrain", {}).get("bounds", _bounds_from_units(units)))
    var view_bounds := _map_view_bounds(full_bounds)
    var full_min_x := float(full_bounds[0])
    var full_min_y := float(full_bounds[1])
    var full_max_x := float(full_bounds[2])
    var full_max_y := float(full_bounds[3])
    var full_w: float = max(full_max_x - full_min_x, 1.0)
    var full_h: float = max(full_max_y - full_min_y, 1.0)
    var tex_size := _actual_map_texture.get_size()
    var src_x: float = clamp((float(view_bounds[0]) - full_min_x) / full_w, 0.0, 1.0) * tex_size.x
    var src_w: float = clamp((float(view_bounds[2]) - float(view_bounds[0])) / full_w, 0.001, 1.0) * tex_size.x
    var src_y: float = clamp((full_max_y - float(view_bounds[3])) / full_h, 0.0, 1.0) * tex_size.y
    var src_h: float = clamp((float(view_bounds[3]) - float(view_bounds[1])) / full_h, 0.001, 1.0) * tex_size.y
    draw_texture_rect_region(_actual_map_texture, r, Rect2(src_x, src_y, src_w, src_h), Color(1.0, 1.0, 1.0, 0.86))
    draw_rect(r, Color(0.06, 0.08, 0.06, 0.10), true)

func _draw_elevation_layer(r: Rect2) -> void:
    if _terrain_cells.is_empty():
        return
    var units: Array = _state.get("units", [])
    var bounds: Array = _terrain_payload.get("bounds", _state.get("terrain", {}).get("bounds", _bounds_from_units(units)))
    var cols: int = max(1, int(_terrain_payload.get("cols", 48)))
    var rows: int = max(1, int(_terrain_payload.get("rows", 32)))
    var cell_w: float = max(2.0, ((_map_rect.size.x - 52.0) / float(cols) + 1.0) * _map_zoom)
    var cell_h: float = max(2.0, ((_map_rect.size.y - 52.0) / float(rows) + 1.0) * _map_zoom)
    for cell in _terrain_cells:
        var p := _world_to_screen(Vector2(float(cell.get("x", 0.0)), float(cell.get("y", 0.0))), bounds)
        var c := _elevation_color_2d(cell)
        if _actual_map_texture != null:
            c.a = 0.22 if not bool(cell.get("water", false)) else 0.34
        draw_rect(Rect2(p - Vector2(cell_w * 0.5, cell_h * 0.5), Vector2(cell_w, cell_h)), c, true)
    var min_e := float(_terrain_payload.get("min_elevation_m", 0.0))
    var max_e := float(_terrain_payload.get("max_elevation_m", min_e))
    _text("%0.0fm" % min_e, r.position + Vector2(18, r.end.y - 36), 9, Color(0.67, 0.88, 0.58))
    _text("%0.0fm" % max_e, r.position + Vector2(72, r.end.y - 36), 9, Color(0.98, 0.79, 0.39))

func _elevation_color_2d(cell: Dictionary) -> Color:
    if bool(cell.get("water", false)):
        return Color(0.05, 0.22, 0.40, 1.0)
    var elev_min := float(_terrain_payload.get("min_elevation_m", 0.0))
    var elev_max := float(_terrain_payload.get("max_elevation_m", elev_min + 1.0))
    var t: float = pow(clamp((float(cell.get("elevation_m", elev_min)) - elev_min) / max(elev_max - elev_min, 0.1), 0.0, 1.0), 1.15)
    var base := Color(0.13 + t * 0.62, 0.30 + t * 0.34, 0.12 + t * 0.04, 1.0)
    if bool(cell.get("road", false)):
        base = base.lerp(Color(0.82, 0.70, 0.42, 1.0), 0.45)
    elif bool(cell.get("rail", false)):
        base = base.lerp(Color(0.07, 0.07, 0.06, 1.0), 0.38)
    return base

func _draw_elevation_peak_labels(r: Rect2) -> void:
    if _terrain_cells.is_empty():
        return
    var units: Array = _state.get("units", [])
    var bounds: Array = _terrain_payload.get("bounds", _state.get("terrain", {}).get("bounds", _bounds_from_units(units)))
    var peaks := []
    for cell in _terrain_cells:
        if bool(cell.get("water", false)):
            continue
        peaks.append(cell)
    peaks.sort_custom(func(a, b): return float(a.get("elevation_m", 0.0)) > float(b.get("elevation_m", 0.0)))
    var shown := 0
    for cell in peaks:
        if shown >= 3:
            break
        var p := _world_to_screen(Vector2(float(cell.get("x", 0.0)), float(cell.get("y", 0.0))), bounds)
        if not r.grow(-20.0).has_point(p):
            continue
        draw_circle(p, 4.5, GOLD)
        draw_arc(p, 11.0, 0, TAU, 28, Color(GOLD.r, GOLD.g, GOLD.b, 0.85), 1.3)
        _text("고도 %0.0fm" % float(cell.get("elevation_m", 0.0)), p + Vector2(8, -8), 10, Color(1.0, 0.88, 0.42), 90)
        shown += 1



func _draw_map_overlays(r: Rect2) -> void:
    # Detection scan-range grid (toggleable). Replaces the old dashed circle.
    if _show_detection_ranges and _state.has("units"):
        _draw_detection_grid(_state.get("units", []), r)
    # Cells where an enemy was detected this step pulse in pastel red (always on).
    _draw_detected_cells(r)


func _draw_recon_coverage(units: Array, _r: Rect2) -> void:
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
    for unit in units:
        var kind := str(unit.get("kind", ""))
        var range_m := float(unit.get("detection_range_m", 0.0))
        if range_m <= 0.0:
            continue
        if kind != "command_post" and kind != "artillery" and kind != "recon" and str(unit.get("id", "")) != _selected_unit_id:
            continue
        var center := _world_to_screen(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), bounds)
        var edge := _world_to_screen(Vector2(float(unit.get("x", 0.0)) + range_m, float(unit.get("y", 0.0))), bounds)
        var radius: float = clamp(center.distance_to(edge), 10.0, max(_map_rect.size.x, _map_rect.size.y))
        var coverage_rect := Rect2(center - Vector2(radius, radius), Vector2(radius * 2.0, radius * 2.0))
        if not coverage_rect.intersects(_map_rect):
            continue
        var side_color := RED if str(unit.get("side", "")) == "red" else BLUE
        var c := Color(side_color.r, side_color.g, side_color.b, 0.36 if str(unit.get("id", "")) == _selected_unit_id else 0.18)
        _draw_dashed_circle(center, radius, c, 1.4)
    _text("지휘/정찰 탐지 범위", _map_rect.position + Vector2(18, _map_rect.size.y - 22), 10, MUTED, _map_rect.size.x - 36)

func _draw_dashed_circle(center: Vector2, radius: float, color: Color, width: float = 1.0) -> void:
    var segments := 48
    for i in range(segments):
        if i % 2 == 1:
            continue
        var a0 := TAU * float(i) / float(segments)
        var a1 := TAU * float(i + 1) / float(segments)
        draw_arc(center, radius, a0, a1, 5, color, width, true)

func _scan_cell_screen_size(center_world: Vector2, gs: float, bounds: Array) -> Vector2:
    # Project a gs x gs world box to screen to get the on-screen cell size (zoom-aware).
    var a := _world_to_screen(center_world, bounds)
    var b := _world_to_screen(center_world + Vector2(gs, gs), bounds)
    return Vector2(max(abs(b.x - a.x), 1.0), max(abs(b.y - a.y), 1.0))

func _effective_grid_size() -> float:
    # Runtime text-box override wins; otherwise use the backend's grid cell size.
    if _grid_cell_size_override > 0.0:
        return _grid_cell_size_override
    return float(_state.get("detection_grid_cell_size_m", 250.0))

func _on_grid_size_submitted(text: String) -> void:
    var v := text.strip_edges().to_float()
    if v >= 10.0:
        _grid_cell_size_override = v
        _status = "탐지 격자 크기: %dm" % int(round(v))
    else:
        _status = "Grid size uses meters; minimum 10m"
    if _grid_size_input:
        _grid_size_input.release_focus()
    queue_redraw()

func _draw_detection_grid(units: Array, _r: Rect2) -> void:
    # Tanks and recon scan on the same grid used by the backend detector.
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
    var gs := _effective_grid_size()
    if gs <= 0.0:
        return
    for unit in units:
        var kind := str(unit.get("kind", ""))
        if kind != "tank" and kind != "recon":
            continue
        var rng := float(unit.get("detection_range_m", 0.0))
        if rng <= 0.0:
            continue
        var ux := float(unit.get("x", 0.0))
        var uy := float(unit.get("y", 0.0))
        var is_red := str(unit.get("side", "")) == "red"
        var base: Color = Color(0.62, 0.62, 0.62) if is_red else Color(0.05, 0.05, 0.05)
        if kind == "recon":
            base = Color(0.65, 0.95, 0.68) if is_red else Color(0.45, 0.78, 1.0)
        var fill_alpha := 0.09 if kind == "recon" else 0.16
        var border_alpha := 0.58 if kind == "recon" else 0.40
        var fill := Color(base.r, base.g, base.b, fill_alpha)
        var border := Color(base.r, base.g, base.b, border_alpha)
        var n := int(ceil(rng / gs))
        var ci := int(floor(ux / gs))
        var cj := int(floor(uy / gs))
        var sz := _scan_cell_screen_size(Vector2((ci + 0.5) * gs, (cj + 0.5) * gs), gs, bounds)
        for di in range(-n, n + 1):
            for dj in range(-n, n + 1):
                var cx := (float(ci + di) + 0.5) * gs
                var cy := (float(cj + dj) + 0.5) * gs
                var p := _world_to_screen(Vector2(cx, cy), bounds)
                if not _map_rect.has_point(p):
                    continue
                var cell := Rect2(p - sz * 0.5, sz)
                draw_rect(cell, fill, true)
                draw_rect(cell, border, false, 1.0)
    _text("탐지 격자(전차 + 정찰 감지범위)", _map_rect.position + Vector2(18, _map_rect.size.y - 22), 10, MUTED, _map_rect.size.x - 36)

func _draw_detected_cells(_r: Rect2) -> void:
    # Cells holding a currently-detected enemy pulse in pastel red (detection -> combat).
    var dets: Array = _state.get("detections", [])
    if dets.is_empty():
        return
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(_state.get("units", [])))
    var gs := _effective_grid_size()
    if gs <= 0.0:
        return
    var t := float(Time.get_ticks_msec()) / 1000.0
    var pulse := 0.5 + 0.5 * sin(t * TAU * 1.5)        # ~1.5 Hz blink
    var a := 0.20 + 0.45 * pulse
    var col := Color(1.0, 0.55, 0.55, a)               # pastel red
    var edge := Color(1.0, 0.45, 0.45, min(1.0, a + 0.25))
    # Blink for cells spotted by combat scanners (tank/recon); artillery consumes recon reports downstream.
    var kind_by_id := {}
    for u in _state.get("units", []):
        kind_by_id[str(u.get("id", ""))] = str(u.get("kind", ""))
    var drawn := {}
    for det in dets:
        var detector_kind := str(kind_by_id.get(str(det.get("detector_id", "")), ""))
        if detector_kind != "tank" and detector_kind != "recon":
            continue
        var tx := float(det.get("x", 0.0))
        var ty := float(det.get("y", 0.0))
        var ci := int(floor(tx / gs))
        var cj := int(floor(ty / gs))
        var key := "%d_%d" % [ci, cj]
        if drawn.has(key):
            continue
        drawn[key] = true
        var center := Vector2((float(ci) + 0.5) * gs, (float(cj) + 0.5) * gs)
        var p := _world_to_screen(center, bounds)
        if not _map_rect.has_point(p):
            continue
        var sz := _scan_cell_screen_size(center, gs, bounds)
        var cell := Rect2(p - sz * 0.5, sz)
        draw_rect(cell, col, true)
        draw_rect(cell, edge, false, 1.5)

func _draw_units() -> void:
    if not _state.has("units"):
        _text("Python backend 시작 후 상태를 수신합니다...", _map_rect.position + Vector2(24, 34), 16, GOLD)
        return
    var units: Array = _state.get("units", [])
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
    _draw_contact_lines(units, bounds)
    _draw_fire_mission_lines(units, bounds)
    _draw_shell_lines(units, bounds)
    for unit in units:
        var pos := _world_to_screen(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), bounds)
        var base_color := RED if str(unit.get("side", "")) == "red" else BLUE
        var alpha := _unit_display_alpha(unit)
        var color := _with_alpha(base_color, alpha)
        var selected := str(unit.get("id", "")) == _selected_unit_id
        var wp_index := 1
        for wp in unit.get("waypoints", []):
            if typeof(wp) == TYPE_ARRAY and wp.size() >= 2:
                var p := _world_to_screen(Vector2(float(wp[0]), float(wp[1])), bounds)
                var route_alpha: float = 0.42 if selected else 0.28 * alpha
                _map_draw_line(pos, p, GOLD if selected else Color(base_color.r, base_color.g, base_color.b, route_alpha), 2.4 if selected else 1.1)
                var waypoint_safe_rect := _map_rect.grow(-8.0 if selected else -5.0)
                if waypoint_safe_rect.has_point(p):
                    draw_circle(p, 6.0 if selected else 3.0, GOLD if selected else Color(base_color.r, base_color.g, base_color.b, 0.60 * alpha))
                if selected and _map_rect.grow(-14.0).has_point(p):
                    _text(str(wp_index), p + Vector2(7, -6), 9, TEXT)
                pos = p
                wp_index += 1
        var unit_pos := _world_to_screen(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), bounds)
        var unit_margin := 40.0 if selected else 26.0
        if _map_rect.grow(-unit_margin).has_point(unit_pos):
            _unit_symbol(unit_pos, unit, color, selected)

func _draw_contact_lines(units: Array, bounds: Array) -> void:
    var by_id := {}
    for u in units:
        by_id[str(u.get("id", ""))] = u
    for eg in _engagements:
        var a: Dictionary = eg.get("attacker", {})
        var b: Dictionary = eg.get("defender", {})
        var aid := str(a.get("id", ""))
        var bid := str(b.get("id", ""))
        if not by_id.has(aid) or not by_id.has(bid):
            continue
        var au: Dictionary = by_id[aid]
        var bu: Dictionary = by_id[bid]
        var p1 := _world_to_screen(Vector2(float(au.get("x", 0.0)), float(au.get("y", 0.0))), bounds)
        var p2 := _world_to_screen(Vector2(float(bu.get("x", 0.0)), float(bu.get("y", 0.0))), bounds)
        var selected := aid == _selected_unit_id or bid == _selected_unit_id
        var line_color := Color(1.0, 0.64, 0.10, 0.95) if selected else Color(1.0, 0.50, 0.08, 0.48)
        var clipped := _map_draw_line(p1, p2, line_color, 3.2 if selected else 1.6)
        if clipped.size() != 2:
            continue
        var mid: Vector2 = (clipped[0] + clipped[1]) * 0.5
        if _map_rect.grow(-6.0).has_point(mid):
            draw_circle(mid, 5.0 if selected else 3.0, line_color)
        if selected and _map_rect.grow(-18.0).has_point(mid):
            _text("교전", mid + Vector2(8, -6), 10, GOLD)

func _draw_fire_mission_lines(units: Array, bounds: Array) -> void:
    var by_id := {}
    for u in units:
        by_id[str(u.get("id", ""))] = u
    for mission in _state.get("fire_missions", []):
        var artillery: Dictionary = by_id.get(str(mission.get("artillery_id", "")), {})
        if artillery.is_empty():
            continue
        var target_point := Vector2.ZERO
        var target_data = mission.get("target", null)
        if typeof(target_data) == TYPE_ARRAY and target_data.size() >= 2:
            target_point = Vector2(float(target_data[0]), float(target_data[1]))
        elif by_id.has(str(mission.get("target_id", ""))):
            var target: Dictionary = by_id[str(mission.get("target_id", ""))]
            target_point = Vector2(float(target.get("x", 0.0)), float(target.get("y", 0.0)))
        else:
            continue
        var p_art := _world_to_screen(Vector2(float(artillery.get("x", 0.0)), float(artillery.get("y", 0.0))), bounds)
        var p_target := _world_to_screen(target_point, bounds)
        _map_draw_line(p_art, p_target, Color(1.0, 0.86, 0.18, 0.34), 1.6)
        if _map_rect.grow(-9.0).has_point(p_target):
            draw_circle(p_target, 8.0, Color(1.0, 0.86, 0.18, 0.20))
        var detector: Dictionary = by_id.get(str(mission.get("detector_id", "")), {})
        var hq: Dictionary = by_id.get(str(mission.get("hq_id", "")), {})
        if not detector.is_empty():
            var p_det := _world_to_screen(Vector2(float(detector.get("x", 0.0)), float(detector.get("y", 0.0))), bounds)
            if not hq.is_empty():
                var p_hq := _world_to_screen(Vector2(float(hq.get("x", 0.0)), float(hq.get("y", 0.0))), bounds)
                _map_draw_line(p_det, p_hq, Color(0.45, 0.92, 1.0, 0.30), 1.2)
                _map_draw_line(p_hq, p_art, Color(0.45, 0.92, 1.0, 0.25), 1.2)
            else:
                _map_draw_line(p_det, p_art, Color(0.45, 0.92, 1.0, 0.25), 1.2)

func _draw_shell_lines(units: Array, bounds: Array) -> void:
    # Replay frames carry en-route shells directly in state. Draw those
    # separately from direct engagements so artillery damage is visible even
    # when no Lanchester contact exists.
    var shell_items: Array = _state.get("shells", [])
    if shell_items.is_empty():
        return
    var by_id := {}
    for u in units:
        by_id[str(u.get("id", ""))] = u
    var start_index: int = max(0, shell_items.size() - 24)
    for shell in shell_items.slice(start_index, shell_items.size()):
        var start_data: Array = shell.get("start", [])
        var target_data: Array = shell.get("target", [])
        if start_data.size() < 2 or target_data.size() < 2:
            continue
        var start_world := Vector2(float(start_data[0]), float(start_data[1]))
        var target_world := Vector2(float(target_data[0]), float(target_data[1]))
        var p_start := _world_to_screen(start_world, bounds)
        var p_target := _world_to_screen(target_world, bounds)
        var remaining: float = _shell_remaining_s(shell)
        var progress: float = _shell_progress(shell)
        var collapsed := _shell_is_visual_instant(shell)
        var arc_height: float = clamp(p_start.distance_to(p_target) * 0.20, 28.0, 120.0)
        var arc_points := _shell_arc_points_2d(p_start, p_target, arc_height)
        var p_shell: Vector2 = _point_on_polyline(arc_points, progress)
        var col := Color(1.0, 0.78, 0.18, 0.86)
        if not collapsed:
            _draw_shell_arc_segments_2d(arc_points, Color(0.05, 0.035, 0.0, 0.58), 5.2, 1.0)
            _draw_shell_arc_segments_2d(arc_points, Color(col.r, col.g, col.b, 0.28), 3.4, 1.0)
            _draw_shell_arc_segments_2d(arc_points, Color(1.0, 0.94, 0.46, 0.96), 2.4, progress)
        if _map_rect.grow(-10.0).has_point(p_start):
            var flash_alpha: float = 0.30 + 0.35 * (1.0 - min(progress, 0.45))
            draw_circle(p_start, 8.0, Color(1.0, 0.68, 0.12, flash_alpha))
            draw_arc(p_start, 14.0, 0.0, TAU, 24, Color(1.0, 0.84, 0.28, min(0.88, flash_alpha + 0.15)), 2.0)
        if not collapsed and _map_rect.grow(-8.0).has_point(p_shell):
            draw_circle(p_shell, 8.0, Color(1.0, 0.58, 0.08, 0.26))
            draw_circle(p_shell, 4.8, col)
            draw_circle(p_shell, 2.2, Color(1.0, 1.0, 0.82, 0.98))
        if _map_rect.grow(-12.0).has_point(p_target):
            var radius_edge := _world_to_screen(target_world + Vector2(float(shell.get("radius_m", 120.0)), 0.0), bounds)
            var radius_px: float = clamp(p_target.distance_to(radius_edge), 7.0, 34.0)
            var flash := 0.28 if collapsed else 0.08
            draw_circle(p_target, radius_px, Color(1.0, 0.46, 0.10, flash))
            draw_arc(p_target, radius_px, 0.0, TAU, 40, Color(1.0, 0.78, 0.18, 0.72 if collapsed else 0.58), 2.0)
            draw_arc(p_target, max(4.0, radius_px * 0.45), 0.0, TAU, 32, Color(1.0, 0.34, 0.08, 0.56 if collapsed else 0.40), 1.5)
        if not collapsed and _map_rect.grow(-24.0).has_point(p_shell):
            _text("포탄 %0.0fs" % remaining, p_shell + Vector2(9, -9), 9, Color(1.0, 0.92, 0.38, 0.96), 78)

func _shell_remaining_s(shell: Dictionary) -> float:
    return max(float(shell.get("remaining", 0.0)), 0.0)

func _shell_progress(shell: Dictionary) -> float:
    var remaining: float = _shell_remaining_s(shell)
    var current_time: float = float(_state.get("time_s", 0.0))
    var impact_time: float = float(shell.get("impact_time", current_time + remaining))
    var launch_time: float = float(shell.get("launch_time", current_time - max(impact_time - current_time - remaining, 0.0)))
    var duration: float = max(impact_time - launch_time, 1.0)
    if _shell_is_visual_instant(shell):
        return 1.0
    return clamp((current_time - launch_time) / duration, 0.0, 1.0)

func _shell_duration_s(shell: Dictionary) -> float:
    var current_time: float = float(_state.get("time_s", 0.0))
    var remaining: float = _shell_remaining_s(shell)
    var impact_time: float = float(shell.get("impact_time", current_time + remaining))
    var launch_time: float = float(shell.get("launch_time", current_time - max(impact_time - current_time - remaining, 0.0)))
    return max(impact_time - launch_time, 0.0)

func _shell_is_visual_instant(shell: Dictionary) -> bool:
    var replay_interval_s: float = float(_last_replay_meta.get("frame_interval_s", REPLAY_SCENARIO_FRAME_INTERVAL_S))
    var duration: float = _shell_duration_s(shell)
    return _in_replay_view() and (bool(shell.get("landed", false)) or duration <= replay_interval_s + 1e-3)

func _shell_arc_points_2d(p_start: Vector2, p_target: Vector2, height_px: float) -> Array:
    var points := []
    var control := (p_start + p_target) * 0.5 + Vector2(0.0, -height_px)
    var steps := 18
    for i in range(steps + 1):
        var t := float(i) / float(steps)
        var a := p_start.lerp(control, t)
        var b := control.lerp(p_target, t)
        points.append(a.lerp(b, t))
    return points

func _point_on_polyline(points: Array, ratio: float) -> Vector2:
    if points.is_empty():
        return Vector2.ZERO
    if points.size() == 1:
        return points[0]
    var t: float = clamp(ratio, 0.0, 1.0) * float(points.size() - 1)
    var i: int = clamp(int(floor(t)), 0, points.size() - 2)
    var a: Vector2 = points[i]
    var b: Vector2 = points[i + 1]
    return a.lerp(b, t - float(i))

func _draw_shell_arc_segments_2d(points: Array, color: Color, width: float, until_ratio: float = 1.0) -> void:
    if points.size() < 2:
        return
    var until_t: float = clamp(until_ratio, 0.0, 1.0)
    for i in range(points.size() - 1):
        var seg_t0 := float(i) / float(points.size() - 1)
        var seg_t1 := float(i + 1) / float(points.size() - 1)
        if seg_t0 >= until_t:
            break
        var a: Vector2 = points[i]
        var b: Vector2 = points[i + 1]
        if seg_t1 > until_t:
            var local_t: float = clamp((until_t - seg_t0) / max(seg_t1 - seg_t0, 0.0001), 0.0, 1.0)
            b = a.lerp(b, local_t)
        _map_draw_line(a, b, color, width)

func _unit_symbol(pos: Vector2, unit: Dictionary, color: Color, selected: bool) -> void:
    var kind := str(unit.get("kind", "tank"))
    var w := 46.0 if kind != "command_post" else 38.0
    var h := 30.0 if kind != "command_post" else 32.0
    var r := Rect2(pos - Vector2(w / 2.0, h / 2.0), Vector2(w, h))
    var alpha: float = _unit_display_alpha(unit)
    if selected:
        draw_circle(pos, 34.0, Color(GOLD.r, GOLD.g, GOLD.b, 0.23))
        draw_arc(pos, 34.0, 0, TAU, 64, GOLD, 2.0)
    _draw_app6_icon(r, kind, color, _unit_strength_ratio(unit), selected, _unit_echelon(unit))
    var label_pos := r.position + Vector2(w + 4, 7)
    var label_width: float = _map_rect.end.x - label_pos.x - 4.0
    if label_width >= 42.0 and _map_rect.grow(-8.0).has_point(label_pos):
        var elevation_m := float(unit.get("elevation_m", 0.0))
        if not unit.has("elevation_m"):
            elevation_m = _terrain_height_at(float(unit.get("x", 0.0)), float(unit.get("y", 0.0)))
        var name_prefix := "RES " if _unit_is_pending_reserve(unit) else ""
        _text(name_prefix + str(unit.get("name", "unit")), label_pos, 9, Color(TEXT.r, TEXT.g, TEXT.b, max(0.52, alpha)), label_width)
        _text("elev %.0fm%s" % [elevation_m, " / reserve pending" if _unit_is_pending_reserve(unit) else ""], r.position + Vector2(w + 4, 20), 8, Color(MUTED.r, MUTED.g, MUTED.b, max(0.44, alpha)), label_width)

func _draw_right_panels() -> void:
    var gap := 8.0
    var selected_h: float = clamp(_right_rect.size.y * (0.42 if _orders_locked() else 0.46), 330.0, 440.0)
    var engagement_h: float = max(190.0, _right_rect.size.y - selected_h - gap)
    var selected := Rect2(_right_rect.position, Vector2(_right_rect.size.x, selected_h))
    var engagement := Rect2(selected.position + Vector2(0, selected.size.y + gap), Vector2(_right_rect.size.x, engagement_h))
    _selected_panel(selected)
    _engagement_panel(engagement)

func _preview(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("3D 전장 미리보기", r.position + Vector2(12, 20), 13, TEXT)
    var inner := Rect2(r.position + Vector2(8, 30), r.size - Vector2(16, 38))
    draw_rect(inner, Color(0.18, 0.22, 0.20), true)
    draw_rect(Rect2(inner.position, Vector2(inner.size.x, inner.size.y * 0.45)), Color(0.25, 0.31, 0.34), true)
    for i in range(7):
        draw_line(Vector2(inner.position.x, inner.position.y + inner.size.y * 0.48 + i * 5), Vector2(inner.end.x, inner.position.y + inner.size.y * 0.47 + i * 2), Color(0.44, 0.39, 0.22, 0.42), 1)
    for i in range(4):
        var p := inner.position + Vector2(70 + i * 95, 82 - i * 5)
        draw_rect(Rect2(p, Vector2(40, 12)), BLUE if i < 2 else RED, true)
        draw_line(p + Vector2(20, 6), p + Vector2(55, -6), Color(0.05, 0.05, 0.04), 2)
    draw_arc(inner.position + Vector2(inner.size.x * 0.50, inner.size.y * 0.65), 92, 0, TAU, 80, Color(GOLD.r, GOLD.g, GOLD.b, 0.34), 1.0)
    _button(Rect2(r.end.x - 92, r.end.y - 38, 78, 26), "3D 보기", "view_3d", _view_mode == "3d")


func _selected_panel(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("선택 부대 / 명령", r.position + Vector2(12, 20), 13, TEXT)
    var unit := _selected_unit()
    if unit.is_empty():
        _text("지도 또는 좌측 편제에서 부대를 선택하세요.", r.position + Vector2(16, 54), 12, MUTED, r.size.x - 32)
        _text("부대 아이콘을 클릭하거나 편제 목록에서 선택할 수 있습니다.", r.position + Vector2(16, 82), 11, GOLD, r.size.x - 32)
        return
    var color := RED if str(unit.get("side", "")) == "red" else BLUE
    _unit_glyph(r.position + Vector2(28, 55), str(unit.get("kind", "tank")), color, 1.15, _unit_strength_ratio(unit))
    _text(str(unit.get("name", "unit")), r.position + Vector2(58, 54), 17, TEXT, r.size.x - 72)
    _text("%s / %s / %s" % [str(unit.get("side", "")), str(unit.get("kind", "")), str(unit.get("type", ""))], r.position + Vector2(58, 76), 11, MUTED, r.size.x - 72)
    _text("상태: %s" % _unit_action_text(unit), r.position + Vector2(18, 100), 11, GOLD, r.size.x - 36)
    _text("Pos %.0f, %.0f  |  elev %.0fm  |  waypoints %d" % [float(unit.get("x", 0.0)), float(unit.get("y", 0.0)), float(unit.get("elevation_m", _terrain_height_at(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))))), Array(unit.get("waypoints", [])).size()], r.position + Vector2(18, 120), 10, MUTED, r.size.x - 36)
    _text("Detect %.0fm  Cmd %.0fm  Combat %.0fm  Armor %.2f" % [float(unit.get("detection_range_m", 0.0)), float(unit.get("command_range_m", 0.0)), float(unit.get("lanchester_range_m", 0.0)), float(unit.get("armor", 1.0))], r.position + Vector2(18, 140), 10, MUTED, r.size.x - 36)
    var strength_ratio := _unit_strength_ratio(unit)
    _text("전투력 %.0f/%.0f (%0.0f%%) · 아이콘 물빠짐" % [float(unit.get("strength", 0.0)), float(unit.get("max_strength", 1.0)), strength_ratio * 100.0], r.position + Vector2(18, 174), 10, TEXT, r.size.x - 36)
    _stat_bar(Vector2(r.position.x + 18, r.position.y + 190), r.size.x - 36, "사기", float(unit.get("morale", 1.0)) * 100.0, 120.0, GREEN)
    _stat_bar(Vector2(r.position.x + 18, r.position.y + 214), r.size.x - 36, "속도", float(unit.get("speed_mps", 0.0)) * 3.6, 60.0, Color(0.28, 0.72, 0.86))
    var eg := _engagement_for_unit(str(unit.get("id", "")))
    if not eg.is_empty():
        var deltas: Dictionary = eg.get("last_deltas", {})
        var k: Dictionary = eg.get("last_k", {})
        _text("Lanchester: k %.5f/%.5f, loss %.2f / %.2f" % [float(k.get("attacker_to_defender", 0.0)), float(k.get("defender_to_attacker", 0.0)), float(deltas.get("attacker_loss", 0.0)), float(deltas.get("defender_loss", 0.0))], r.position + Vector2(18, 240), 10, GOLD, r.size.x - 36)
    else:
        _text("No direct engagement. Use movement/attack tools before starting the simulation.", r.position + Vector2(18, 240), 10, MUTED, r.size.x - 36)

    if _orders_locked():
        _panel(Rect2(r.position.x + 18, r.position.y + 270, r.size.x - 36, 54), Color(0.07, 0.045, 0.035, 0.92), Color(0.35, 0.22, 0.12))
        _text("시뮬레이션 진행 중", r.position + Vector2(30, 292), 12, GOLD, r.size.x - 60)
        _text("일시정지할 때까지 경유점/자세/표적/부대 편집이 잠깁니다.", r.position + Vector2(30, 314), 10, MUTED, r.size.x - 60)
        return

    var button_w: float = max(64.0, min(88.0, (r.size.x - 54.0) / 4.0))
    var bx := r.position.x + 18.0
    var by := r.position.y + 266.0
    _button(Rect2(bx, by, button_w, 30), "이동", "order_move", _order_mode == "move")
    _button(Rect2(bx + button_w + 8, by, button_w, 30), "공격", "order_attack", _order_mode == "attack")
    _button(Rect2(bx + (button_w + 8) * 2.0, by, button_w, 30), "방어", "order_defend", _order_mode == "defend")
    _button(Rect2(bx + (button_w + 8) * 3.0, by, button_w, 30), "후퇴", "order_retreat", _order_mode == "retreat")
    var edit_y := by + 40.0
    var edit_w: float = max(76.0, (r.size.x - 56.0) / 4.0)
    _button(Rect2(bx, edit_y, edit_w, 30), "Edit position", "edit_position", _tool_mode == "edit_position")
    _button(Rect2(bx + edit_w + 8, edit_y, edit_w, 30), "경유점 추가", "waypoint_append", _tool_mode == "move")
    _button(Rect2(bx + (edit_w + 8) * 2.0, edit_y, edit_w, 30), "마지막 제거", "waypoint_remove_last")
    _button(Rect2(bx + (edit_w + 8) * 3.0, edit_y, edit_w, 30), "경유점 초기화", "waypoint_clear")


func _engagement_panel(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("교전 / Lanchester", r.position + Vector2(12, 20), 13, TEXT)
    var eg := _engagement_for_unit(_selected_unit_id)
    if eg.is_empty():
        _text("선택 부대의 직접 교전 기록이 없습니다.", r.position + Vector2(16, 52), 11, MUTED, r.size.x - 32)
        _text("교전 발생 후 손실률과 계수가 표시됩니다.", r.position + Vector2(16, 76), 10, MUTED, r.size.x - 32)
        return
    var a: Dictionary = eg.get("attacker", {})
    var b: Dictionary = eg.get("defender", {})
    var deltas: Dictionary = eg.get("last_deltas", {})
    var k: Dictionary = eg.get("last_k", {})
    var terrain: Dictionary = eg.get("terrain_factors", {})
    _text("%s  vs  %s" % [str(a.get("name", "A")), str(b.get("name", "B"))], r.position + Vector2(16, 50), 12, TEXT, r.size.x - 32)
    _text("Range %0.0fm / active %0.0fs / %s" % [float(eg.get("range_m", 0.0)), float(eg.get("active_seconds", 0.0)), str(eg.get("law", "Square"))], r.position + Vector2(16, 72), 10, MUTED, r.size.x - 32)
    _stat_bar(Vector2(r.position.x + 16, r.position.y + 96), r.size.x - 32, "공격자", float(a.get("strength", 0.0)), float(a.get("max_strength", 1.0)), RED if str(a.get("side", "")) == "red" else BLUE)
    _stat_bar(Vector2(r.position.x + 16, r.position.y + 120), r.size.x - 32, "방어자", float(b.get("strength", 0.0)), float(b.get("max_strength", 1.0)), RED if str(b.get("side", "")) == "red" else BLUE)
    _text("loss A %0.3f  B %0.3f  |  terrain A %0.2f  B %0.2f" % [float(deltas.get("attacker_loss", 0.0)), float(deltas.get("defender_loss", 0.0)), float(terrain.get("attacker", 1.0)), float(terrain.get("defender", 1.0))], r.position + Vector2(16, 148), 10, MUTED, r.size.x - 32)
    _text("k A->B %0.5f  k B->A %0.5f" % [float(k.get("attacker_to_defender", 0.0)), float(k.get("defender_to_attacker", 0.0))], r.position + Vector2(16, 168), 10, GOLD, r.size.x - 160)
    _button(Rect2(r.end.x - 132, r.end.y - 38, 116, 28), "그래프 열기", "dialog_engagement_graph")


func _draw_engagement_history_graph(plot: Rect2, eg: Dictionary) -> void:
    draw_rect(plot, Color(0.025, 0.030, 0.030), true)
    draw_rect(plot, Color(0.18, 0.22, 0.21), false, 1.0)
    for i in range(1, 4):
        var y := plot.position.y + plot.size.y * float(i) / 4.0
        draw_line(Vector2(plot.position.x, y), Vector2(plot.end.x, y), Color(0.25, 0.28, 0.26, 0.25), 1.0)
    var history: Array = eg.get("history", [])
    if history.size() < 2:
        _text("No engagement history", plot.position + Vector2(8, 20), 9, MUTED, plot.size.x - 16)
        return
    var max_s := 1.0
    for h in history:
        max_s = max(max(max_s, float(h.get("a_strength", 0.0))), float(h.get("b_strength", 0.0)))
    var a_points := PackedVector2Array()
    var b_points := PackedVector2Array()
    for i in range(history.size()):
        var h: Dictionary = history[i]
        var x: float = plot.position.x + plot.size.x * float(i) / max(float(history.size() - 1), 1.0)
        a_points.append(Vector2(x, plot.end.y - plot.size.y * clamp(float(h.get("a_strength", 0.0)) / max_s, 0.0, 1.0)))
        b_points.append(Vector2(x, plot.end.y - plot.size.y * clamp(float(h.get("b_strength", 0.0)) / max_s, 0.0, 1.0)))
    if a_points.size() >= 2:
        draw_polyline(a_points, RED, 2.0, true)
        draw_polyline(b_points, BLUE, 2.0, true)
    _text("A", plot.position + Vector2(6, 14), 9, RED)
    _text("B", plot.position + Vector2(28, 14), 9, BLUE)


func _ensure_unit_type_matches_active_side() -> void:
    if _unit_type_options.is_empty():
        return
    if str(_unit_type_options[_selected_unit_type_index].get("side", "")) == _active_oob_side:
        return
    for i in range(_unit_type_options.size()):
        if str(_unit_type_options[i].get("side", "")) == _active_oob_side:
            _selected_unit_type_index = i
            return

func _cycle_unit_type(direction: int) -> void:
    if _unit_type_options.is_empty():
        return
    var idx := _selected_unit_type_index
    for _i in range(_unit_type_options.size()):
        idx = (idx + direction + _unit_type_options.size()) % _unit_type_options.size()
        if str(_unit_type_options[idx].get("side", "")) == _active_oob_side:
            _selected_unit_type_index = idx
            return

func _draw_add_unit_controls(r: Rect2) -> void:
    _ensure_unit_type_matches_active_side()
    var option: Dictionary = _unit_type_options[_selected_unit_type_index]
    if _add_unit_echelon_index < 0 or _add_unit_echelon_index >= _add_unit_echelon_options.size():
        _add_unit_echelon_index = max(0, _add_unit_echelon_options.find(str(option.get("echelon", "I"))))
    _panel(r, Color(0.030, 0.036, 0.038, 1.0), Color(0.22, 0.27, 0.27))
    var side_label := "RED" if _active_oob_side == "red" else "BLUE"
    var option_kind := str(option.get("kind", "tank"))
    var kind_label := "artillery" if option_kind == "artillery" else ("recon/WTA" if option_kind == "recon" else "tank/mech")
    _text("부대 추가", r.position + Vector2(10, 20), 12, GOLD, r.size.x - 94)
    _button(Rect2(r.end.x - 72, r.position.y + 10, 28, 26), "<", "unit_type_prev")
    _button(Rect2(r.end.x - 38, r.position.y + 10, 28, 26), ">", "unit_type_next")
    if _orders_locked():
        _text("시뮬레이션 중에는 추가/편집 잠금", r.position + Vector2(10, 46), 10, MUTED, r.size.x - 20)
        _text("일시정지 후 부대 유형을 선택하세요.", r.position + Vector2(10, 66), 9, MUTED, r.size.x - 20)
        return
    _text("%s  |  %s  |  %s" % [str(option.get("label", "custom")), side_label, kind_label], r.position + Vector2(10, 44), 10, TEXT, r.size.x - 20)
    _text("type %s · strength %.0f · speed %.1f · armor %.2f" % [str(option.get("type", "")), float(option.get("strength", 0.0)), float(option.get("speed_mps", 0.0)), float(option.get("armor", 1.0))], r.position + Vector2(10, 64), 9, MUTED, r.size.x - 20)
    var reserve_ratio := float(_add_unit_reserve_ratio_options[_add_unit_reserve_ratio_index])
    var echelon := str(_add_unit_echelon_options[_add_unit_echelon_index])
    _button(Rect2(r.position.x + 10, r.position.y + 78, 86, 24), "예비 %s" % ("ON" if _add_unit_as_reserve else "OFF"), "add_reserve_toggle", _add_unit_as_reserve)
    _button(Rect2(r.position.x + 102, r.position.y + 78, 82, 24), "트리거 %.0f%%" % (reserve_ratio * 100.0), "add_reserve_ratio")
    _button(Rect2(r.position.x + 190, r.position.y + 78, 74, 24), "규모 %s" % echelon, "add_echelon")
    var trigger_note := "예비 ON: %s %s 손실 %.0f%% 시 투입" % [side_label, kind_label, reserve_ratio * 100.0]
    _text(trigger_note if _add_unit_as_reserve else "규모 표식은 단대호 위에 표시됩니다.", r.position + Vector2(10, 108), 9, MUTED, r.size.x - 20)
    _button(Rect2(r.position.x + 10, r.end.y - 32, r.size.x - 20, 26), "선택 형식 추가", "add_unit")

func _engagement_for_unit(unit_id: String) -> Dictionary:
    if unit_id == "":
        return {}
    for eg in _engagements:
        var a: Dictionary = eg.get("attacker", {})
        var b: Dictionary = eg.get("defender", {})
        if str(a.get("id", "")) == unit_id or str(b.get("id", "")) == unit_id:
            return eg
    return {}

func _orders_locked() -> bool:
    return _playing

func _unit_action_text(unit: Dictionary) -> String:
    var eg := _engagement_for_unit(str(unit.get("id", "")))
    if not eg.is_empty():
        return "교전 중 - %0.0fm, Lanchester 적용" % float(eg.get("range_m", 0.0))
    var order: Dictionary = unit.get("order", {})
    var intent := str(order.get("intent", _unit_orders.get(str(unit.get("id", "")), {}).get("intent", "idle")))
    if Array(unit.get("waypoints", [])).size() > 0:
        return "%s / 경유점 이동" % _intent_label(intent)
    if str(unit.get("kind", "")) == "artillery":
        return "화력지원 대기 / 탄약 %s" % str(unit.get("ammo_remaining", "-"))
    return _intent_label(intent)

func _model_panel(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("Lanchester 교전 예측 + DES", r.position + Vector2(12, 20), 13, TEXT)
    var summary: Dictionary = _state.get("summary", {})
    var red := float(summary.get("red_strength", INITIAL_RED_STRENGTH))
    var blue := float(summary.get("blue_strength", INITIAL_BLUE_STRENGTH))
    _text("Square Law 직접사격", r.position + Vector2(16, 50), 12, TEXT)
    _text("전차: P_hit × P_pen × P_k|pen → 4-State", r.position + Vector2(16, 68), 10, MUTED)
    _text("Linear Law 간접사격", r.position + Vector2(16, 94), 12, TEXT)
    _text("포병: q × a × LA × N / A_target, DES 240초 지연", r.position + Vector2(16, 112), 10, MUTED)
    if not _engagements.is_empty():
        var eg: Dictionary = _engagements[0]
        var a: Dictionary = eg.get("attacker", {})
        var b: Dictionary = eg.get("defender", {})
        _text("Active: %s vs %s  d %.2f / %.2f" % [str(a.get("name", "A")), str(b.get("name", "B")), float(eg.get("last_deltas", {}).get("attacker_loss", 0.0)), float(eg.get("last_deltas", {}).get("defender_loss", 0.0))], r.position + Vector2(16, 184), 9, GOLD, r.size.x - 230)
    else:
        _text("No active engagement prediction", r.position + Vector2(16, 184), 9, MUTED, r.size.x - 230)
    _text("전투력 비율 RED : BLUE", r.position + Vector2(r.size.x - 192, 50), 11, MUTED)
    _text("%0.2f : 1" % (red / max(blue, 1.0)), r.position + Vector2(r.size.x - 192, 82), 25, TEXT)
    var box := Rect2(r.position.x + r.size.x - 204, r.position.y + 106, 188, 76)
    _panel(box, PANEL_DARK, LINE)
    _text("Key modifiers", box.position + Vector2(10, 18), 11, TEXT, box.size.x - 20)
    _text("Terrain / LOS +15%", box.position + Vector2(10, 36), 10, GREEN, box.size.x - 20)
    _text("Fatigue / ammo -9%", box.position + Vector2(10, 52), 10, RED, box.size.x - 20)
    _text("Net modifier +31%", box.position + Vector2(10, 68), 10, GOLD, box.size.x - 20)
    var toggles := ["Square", "Linear", "CB", "Bracken"]
    for i in range(toggles.size()):
        var col := i % 3
        var row := int(i / 3)
        var x := r.position.x + 16 + col * 92
        var y := r.position.y + 152 + row * 19
        draw_rect(Rect2(x, y, 14, 14), Color(0.06, 0.11, 0.07), true)
        draw_rect(Rect2(x, y, 14, 14), GREEN, false, 1)
        draw_line(Vector2(x + 3, y + 8), Vector2(x + 6, y + 11), GREEN, 1.5)
        draw_line(Vector2(x + 6, y + 11), Vector2(x + 12, y + 3), GREEN, 1.5)
        _text(str(toggles[i]), Vector2(x + 20, y + 12), 10, TEXT, 70)


func _damage_chart(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("전투력 추이 / C(t)", r.position + Vector2(12, 20), 13, TEXT)
    _text("C(t)=전체 전투력. 교전/포병 손실 변화가 누적됩니다.", r.position + Vector2(12, 38), 9, MUTED, r.size.x - 24)
    var plot := Rect2(r.position + Vector2(42, 58), r.size - Vector2(58, 72))
    draw_rect(plot, Color(0.025, 0.030, 0.030), true)
    for i in range(5):
        var y := plot.position.y + i * plot.size.y / 4.0
        draw_line(Vector2(plot.position.x, y), Vector2(plot.end.x, y), Color(0.25, 0.28, 0.26, 0.32), 1)
    for i in range(6):
        var x := plot.position.x + i * plot.size.x / 5.0
        draw_line(Vector2(x, plot.position.y), Vector2(x, plot.end.y), Color(0.25, 0.28, 0.26, 0.24), 1)
    if _history.size() >= 2:
        _history_line(plot, "red", RED, INITIAL_RED_STRENGTH)
        _history_line(plot, "blue", BLUE, INITIAL_BLUE_STRENGTH)
    _text("Red", plot.position + Vector2(8, 14), 10, RED)
    _text("Blue", plot.position + Vector2(72, 14), 10, BLUE)

func _draw_bottom() -> void:
    var gap := 8.0
    var timeline := Rect2(_bottom_rect.position, Vector2(_bottom_rect.size.x * 0.34, _bottom_rect.size.y))
    var queue := Rect2(timeline.end.x + gap, _bottom_rect.position.y, _bottom_rect.size.x * 0.27, _bottom_rect.size.y)
    var log := Rect2(queue.end.x + gap, _bottom_rect.position.y, _bottom_rect.end.x - queue.end.x - gap, _bottom_rect.size.y)
    _timeline(timeline)
    _command_queue(queue)
    _event_log(log)

func _timeline(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("시간 / 리플레이", r.position + Vector2(12, 22), 13, TEXT)
    var summary: Dictionary = _state.get("summary", {})
    var has_replay := not _replay_frames.is_empty()
    var total_frames: int = max(1, int(summary.get("total_frames", max(1, int(float(summary.get("expected_duration_s", 3600.0)) / STEP_SECONDS)))))
    var current_frame: int = clamp(int(summary.get("current_frame", int(float(_state.get("time_s", 0.0)) / STEP_SECONDS))), 0, total_frames)
    if has_replay:
        total_frames = max(1, _replay_frames.size())
        current_frame = clamp(_replay_index + 1, 1, total_frames)
    var progress: float = clamp(float(summary.get("progress_ratio", float(current_frame) / float(total_frames))), 0.0, 1.0)
    if has_replay:
        progress = clamp(float(_replay_index) / max(float(_replay_frames.size() - 1), 1.0), 0.0, 1.0)
    elif bool(summary.get("ended", false)):
        progress = 1.0

    _text("현재 %s" % _clock_text(), r.position + Vector2(14, 52), 12, GOLD)
    _text("프레임 %d / %d" % [current_frame, total_frames], r.position + Vector2(r.size.x * 0.38, 52), 10, TEXT)
    _text(_playback_rate_label(), r.position + Vector2(r.size.x - 142, 52), 10, TEXT, 130)

    var line_y := r.position.y + 78
    var line_start := Vector2(r.position.x + 22, line_y)
    var line_end := Vector2(r.end.x - 22, line_y)
    _timeline_seek_rect = Rect2(line_start - Vector2(8, 14), Vector2(line_end.x - line_start.x + 16, 28))
    draw_line(line_start, line_end, Color(0.58, 0.60, 0.56), 2)
    draw_line(line_start, Vector2(lerp(line_start.x, line_end.x, progress), line_y), GOLD, 4)
    draw_circle(Vector2(lerp(line_start.x, line_end.x, progress), line_y), 7, GOLD)
    if has_replay:
        _text("진행바 클릭/드래그로 계산된 프레임으로 즉시 이동", r.position + Vector2(14, 104), 10, MUTED, r.size.x - 28)
    elif bool(summary.get("ended", false)):
        _text("교전 종료: %s / %s" % [str(summary.get("winner", "-")), str(summary.get("end_reason", ""))], r.position + Vector2(14, 104), 10, GOLD, r.size.x - 28)
    elif _replay_calculating:
        _text("전체 프레임 계산 중... 완료되면 캐시 리플레이로 전환됩니다.", r.position + Vector2(14, 104), 10, GOLD, r.size.x - 28)
    elif not _last_replay_meta.is_empty():
        _text("계산 완료: %d프레임 / %0.0fms / 종료=%s" % [int(_last_replay_meta.get("frames", _replay_frames.size())), float(_last_replay_meta.get("compute_ms", 0.0)), str(_last_replay_meta.get("end_reason", ""))], r.position + Vector2(14, 104), 10, GOLD, r.size.x - 28)

    var bx := r.position.x + 18
    _button(Rect2(bx, r.end.y - 48, 48, 34), "일시" if (_playing or _replay_playing) else "재생", "toggle_play", _playing or _replay_playing)
    _button(Rect2(bx + 54, r.end.y - 48, 48, 34), "뒤로", "replay_back")
    _button(Rect2(bx + 108, r.end.y - 48, 48, 34), "한칸", "step")
    var calc_label := "계산중" if _replay_calculating else ("계산됨" if has_replay else "계산")
    _button(Rect2(bx + 162, r.end.y - 48, 64, 34), calc_label, "replay_generate", _replay_calculating)
    _button(Rect2(bx + 232, r.end.y - 48, 68, 34), "일시" if _replay_playing else "리플레이", "replay_play", _replay_playing)
    _button(Rect2(bx + 306, r.end.y - 48, 54, 34), "통계", "dialog_stats")
    var sx := bx + 372
    if has_replay:
        _text("FPS", Vector2(sx, r.end.y - 56), 8, MUTED, 36)
        for i in range(_replay_fps_options.size()):
            _button(Rect2(sx + i * 42, r.end.y - 48, 36, 34), "%d" % int(_replay_fps_options[i]), "replay_fps_%d" % i, i == _replay_fps_index)
    else:
        _text("Speed", Vector2(sx, r.end.y - 56), 8, MUTED, 36)
        for i in range(_speeds.size()):
            _button(Rect2(sx + i * 48, r.end.y - 48, 42, 34), "x%0.1f" % float(_speeds[i]), "speed_%d" % i, i == _speed_index)

func _command_queue(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("명령 대기열", r.position + Vector2(12, 22), 13, TEXT)
    var unit := _selected_unit()
    var lines: Array = []
    if not unit.is_empty():
        var uid := str(unit.get("id", ""))
        var order: Dictionary = _unit_orders.get(uid, {})
        var intent := str(order.get("intent", _order_mode))
        lines.append("%s : %s" % [str(unit.get("name", "unit")), _intent_label(intent)])
        lines.append("Waypoints %d, right-click to update" % Array(unit.get("waypoints", [])).size())
    for item in _manual_queue.slice(max(0, _manual_queue.size() - 2), _manual_queue.size()):
        lines.append(str(item))
    var missions: Array = _state.get("fire_missions", [])
    if missions.is_empty():
        lines.append("Artillery WTA: waiting for recon report")
    else:
        for mission in missions.slice(0, min(2, missions.size())):
            lines.append("WTA %s -> %s via %s" % [str(mission.get("artillery_id", "ART")), str(mission.get("target_name", "target")), str(mission.get("detector_name", "recon"))])
    var y := r.position.y + 48
    var idx := 1
    for line in lines:
        if y > r.end.y - 48:
            break
        _text("%d) %s" % [idx, line], Vector2(r.position.x + 14, y), 10, TEXT if idx < 3 else MUTED, r.size.x - 28)
        y += 22
        idx += 1
    _button(Rect2(r.position.x + 14, r.end.y - 40, 74, 28), "추가", "queue_add")
    _button(Rect2(r.position.x + 94, r.end.y - 40, 64, 28), "비움", "queue_clear")
    _button(Rect2(r.position.x + 164, r.end.y - 40, 92, 28), "부대 저장", "file_unitset_save")
    _button(Rect2(r.position.x + 262, r.end.y - 40, 92, 28), "부대 열기", "file_unitset_load")

func _event_log(r: Rect2) -> void:
    _event_log_rect = r
    _panel(r, PANEL, LINE)
    _text("전투 로그", r.position + Vector2(12, 22), 13, TEXT)
    var row_h := 20.0
    var visible_rows: int = max(1, int(floor((r.size.y - 58.0) / row_h)))
    _event_log_max_scroll = max(0, _events.size() - visible_rows)
    _event_log_scroll = clamp(_event_log_scroll, 0, _event_log_max_scroll)
    var y := r.position.y + 48.0
    if _events.is_empty():
        _text("전투 로그가 아직 없습니다", r.position + Vector2(14, y), 10, MUTED)
        return
    var start_index: int = _events.size() - 1 - _event_log_scroll
    var shown := 0
    for idx in range(start_index, -1, -1):
        if shown >= visible_rows:
            break
        var e: Dictionary = _events[idx]
        _text("%s  %s" % [_event_time(float(e.get("time_s", 0.0))), _event_message_ko(e)], Vector2(r.position.x + 14, y), 10, TEXT, r.size.x - 34)
        y += row_h
        shown += 1
    if _event_log_max_scroll > 0:
        var track := Rect2(r.end.x - 12.0, r.position.y + 46.0, 4.0, max(24.0, r.size.y - 64.0))
        draw_rect(track, Color(0.12, 0.14, 0.13, 0.85), true)
        var knob_h: float = max(18.0, track.size.y * float(visible_rows) / float(_events.size()))
        var travel: float = max(1.0, track.size.y - knob_h)
        var ratio: float = float(_event_log_scroll) / float(max(_event_log_max_scroll, 1))
        var knob := Rect2(track.position + Vector2(0, travel * ratio), Vector2(track.size.x, knob_h))
        draw_rect(knob, GOLD, true)
        _text("??? ?? ??/?? ??", Vector2(r.position.x + 14, r.end.y - 10), 8, MUTED, r.size.x - 40)

func _parameter_lab(r: Rect2) -> void:
    _panel(r, PANEL, LINE)
    _text("Parameter lab", r.position + Vector2(12, 22), 13, TEXT, r.size.x - 24)
    _text("Queued commands are sent to the Python backend.", r.position + Vector2(12, 42), 10, MUTED, r.size.x - 24)
    _parameter_row(r.position + Vector2(16, 62), r.size.x - 32, "direct_fire_scale", "Direct fire", "Lanchester")
    _parameter_row(r.position + Vector2(16, 89), r.size.x - 32, "artillery_delay_s", "Artillery delay", "DES")
    _parameter_row(r.position + Vector2(16, 116), r.size.x - 32, "artillery_damage_scale", "Artillery dmg", "scale")
    _parameter_row(r.position + Vector2(16, 143), r.size.x - 32, "target_area_scale", "Target area", "scale")
    var by := r.end.y - 30.0
    _button(Rect2(r.position.x + 14, by, 72, 24), "Cfg save", "config_dump")
    _button(Rect2(r.position.x + 92, by, 72, 24), "Cfg load", "config_load")
    _button(Rect2(r.position.x + 170, by, 78, 24), "State save", "state_dump")
    _button(Rect2(r.position.x + 254, by, 78, 24), "State load", "state_load")

func _parameter_row(pos: Vector2, width: float, key: String, label: String, note: String) -> void:
    var value := float(_parameters.get(key, 1.0))
    var schema: Dictionary = _parameter_schema.get(key, {})
    var min_v := float(schema.get("min", 0.0))
    var max_v := float(schema.get("max", 1.0))
    var pct: float = clamp((value - min_v) / max(max_v - min_v, 0.001), 0.0, 1.0)
    _text(label, pos, 10, TEXT, 112)
    var bar_y := pos.y + 14
    var bar_x := pos.x + 122
    var value_x := pos.x + width - 116
    var bar_w: float = max(value_x - bar_x - 66.0, 40.0)
    draw_line(Vector2(bar_x, bar_y), Vector2(bar_x + bar_w, bar_y), Color(0.25, 0.28, 0.26), 3)
    draw_line(Vector2(bar_x, bar_y), Vector2(bar_x + bar_w * pct, bar_y), GOLD, 3)
    draw_circle(Vector2(bar_x + bar_w * pct, bar_y), 6, GOLD)
    _text(note, Vector2(bar_x + bar_w + 8.0, pos.y), 9, MUTED, 52)
    _text(_format_parameter(key, value), Vector2(value_x, pos.y + 2), 10, TEXT, 54)
    _button(Rect2(pos.x + width - 58, pos.y - 5, 24, 22), "-", "param_" + key + "_dec")
    _button(Rect2(pos.x + width - 28, pos.y - 5, 24, 22), "+", "param_" + key + "_inc")

func _parameter_input_row(pos: Vector2, width: float, key: String, label: String, note: String, desc: String = "") -> void:
    var value := float(_parameters.get(key, 1.0))
    var schema: Dictionary = _parameter_schema.get(key, {})
    var min_v := float(schema.get("min", 0.0))
    var max_v := float(schema.get("max", 1.0))
    var pct: float = clamp((value - min_v) / max(max_v - min_v, 0.001), 0.0, 1.0)
    var label_w: float = clamp(width * 0.30, 116.0, 156.0)
    var input_w := 72.0
    var button_w := 54.0
    var input := Rect2(pos.x + width - input_w - button_w - 8.0, pos.y - 5, input_w, 24)
    var button := Rect2(pos.x + width - button_w, pos.y - 5, button_w, 24)
    var bar_x: float = pos.x + label_w
    var bar_y := pos.y + 14
    var bar_w: float = max(input.position.x - bar_x - 54.0, 56.0)
    _text(label, pos, 10, TEXT, label_w - 8.0)
    if desc != "":
        _text(desc, pos + Vector2(0, 34), 8, MUTED, width - 72.0)
    draw_line(Vector2(bar_x, bar_y), Vector2(bar_x + bar_w, bar_y), Color(0.25, 0.28, 0.26), 3)
    draw_line(Vector2(bar_x, bar_y), Vector2(bar_x + bar_w * pct, bar_y), GOLD, 3)
    draw_circle(Vector2(bar_x + bar_w * pct, bar_y), 5, GOLD)
    _text(note, Vector2(bar_x + bar_w + 8.0, pos.y + 1.0), 9, MUTED, 42)
    _panel(input, Color(0.025, 0.032, 0.034), GOLD if _editing_parameter_key == key else Color(0.18, 0.22, 0.22))
    var shown := _parameter_input_buffer if _editing_parameter_key == key else _format_parameter_raw(key, value)
    _text(shown, input.position + Vector2(7, 17), 10, TEXT, input.size.x - 12)
    _buttons.append({"rect": input.grow(4.0), "action": "param_edit|" + key})
    _button(button, "적용", "param_commit")

func _format_parameter_raw(key: String, value: float) -> String:
    if key == "artillery_delay_s":
        return "%0.0f" % value
    if key == "red_force_end_ratio" or key == "unit_removal_ratio":
        return "%0.0f" % (value * 100.0)
    if key == "blue_tank_end_count":
        return "%0.0f" % value
    return "%0.2f" % value

func _start_parameter_edit(key: String) -> void:
    _editing_parameter_key = key
    _parameter_input_buffer = _format_parameter_raw(key, float(_parameters.get(key, 1.0)))
    _status = "파라미터 편집: %s" % key

func _commit_parameter_input() -> void:
    if _editing_parameter_key == "":
        return
    if not _parameter_input_buffer.is_valid_float():
        _status = "숫자 형식이 아닙니다: %s" % _parameter_input_buffer
        return
    var key := _editing_parameter_key
    var schema: Dictionary = _parameter_schema.get(key, {})
    var min_v := float(schema.get("min", -INF))
    var max_v := float(schema.get("max", INF))
    var entered := float(_parameter_input_buffer)
    if key == "red_force_end_ratio" or key == "unit_removal_ratio":
        entered = entered / 100.0 if entered > 1.0 else entered
    var next_value: float = clamp(entered, min_v, max_v)
    _parameters[key] = next_value
    BackendClient.update_parameters({key: next_value})
    _status = "파라미터 적용: %s = %s" % [key, _format_parameter(key, next_value)]
    _editing_parameter_key = ""
    _parameter_input_buffer = ""
    queue_redraw()

func _handle_parameter_key(event: InputEventKey) -> bool:
    if _editing_parameter_key == "" or not event.pressed or event.echo:
        return false
    var kc := event.keycode
    if kc >= KEY_0 and kc <= KEY_9:
        _parameter_input_buffer += str(kc - KEY_0)
    elif kc >= KEY_KP_0 and kc <= KEY_KP_9:
        _parameter_input_buffer += str(kc - KEY_KP_0)
    elif kc == KEY_PERIOD or kc == KEY_KP_PERIOD:
        if not _parameter_input_buffer.contains("."):
            _parameter_input_buffer += "."
    elif kc == KEY_MINUS:
        if _parameter_input_buffer.begins_with("-"):
            _parameter_input_buffer = _parameter_input_buffer.substr(1)
        else:
            _parameter_input_buffer = "-" + _parameter_input_buffer
    elif kc == KEY_BACKSPACE:
        if _parameter_input_buffer.length() > 0:
            _parameter_input_buffer = _parameter_input_buffer.substr(0, _parameter_input_buffer.length() - 1)
    elif kc == KEY_ENTER or kc == KEY_KP_ENTER:
        _commit_parameter_input()
    elif kc == KEY_ESCAPE:
        _editing_parameter_key = ""
        _parameter_input_buffer = ""
    else:
        return false
    queue_redraw()
    return true

func _format_parameter(key: String, value: float) -> String:
    if key == "artillery_delay_s":
        return "%0.0fs" % value
    if key == "red_force_end_ratio" or key == "unit_removal_ratio":
        return "%0.0f%%" % (value * 100.0)
    if key == "blue_tank_end_count":
        return "%0.0f" % value
    return "%0.2f" % value

func _change_parameter(key: String, direction: int) -> void:
    var schema: Dictionary = _parameter_schema.get(key, {})
    var current := float(_parameters.get(key, 1.0))
    var step := float(schema.get("step", 0.1))
    var min_v := float(schema.get("min", 0.0))
    var max_v := float(schema.get("max", 10.0))
    var next_value: float = clamp(current + step * float(direction), min_v, max_v)
    _parameters[key] = next_value
    BackendClient.update_parameters({key: next_value})
    queue_redraw()


func _handle_matrix_action(action: String) -> void:
    var parts := action.split("|")
    if parts.size() < 4:
        return
    var attacker := str(parts[1])
    var target := str(parts[2])
    if _is_same_side_pair(attacker, target):
        _status = "같은 진영 조합은 Lanchester k를 수정하지 않습니다."
        queue_redraw()
        return
    var op := str(parts[3])
    var schema: Dictionary = _lanchester_payload.get("schema", {"step": 0.0001, "min": 0.0, "max": 0.02})
    var step := float(schema.get("step", 0.0001))
    var current := _matrix_value(attacker, target)
    var next_value: float = current + (step if op == "inc" else -step)
    _set_matrix_value(attacker, target, next_value)


func _matrix_key(attacker: String, target: String) -> String:
    return attacker + "->" + target

func _start_matrix_edit(attacker: String, target: String) -> void:
    if _is_same_side_pair(attacker, target):
        _status = "같은 진영 조합은 Lanchester k를 수정하지 않습니다."
        queue_redraw()
        return
    _editing_matrix_key = _matrix_key(attacker, target)
    _matrix_input_buffer = "%0.5f" % _matrix_value(attacker, target)
    _editing_parameter_key = ""
    _parameter_input_buffer = ""
    _status = "Lanchester k 입력: %s 공격 → %s 방어" % [attacker, target]
    queue_redraw()

func _set_matrix_value(attacker: String, target: String, value: float) -> void:
    if _is_same_side_pair(attacker, target):
        _status = "같은 진영 조합은 Lanchester k를 수정하지 않습니다."
        queue_redraw()
        return
    var schema: Dictionary = _lanchester_payload.get("schema", {"step": 0.0001, "min": 0.0, "max": 0.02})
    var min_v := float(schema.get("min", 0.0))
    var max_v := float(schema.get("max", 0.02))
    var next_value: float = clamp(value, min_v, max_v)
    if not _lanchester_matrix.has(attacker):
        _lanchester_matrix[attacker] = {}
    _lanchester_matrix[attacker][target] = next_value
    BackendClient.update_lanchester_matrix({"matrix": {attacker: {target: next_value}}})
    _status = "Lanchester k 적용: %s 공격 → %s 방어 = %0.5f" % [attacker, target, next_value]
    queue_redraw()

func _commit_matrix_input() -> void:
    if _editing_matrix_key == "":
        return
    if not _matrix_input_buffer.is_valid_float():
        _status = "숫자 형식이 아닙니다: %s" % _matrix_input_buffer
        return
    var parts := _editing_matrix_key.split("->")
    if parts.size() < 2:
        _editing_matrix_key = ""
        _matrix_input_buffer = ""
        return
    _set_matrix_value(str(parts[0]), str(parts[1]), float(_matrix_input_buffer))
    _editing_matrix_key = ""
    _matrix_input_buffer = ""

func _handle_matrix_key(event: InputEventKey) -> bool:
    if _editing_matrix_key == "" or not event.pressed or event.echo:
        return false
    var kc := event.keycode
    if kc >= KEY_0 and kc <= KEY_9:
        _matrix_input_buffer += str(kc - KEY_0)
    elif kc >= KEY_KP_0 and kc <= KEY_KP_9:
        _matrix_input_buffer += str(kc - KEY_KP_0)
    elif kc == KEY_PERIOD or kc == KEY_KP_PERIOD:
        if not _matrix_input_buffer.contains("."):
            _matrix_input_buffer += "."
    elif kc == KEY_BACKSPACE:
        if _matrix_input_buffer.length() > 0:
            _matrix_input_buffer = _matrix_input_buffer.substr(0, _matrix_input_buffer.length() - 1)
    elif kc == KEY_ENTER or kc == KEY_KP_ENTER:
        _commit_matrix_input()
    elif kc == KEY_ESCAPE:
        _editing_matrix_key = ""
        _matrix_input_buffer = ""
    else:
        return false
    queue_redraw()
    return true

func _matrix_value(attacker: String, target: String) -> float:
    var row: Dictionary = _lanchester_matrix.get(attacker, {})
    if row.has(target):
        return float(row.get(target, 0.0))
    return 0.0

func _unit_type_side(unit_type: String) -> String:
    var side_map: Dictionary = _lanchester_payload.get("unit_type_sides", {})
    if side_map.has(unit_type):
        return str(side_map.get(unit_type, ""))
    for unit in _state.get("units", []):
        if str(unit.get("type", "")) == unit_type and str(unit.get("kind", "")) == "tank":
            return str(unit.get("side", ""))
    if unit_type.begins_with("T-") or unit_type.begins_with("SU-") or unit_type.begins_with("IS-"):
        return "red"
    if unit_type.begins_with("Pz") or unit_type.begins_with("Panther") or unit_type.begins_with("Tiger"):
        return "blue"
    return ""

func _is_same_side_pair(attacker: String, target: String) -> bool:
    var attacker_side := _unit_type_side(attacker)
    var target_side := _unit_type_side(target)
    return attacker_side != "" and attacker_side == target_side

func _request_replay_precompute(autoplay_after_generate: bool = false) -> void:
    _playing = false
    _replay_playing = false
    _replay_autoplay_after_generate = autoplay_after_generate
    _pending_replay_back = false
    _replay_calculating = true
    _last_replay_meta.clear()
    _status = "Replay precompute: %d frames including initial / 1 simulated day" % REPLAY_SCENARIO_FRAMES
    BackendClient.generate_replay_timeline(REPLAY_SCENARIO_FRAME_INTERVAL_S, REPLAY_SCENARIO_FRAMES, REPLAY_SCENARIO_INTEGRATION_DT_S)

func _matrix_types_all() -> Array:
    var found := {}
    for t in _lanchester_payload.get("unit_types", []):
        found[str(t)] = true
    for t in _lanchester_payload.get("red_unit_types", []):
        found[str(t)] = true
    for t in _lanchester_payload.get("blue_unit_types", []):
        found[str(t)] = true
    for unit in _state.get("units", []):
        if str(unit.get("kind", "")) == "tank":
            found[str(unit.get("type", ""))] = true
    var out := found.keys()
    out.sort()
    return out

func _tank_types_for_side(side: String) -> Array:
    var preferred: Array = _lanchester_payload.get("red_unit_types" if side == "red" else "blue_unit_types", [])
    if not preferred.is_empty():
        preferred.sort()
        return preferred
    var found := {}
    for unit in _state.get("units", []):
        if str(unit.get("side", "")) == side and str(unit.get("kind", "")) == "tank":
            found[str(unit.get("type", ""))] = true
    for t in _lanchester_payload.get("unit_types", []):
        var unit_type := str(t)
        var red_match := unit_type.begins_with("T-") or unit_type.begins_with("SU-") or unit_type.begins_with("IS-")
        var blue_match := unit_type.begins_with("Pz") or unit_type.begins_with("Panther") or unit_type.begins_with("Tiger")
        if side == "red" and red_match:
            found[unit_type] = true
        elif side == "blue" and blue_match:
            found[unit_type] = true
    var out := found.keys()
    out.sort()
    return out

func _draw_dialogs() -> void:
    if _active_dialog == "":
        return
    draw_rect(Rect2(Vector2.ZERO, size), Color(0.0, 0.0, 0.0, 0.48), true)
    if _active_dialog == "params":
        _draw_parameter_dialog()
    elif _active_dialog == "help":
        _draw_help_dialog()
    elif _active_dialog == "engagement_graph":
        _draw_engagement_graph_dialog()
    elif _active_dialog == "stats":
        _draw_statistics_dialog()
    elif _active_dialog == "file_dialog":
        _draw_file_dialog()



func _draw_file_dialog() -> void:
    var r := Rect2(size * 0.22, size * 0.60)
    _panel(r, Color(0.035, 0.045, 0.048, 1.0), LINE)
    var kind := _file_dialog_kind()
    var is_save := _file_dialog_mode.ends_with("_save")
    var title := _file_dialog_title()
    _text(title, r.position + Vector2(18, 30), 18, TEXT, r.size.x - 90)
    _button(Rect2(r.end.x - 70, r.position.y + 14, 52, 28), "닫기", "dialog_close")
    var input_rect := Rect2(r.position.x + 24, r.position.y + 72, r.size.x - 168, 34)
    if is_save:
        _text("이름(확장자 제외)", r.position + Vector2(24, 62), 10, MUTED, r.size.x - 48)
        _panel(input_rect, Color(0.018, 0.024, 0.025, 1.0), GOLD if _editing_file_name else Color(0.34, 0.41, 0.42))
        _text(_file_name_buffer, input_rect.position + Vector2(10, 23), 12, TEXT, input_rect.size.x - 20)
        _buttons.append({"rect": input_rect.grow(4.0), "action": "file_name_edit"})
        _button(Rect2(r.end.x - 126, r.position.y + 74, 94, 30), "저장", "file_save_confirm")
    else:
        _text("저장할 이름을 입력하세요. 기존 이름과 같으면 덮어씁니다.", r.position + Vector2(24, 84), 11, MUTED, r.size.x - 48)
    _refresh_file_dialog_items(kind)
    var list_y := r.position.y + 126.0
    _text("저장 목록", Vector2(r.position.x + 24, list_y), 12, GOLD, r.size.x - 48)
    list_y += 24.0
    _file_scroll_track = Rect2()
    _file_scroll_knob = Rect2()
    var row_step := 32.0
    var visible_rows := int(max(1.0, floor((r.end.y - list_y - 18.0) / row_step)))
    var max_start: int = max(0, _file_dialog_items.size() - visible_rows)
    _file_dialog_scroll = clamp(_file_dialog_scroll, 0.0, float(max_start))
    _file_scroll_max = float(max_start)
    var start_index := int(round(_file_dialog_scroll))
    if _file_dialog_items.is_empty():
        _text("저장된 파일이 없습니다.", Vector2(r.position.x + 28, list_y + 18), 11, MUTED, r.size.x - 56)
    else:
        var end_index: int = min(_file_dialog_items.size(), start_index + visible_rows)
        for idx in range(start_index, end_index):
            var item: Dictionary = _file_dialog_items[idx]
            var item_name := str(item.get("name", "file"))
            var item_path := str(item.get("path", ""))
            var row_i := idx - start_index
            var row := Rect2(r.position.x + 24, list_y + row_i * row_step, r.size.x - 48, 26)
            if _file_dialog_items.size() > visible_rows:
                row.size.x -= 18.0
            _panel(row, Color(0.055, 0.065, 0.066, 1.0), Color(0.18, 0.22, 0.22))
            if not is_save:
                var delete_rect := Rect2(row.end.x - 58, row.position.y + 2, 52, 22)
                var load_rect := Rect2(row.position.x, row.position.y, row.size.x - 68, row.size.y)
                _text(item_name, row.position + Vector2(10, 19), 11, TEXT, load_rect.size.x - 20)
                _buttons.append({"rect": load_rect.grow(3.0), "action": "file_load|%s|%s" % [kind, item_path]})
                _button(delete_rect, "삭제", "file_delete|%s|%s" % [kind, item_path])
            else:
                _text(item_name, row.position + Vector2(10, 19), 11, TEXT, row.size.x - 20)
        if _file_dialog_items.size() > visible_rows:
            _file_scroll_track = Rect2(r.end.x - 32.0, list_y, 8.0, max(28.0, visible_rows * row_step - 6.0))
            draw_rect(_file_scroll_track, Color(0.14, 0.16, 0.15), true)
            var knob_h: float = max(24.0, _file_scroll_track.size.y * float(visible_rows) / float(_file_dialog_items.size()))
            var knob_y: float = _file_scroll_track.position.y + (_file_scroll_track.size.y - knob_h) * (float(start_index) / max(float(max_start), 1.0))
            _file_scroll_knob = Rect2(_file_scroll_track.position.x - 2.0, knob_y, _file_scroll_track.size.x + 4.0, knob_h)
            draw_rect(_file_scroll_knob, GOLD, true)
            _text("%d-%d / %d" % [start_index + 1, end_index, _file_dialog_items.size()], Vector2(r.position.x + 24, r.end.y - 10), 8, MUTED, r.size.x - 60)

func _file_dialog_title() -> String:
    var labels := {
        "config_save": "Config 저장",
        "config_load": "Config 불러오기",
        "state_save": "State 저장",
        "state_load": "State 불러오기",
        "unitset_save": "부대편성 저장",
        "unitset_load": "부대편성 불러오기",
    }
    return str(labels.get(_file_dialog_mode, "파일"))

func _file_dialog_kind() -> String:
    if _file_dialog_mode.begins_with("config"):
        return "config"
    if _file_dialog_mode.begins_with("state"):
        return "state"
    return "unitset"

func _open_file_dialog(mode: String) -> void:
    _file_dialog_mode = mode
    _file_name_buffer = _default_save_name(_file_dialog_kind())
    _editing_file_name = mode.ends_with("_save")
    _file_dialog_scroll = 0.0
    _active_dialog = "file_dialog"
    _refresh_file_dialog_items(_file_dialog_kind())
    queue_redraw()

func _refresh_file_dialog_items(kind: String) -> void:
    _file_dialog_items = []
    var path := SAVE_ROOT + "/" + kind
    var dir := DirAccess.open(path)
    if dir == null:
        return
    dir.list_dir_begin()
    var name := dir.get_next()
    while name != "":
        if not dir.current_is_dir() and name.ends_with(".json"):
            _file_dialog_items.append({"name": name.trim_suffix(".json"), "path": path + "/" + name})
        name = dir.get_next()
    dir.list_dir_end()
    _file_dialog_items.sort_custom(func(a, b): return str(a.get("name", "")) < str(b.get("name", "")))

func _default_save_name(kind: String) -> String:
    return "%s_%s" % [kind, Time.get_datetime_string_from_system(false, true).replace(":", "-").replace(" ", "_")]

func _safe_save_name() -> String:
    var out := _file_name_buffer.strip_edges().trim_suffix(".json")
    for ch in ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "."]:
        out = out.replace(ch, "_")
    if out == "":
        out = _default_save_name(_file_dialog_kind())
    return out

func _ensure_save_dir(kind: String) -> String:
    DirAccess.make_dir_recursive_absolute(SAVE_ROOT)
    var path := SAVE_ROOT + "/" + kind
    DirAccess.make_dir_recursive_absolute(path)
    return path

func _save_json_named(kind: String, name: String, payload: Dictionary) -> String:
    var dir := _ensure_save_dir(kind)
    var path := dir + "/" + name + ".json"
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file:
        file.store_string(JSON.stringify(payload, "\t"))
    return path

func _handle_file_dialog_key(event: InputEventKey) -> bool:
    if _active_dialog != "file_dialog" or not _editing_file_name or not event.pressed or event.echo:
        return false
    var kc := event.keycode
    if kc == KEY_BACKSPACE:
        if _file_name_buffer.length() > 0:
            _file_name_buffer = _file_name_buffer.substr(0, _file_name_buffer.length() - 1)
    elif kc == KEY_ENTER or kc == KEY_KP_ENTER:
        _handle_action("file_save_confirm")
    elif kc == KEY_ESCAPE:
        _editing_file_name = false
    else:
        var ch := ""
        if event.unicode > 0:
            ch = char(event.unicode)
        elif kc == KEY_MINUS:
            ch = "-"
        if ch.length() == 1 and ch != "\\" and ch != "/" and ch != ":" and ch != "*" and ch != "?" and ch != char(34) and ch != "<" and ch != ">" and ch != "|" and ch != ".":
            _file_name_buffer += ch
        else:
            return false
    queue_redraw()
    return true

func _load_named_file(kind: String, path: String) -> void:
    if kind == "config":
        _load_dump_file(path, true)
    elif kind == "state":
        _load_dump_file(path, false)
    else:
        _load_unitset_file(path)
    _active_dialog = ""
    _file_dialog_mode = ""

func _delete_named_file(kind: String, path: String) -> void:
    var base := SAVE_ROOT + "/" + kind
    if not path.begins_with(base + "/") or not path.ends_with(".json"):
        _status = "안전하지 않은 파일 삭제 경로: %s" % path
        return
    if not FileAccess.file_exists(path):
        _status = "삭제할 저장 파일이 없습니다: %s" % path
        _refresh_file_dialog_items(kind)
        return
    var dir := DirAccess.open(base)
    if dir == null:
        _status = "저장 폴더를 열 수 없습니다: %s" % base
        return
    var err := dir.remove(path.get_file())
    if err == OK:
        _status = "저장 파일 삭제: %s" % path.get_file().trim_suffix(".json")
        _refresh_file_dialog_items(kind)
    else:
        _status = "저장 파일 삭제 실패(%d): %s" % [err, path]

func _save_unitset_named(name: String) -> void:
    var payload := {
        "schema_version": "2026-05-20.1",
        "units": _state.get("units", []),
        "unit_orders": _unit_orders,
        "manual_queue": _manual_queue,
    }
    var path := _save_json_named("unitset", name, payload)
    _status = "부대편성 저장: %s" % path

func _load_unitset_file(path: String) -> void:
    if not FileAccess.file_exists(path):
        _status = "No unitset file found: %s" % path
        return
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        _status = "Cannot open unitset file: %s" % path
        return
    var parsed = JSON.parse_string(file.get_as_text())
    if typeof(parsed) != TYPE_DICTIONARY:
        _status = "Unitset JSON parse failed: %s" % path
        return
    var next_state := _state.duplicate(true)
    next_state["time_s"] = 0.0
    next_state["units"] = parsed.get("units", [])
    next_state["shells"] = []
    _unit_orders = parsed.get("unit_orders", {})
    _manual_queue = parsed.get("manual_queue", [])
    BackendClient.load_state({"state": next_state})
    _status = "부대편성 불러오기 요청: %s" % path

func _draw_parameter_dialog() -> void:
    var r: Rect2 = Rect2(size * 0.05, size * 0.90)
    _panel(r, Color(0.035, 0.045, 0.048, 0.99), LINE)
    _text("파라미터 / 란체스터 행렬", r.position + Vector2(18, 30), 18, TEXT, r.size.x - 100)
    _button(Rect2(r.end.x - 72, r.position.y + 16, 54, 30), "닫기", "dialog_close")
    _text("비슷한 역할의 조정값을 함께 묶었습니다. 값은 즉시 시뮬레이션/리플레이 계산에 반영됩니다.", r.position + Vector2(18, 58), 11, MUTED, r.size.x - 36)

    var gap := 14.0
    var card_y := r.position.y + 86.0
    var card_h := 240.0
    var card_w: float = (r.size.x - 44.0 - gap * 2.0) / 3.0
    var combat_rows := [
        {"key": "direct_fire_scale", "label": "직사 화력", "unit": "배", "desc": "전차 간 직접 교전 피해량 배율"},
        {"key": "combat_speed_scale", "label": "교전 진행", "unit": "배", "desc": "란체스터 소모가 진행되는 속도"},
    ]
    var artillery_rows := [
        {"key": "artillery_delay_s", "label": "포병 지연", "unit": "초", "desc": "관측 후 포탄 효과가 도착하기까지 시간"},
        {"key": "artillery_damage_scale", "label": "포병 피해", "unit": "배", "desc": "포병/화력지원 피해량 배율"},
        {"key": "target_area_scale", "label": "표적 면적", "unit": "배", "desc": "WTA 표적 분산·영향 면적 보정"},
    ]
    var end_rows := [
        {"key": "red_force_end_ratio", "label": "적 종료 기준", "unit": "%", "desc": "Red 전체 전투력이 초기값 대비 이 비율 이하이면 종료"},
        {"key": "blue_tank_end_count", "label": "아군 전차 종료", "unit": "대", "desc": "Blue 전차 수가 이 값 이하이면 종료"},
        {"key": "unit_removal_ratio", "label": "부대 소멸", "unit": "%", "desc": "개별 부대가 초기 전투력 대비 이 비율 이하이면 제거"},
    ]
    _draw_parameter_group(Rect2(r.position.x + 22.0, card_y, card_w, card_h), "교전 동역학", "직접 교전과 전체 소모 속도", combat_rows)
    _draw_parameter_group(Rect2(r.position.x + 22.0 + card_w + gap, card_y, card_w, card_h), "포병 / WTA", "관측-타격 지연, 피해량, 표적 영향 범위", artillery_rows)
    _draw_parameter_group(Rect2(r.position.x + 22.0 + (card_w + gap) * 2.0, card_y, card_w, card_h), "종료 / 소멸", "시나리오 종료와 개별 부대 제거 규칙", end_rows)

    var io_y := card_y + card_h + 12.0
    _panel(Rect2(r.position.x + 22.0, io_y, r.size.x - 44.0, 44.0), Color(0.030, 0.038, 0.040, 1.0), Color(0.14, 0.18, 0.18))
    _text("저장 / 불러오기", Vector2(r.position.x + 36.0, io_y + 28.0), 11, TEXT, 130)
    _button(Rect2(r.position.x + 170.0, io_y + 8.0, 104, 28), "설정 저장", "config_dump")
    _button(Rect2(r.position.x + 282.0, io_y + 8.0, 104, 28), "설정 열기", "config_load")
    _button(Rect2(r.position.x + 402.0, io_y + 8.0, 108, 28), "상태 저장", "state_dump")
    _button(Rect2(r.position.x + 518.0, io_y + 8.0, 108, 28), "상태 열기", "state_load")

    var all_types: Array = _matrix_types_all()
    var grid := Rect2(r.position.x + 22, io_y + 58.0, r.size.x - 44, r.end.y - (io_y + 82.0))
    _panel(grid, PANEL_DARK, LINE)
    _text("란체스터 K 행렬", grid.position + Vector2(14, 24), 13, GOLD, grid.size.x - 28)
    _text("행은 공격 부대 유형, 열은 방어 부대 유형입니다. 같은 진영 조합은 잠겨 있습니다.", grid.position + Vector2(14, 46), 10, MUTED, grid.size.x - 28)
    if all_types.is_empty():
        _text("백엔드의 전차 유형 데이터를 기다리는 중입니다.", grid.position + Vector2(16, 80), 12, MUTED, grid.size.x - 32)
        return
    var rows: int = min(all_types.size(), 8)
    var cols: int = min(all_types.size(), 8)
    var row_header_w := 128.0
    var usable_w := grid.size.x - row_header_w - 24.0
    var cell_w: float = clamp(usable_w / float(cols), 96.0, 164.0)
    var cell_h := 54.0
    var start := grid.position + Vector2(row_header_w + 12.0, 94.0)
    _panel(Rect2(grid.position + Vector2(12, 68), Vector2(row_header_w - 8.0, 24.0)), Color(0.040, 0.052, 0.054, 1.0), Color(0.16, 0.20, 0.20))
    _text("공격 / 방어", grid.position + Vector2(20, 85), 8, MUTED, row_header_w - 18)
    for c in range(cols):
        var defender := str(all_types[c])
        var defender_side := _unit_type_side(defender).to_upper()
        var hrect := Rect2(start + Vector2(c * cell_w, -26.0), Vector2(cell_w - 6.0, 24.0))
        _panel(hrect, Color(0.040, 0.052, 0.054, 1.0), Color(0.16, 0.20, 0.20))
        _text("%s %s" % [defender, defender_side], hrect.position + Vector2(6, 17), 8, TEXT, hrect.size.x - 12)
    for row_i in range(rows):
        var attacker := str(all_types[row_i])
        var row_y := start.y + row_i * cell_h
        var label_rect := Rect2(grid.position.x + 12.0, row_y, row_header_w - 8.0, cell_h - 6.0)
        var attacker_side := _unit_type_side(attacker).to_upper()
        _panel(label_rect, Color(0.035, 0.044, 0.046, 1.0), Color(0.15, 0.19, 0.19))
        _text(attacker, label_rect.position + Vector2(10, 23), 10, TEXT, label_rect.size.x - 20)
        _text(attacker_side + " 공격", label_rect.position + Vector2(10, 41), 8, MUTED, label_rect.size.x - 20)
        for col_i in range(cols):
            var target := str(all_types[col_i])
            var key := _matrix_key(attacker, target)
            var locked := _is_same_side_pair(attacker, target)
            var cell := Rect2(start + Vector2(col_i * cell_w, row_i * cell_h), Vector2(cell_w - 6.0, cell_h - 6.0))
            var border := Color(0.18, 0.22, 0.22)
            if _editing_matrix_key == key:
                border = GOLD
            elif locked:
                border = Color(0.12, 0.14, 0.14)
            _panel(cell, Color(0.030, 0.035, 0.036, 1.0) if locked else Color(0.043, 0.055, 0.057, 1.0), border)
            if locked:
                _text("동일 진영", cell.position + Vector2(8, 21), 9, MUTED, cell.size.x - 16)
                _text("잠김", cell.position + Vector2(8, 39), 8, Color(0.42, 0.46, 0.44), cell.size.x - 16)
            else:
                _buttons.append({"rect": cell.grow(3.0), "action": "matrix_edit|%s|%s" % [attacker, target]})
                var shown := _matrix_input_buffer if _editing_matrix_key == key else "%0.5f" % _matrix_value(attacker, target)
                var input_rect := Rect2(cell.position + Vector2(7, 7), Vector2(cell.size.x - 14, 23))
                _panel(input_rect, Color(0.018, 0.024, 0.025, 1.0), GOLD if _editing_matrix_key == key else Color(0.46, 0.55, 0.56))
                _text(shown, input_rect.position + Vector2(7, 16), 9, TEXT, input_rect.size.x - 14)
                _button(Rect2(cell.end.x - 48, cell.end.y - 21, 21, 18), "-", "matrix|%s|%s|dec" % [attacker, target])
                _button(Rect2(cell.end.x - 24, cell.end.y - 21, 21, 18), "+", "matrix|%s|%s|inc" % [attacker, target])

func _draw_parameter_group(card: Rect2, title: String, subtitle: String, rows: Array) -> void:
    _panel(card, Color(0.030, 0.038, 0.040, 1.0), Color(0.15, 0.19, 0.19))
    _text(title, card.position + Vector2(12, 22), 13, TEXT, card.size.x - 24)
    _text(subtitle, card.position + Vector2(12, 40), 9, MUTED, card.size.x - 24)
    var y := card.position.y + 66.0
    for row in rows:
        if typeof(row) == TYPE_DICTIONARY:
            _parameter_input_row(Vector2(card.position.x + 12.0, y), card.size.x - 24.0, str(row.get("key", "")), str(row.get("label", "")), str(row.get("unit", "")), str(row.get("desc", "")))
            y += 54.0

func _draw_engagement_graph_dialog() -> void:
    var r := Rect2(size * 0.14, size * 0.72)
    _panel(r, Color(0.035, 0.045, 0.048, 0.98), LINE)
    _text("Engagement matrix", r.position + Vector2(18, 30), 18, TEXT, r.size.x - 90)
    _button(Rect2(r.end.x - 70, r.position.y + 14, 52, 28), "닫기", "dialog_close")
    var eg := _engagement_for_unit(_selected_unit_id)
    if eg.is_empty():
        _text("No engagement history is available yet.", r.position + Vector2(24, 74), 13, MUTED, r.size.x - 48)
        return
    var a: Dictionary = eg.get("attacker", {})
    var b: Dictionary = eg.get("defender", {})
    _text("%s  vs  %s" % [str(a.get("name", "A")), str(b.get("name", "B"))], r.position + Vector2(24, 68), 12, GOLD, r.size.x - 48)
    _draw_engagement_history_graph(Rect2(r.position + Vector2(24, 92), r.size - Vector2(48, 126)), eg)

func _append_history_sample(state: Dictionary) -> void:
    var summary: Dictionary = state.get("summary", {})
    var tank_counts: Dictionary = summary.get("tank_counts", {})
    var exchange: Dictionary = summary.get("exchange", {})
    var reserve_status: Dictionary = summary.get("reserve_status", {})
    var tank_strengths := _tank_type_strengths_from_units(state.get("units", []))
    var sample := {
        "time": float(state.get("time_s", 0.0)),
        "red": float(summary.get("red_strength", INITIAL_RED_STRENGTH)),
        "blue": float(summary.get("blue_strength", INITIAL_BLUE_STRENGTH)),
        "red_tanks": float(summary.get("red_tanks", 0)),
        "blue_tanks": float(summary.get("blue_tanks", 0)),
        "red_losses": float(exchange.get("red_losses", 0.0)),
        "blue_losses": float(exchange.get("blue_losses", 0.0)),
        "loss_exchange_ratio": float(summary.get("loss_exchange_ratio", 0.0)) if summary.get("loss_exchange_ratio") != null else 0.0,
        "reserve_pending_units": float(summary.get("reserve_pending_units", reserve_status.get("pending_units", 0))),
        "reserve_triggered_units": float(summary.get("reserve_triggered_units", reserve_status.get("triggered_units", 0))),
        "red_tank_loss_ratio": float(summary.get("red_tank_loss_ratio", reserve_status.get("red_tank_loss_ratio", 0.0))),
        "red_tank_counts": (tank_counts.get("red", {}) as Dictionary).duplicate(true),
        "blue_tank_counts": (tank_counts.get("blue", {}) as Dictionary).duplicate(true),
        "red_tank_strengths": (tank_strengths.get("red", {}) as Dictionary).duplicate(true),
        "blue_tank_strengths": (tank_strengths.get("blue", {}) as Dictionary).duplicate(true),
    }
    if not _history.is_empty() and abs(float(_history[-1].get("time", -999.0)) - float(sample.get("time", 0.0))) < 0.001:
        _history[-1] = sample
    else:
        _history.append(sample)
    if _history.size() > 240:
        _history.pop_front()

func _rebuild_history_from_replay() -> void:
    if _replay_frames.is_empty():
        return
    _history.clear()
    var stride: int = max(1, int(ceil(float(_replay_frames.size()) / 240.0)))
    for i in range(_replay_frames.size()):
        if i % stride != 0 and i != _replay_frames.size() - 1:
            continue
        var frame = _replay_frames[i]
        if typeof(frame) == TYPE_DICTIONARY:
            _append_history_sample(frame)
    _history_from_replay = true

func _draw_statistics_dialog() -> void:
    var r := Rect2(size * 0.07, size * 0.86)
    _panel(r, Color(0.035, 0.045, 0.048, 0.98), LINE)
    _text("관심 통계", r.position + Vector2(18, 30), 18, TEXT, r.size.x - 100)
    _button(Rect2(r.end.x - 70, r.position.y + 14, 52, 28), "닫기", "dialog_close")
    var summary: Dictionary = _state.get("summary", {})
    var red_threshold := float(summary.get("red_force_end_threshold", 0.0))
    _text("종료 기준: Red ≤ %0.0f(초기 %0.0f%%), Blue 전차 ≤ %d대, 부대 소멸 ≤ %0.0f%%" % [red_threshold, 100.0 * float(_parameters.get("red_force_end_ratio", 0.5)), int(summary.get("blue_tank_end_count", 0)), 100.0 * float(_parameters.get("unit_removal_ratio", 0.2))], r.position + Vector2(22, 62), 11, GOLD, r.size.x - 44)
    _draw_exchange_and_reserve_strip(Rect2(r.position.x + 22, r.position.y + 82, r.size.x - 44, 34), summary)

    var left_w: float = r.size.x * 0.58
    var right_x: float = r.position.x + left_w + 38.0
    var plot_top := r.position.y + 120.0
    var strength_plot := Rect2(r.position + Vector2(22, plot_top - r.position.y), Vector2(left_w - 34.0, r.size.y * 0.30))
    _draw_stats_plot(strength_plot, "전체 병력 전투력", [{"key":"red", "label":"Red", "color":RED}, {"key":"blue", "label":"Blue", "color":BLUE}], "전투력")
    var tank_plot := Rect2(r.position.x + 22, strength_plot.end.y + 30.0, left_w - 34.0, r.size.y * 0.27)
    _draw_stats_plot(tank_plot, "생존 전차 부대 수", [{"key":"red_tanks", "label":"Red 전차", "color":Color(1.0, 0.42, 0.35)}, {"key":"blue_tanks", "label":"Blue 전차", "color":Color(0.35, 0.62, 1.0)}], "부대")
    var type_plot := Rect2(r.position.x + 22, tank_plot.end.y + 30.0, left_w - 34.0, r.end.y - tank_plot.end.y - 52.0)
    _draw_tank_type_trend_plot(type_plot)

    _draw_tank_type_stats(Rect2(right_x, plot_top, r.end.x - right_x - 22.0, r.end.y - plot_top - 24.0), summary)

func _draw_exchange_and_reserve_strip(r: Rect2, summary: Dictionary) -> void:
    var exchange: Dictionary = summary.get("exchange", {})
    var reserve_status: Dictionary = summary.get("reserve_status", {})
    var ratio_text := "∞"
    if summary.get("loss_exchange_ratio") != null:
        ratio_text = "%0.2f:1" % float(summary.get("loss_exchange_ratio", 0.0))
    var threshold_text := "-"
    if reserve_status.get("threshold") != null:
        threshold_text = "%0.0f%%" % (100.0 * float(reserve_status.get("threshold", 0.0)))
    var red_tank_loss := 100.0 * float(summary.get("red_tank_loss_ratio", reserve_status.get("red_tank_loss_ratio", 0.0)))
    var text := "교환비(Red 손실/Blue 손실) %s  ·  손실 Red %.0f / Blue %.0f  ·  Red 예비대 %d투입/%d대기  ·  투입조건 %s, 현재 선발전차손실 %.0f%%" % [
        ratio_text,
        float(exchange.get("red_losses", 0.0)),
        float(exchange.get("blue_losses", 0.0)),
        int(summary.get("reserve_triggered_units", reserve_status.get("triggered_units", 0))),
        int(summary.get("reserve_pending_units", reserve_status.get("pending_units", 0))),
        threshold_text,
        red_tank_loss,
    ]
    _text(text, r.position + Vector2(0, 20), 10, TEXT, r.size.x)

func _draw_stats_plot(plot: Rect2, title: String, series: Array, unit_label: String = "") -> void:
    _panel(plot, Color(0.020, 0.026, 0.027, 1.0), Color(0.18, 0.22, 0.21))
    _text(title, plot.position + Vector2(12, 20), 12, TEXT, plot.size.x - 24)
    if _history.size() < 2:
        _text("아직 시간 샘플이 없습니다. 계산 버튼을 누르거나 시뮬레이션을 진행하세요.", plot.position + Vector2(14, 52), 10, MUTED, plot.size.x - 28)
        return
    var inner := Rect2(plot.position + Vector2(52, 38), plot.size - Vector2(68, 72))
    draw_rect(inner, Color(0.012, 0.016, 0.017, 1.0), true)
    draw_rect(inner, Color(0.16, 0.20, 0.19), false, 1.0)
    var max_value := 1.0
    for item in _history:
        for spec in series:
            max_value = max(max_value, float((item as Dictionary).get(str(spec.get("key", "")), 0.0)))
    max_value = _nice_axis_max(max_value)
    for i in range(5):
        var ratio := float(i) / 4.0
        var y := inner.end.y - inner.size.y * ratio
        var label_value := max_value * ratio
        draw_line(Vector2(inner.position.x, y), Vector2(inner.end.x, y), Color(0.30, 0.34, 0.32, 0.25), 1.0)
        _text(_format_axis_value(label_value), Vector2(plot.position.x + 10, y + 4), 8, MUTED, 38)
    var max_t: float = max(float(_history[-1].get("time", 1.0)), 1.0)
    _text("0", Vector2(inner.position.x, inner.end.y + 18), 8, MUTED, 42)
    _text(_format_time_axis(max_t), Vector2(inner.end.x - 58, inner.end.y + 18), 8, MUTED, 60)
    var legend_x := inner.position.x
    for spec in series:
        var key := str(spec.get("key", ""))
        var color: Color = spec.get("color", GOLD)
        var last_point := _history_line_scaled(inner, key, color, max_value)
        var current := float(_history[-1].get(key, 0.0))
        if last_point.x >= 0.0:
            draw_circle(last_point, 4.0, color)
            _text(_format_axis_value(current), last_point + Vector2(6, -5), 8, color, 52)
        _text("%s %s" % [str(spec.get("label", "")), _format_axis_value(current)], Vector2(legend_x, plot.end.y - 12), 9, color, 128)
        legend_x += 136.0
    if unit_label != "":
        _text(unit_label, Vector2(plot.end.x - 72, plot.position.y + 20), 8, MUTED, 60)

func _history_line_scaled(plot: Rect2, key: String, color: Color, max_value: float) -> Vector2:
    if _history.size() < 2:
        return Vector2(-1, -1)
    var max_t: float = max(float(_history[-1].get("time", 1.0)), 1.0)
    var prev := Vector2.ZERO
    var last := Vector2(-1, -1)
    for i in range(_history.size()):
        var item: Dictionary = _history[i]
        var x: float = plot.position.x + (float(item.get("time", 0.0)) / max_t) * plot.size.x
        var y: float = plot.end.y - (float(item.get(key, 0.0)) / max(max_value, 1.0)) * plot.size.y
        var point: Vector2 = Vector2(x, y)
        if i > 0:
            draw_line(prev, point, color, 2.0)
        prev = point
        last = point
    return last

func _draw_tank_type_trend_plot(plot: Rect2) -> void:
    _panel(plot, Color(0.020, 0.026, 0.027, 1.0), Color(0.18, 0.22, 0.21))
    _text("전차 종류별 전투력 추이", plot.position + Vector2(12, 20), 12, TEXT, plot.size.x - 24)
    if _history.size() < 2:
        _text("리플레이/통계 이력이 아직 없습니다.", plot.position + Vector2(14, 52), 10, MUTED, plot.size.x - 28)
        return
    var types := _current_tank_types_sorted()
    if types.is_empty():
        _text("전차 종류 데이터가 없습니다.", plot.position + Vector2(14, 52), 10, MUTED, plot.size.x - 28)
        return
    var inner := Rect2(plot.position + Vector2(52, 38), plot.size - Vector2(68, 72))
    draw_rect(inner, Color(0.012, 0.016, 0.017, 1.0), true)
    draw_rect(inner, Color(0.16, 0.20, 0.19), false, 1.0)
    var max_value := 1.0
    for item in _history:
        var red_s: Dictionary = item.get("red_tank_strengths", {})
        var blue_s: Dictionary = item.get("blue_tank_strengths", {})
        for t in types:
            max_value = max(max_value, float(red_s.get(str(t), {}).get("strength", 0.0)) if red_s.get(str(t), {}) is Dictionary else 0.0)
            max_value = max(max_value, float(blue_s.get(str(t), {}).get("strength", 0.0)) if blue_s.get(str(t), {}) is Dictionary else 0.0)
    max_value = _nice_axis_max(max_value)
    for i in range(5):
        var ratio := float(i) / 4.0
        var y := inner.end.y - inner.size.y * ratio
        draw_line(Vector2(inner.position.x, y), Vector2(inner.end.x, y), Color(0.30, 0.34, 0.32, 0.22), 1.0)
        _text(_format_axis_value(max_value * ratio), Vector2(plot.position.x + 10, y + 4), 8, MUTED, 38)
    var palette := [RED, BLUE, GOLD, GREEN, Color(0.9, 0.55, 0.25), Color(0.62, 0.55, 1.0)]
    var drawn := 0
    for t in types:
        if drawn >= 6:
            break
        var side := _tank_type_side_from_state(str(t))
        var color: Color = palette[drawn % palette.size()]
        if side == "red":
            color = color.lerp(RED, 0.45)
        elif side == "blue":
            color = color.lerp(BLUE, 0.45)
        var last_point := _history_tank_type_line(inner, str(t), side, color, max_value)
        if last_point.x >= 0.0:
            var current_strengths: Dictionary = _tank_type_strengths_from_units(_state.get("units", []))
            var current_side: Dictionary = current_strengths.get(side, {})
            var current = current_side.get(str(t), {})
            var current_strength: float = float(current.get("strength", 0.0)) if current is Dictionary else 0.0
            draw_circle(last_point, 4.0, color)
            _text(_format_axis_value(current_strength), last_point + Vector2(6, -5), 8, color, 48)
        _text(str(t), Vector2(inner.position.x + drawn * 86.0, plot.end.y - 12), 8, color, 80)
        drawn += 1

func _history_tank_type_line(plot: Rect2, tank_type: String, side: String, color: Color, max_value: float) -> Vector2:
    var max_t: float = max(float(_history[-1].get("time", 1.0)), 1.0)
    var prev := Vector2.ZERO
    var last := Vector2(-1, -1)
    for i in range(_history.size()):
        var item: Dictionary = _history[i]
        var bucket: Dictionary = item.get("%s_tank_strengths" % side, {})
        var entry = bucket.get(tank_type, {})
        var v: float = float(entry.get("strength", 0.0)) if entry is Dictionary else 0.0
        var x: float = plot.position.x + (float(item.get("time", 0.0)) / max_t) * plot.size.x
        var y: float = plot.end.y - (v / max(max_value, 1.0)) * plot.size.y
        var point: Vector2 = Vector2(x, y)
        if i > 0:
            draw_line(prev, point, color, 1.7)
        prev = point
        last = point
    return last

func _draw_tank_type_stats(r: Rect2, _summary: Dictionary) -> void:
    _panel(r, PANEL_DARK, LINE)
    _text("전차 종류별 잔존 전투력", r.position + Vector2(14, 24), 13, TEXT, r.size.x - 28)
    _text("현재 전투력을 전차 종류별로 합산하고 부대 수를 함께 표시합니다.", r.position + Vector2(14, 43), 9, MUTED, r.size.x - 28)
    var strengths := _tank_type_strengths_from_units(_state.get("units", []))
    var max_total: float = max(_max_tank_type_max(strengths), 1.0)
    var y := r.position.y + 72.0
    y = _draw_tank_type_side_bars(Rect2(r.position.x + 14, y, r.size.x - 28, r.size.y * 0.43), "Red", "red", strengths.get("red", {}), max_total, RED)
    y += 18.0
    _draw_tank_type_side_bars(Rect2(r.position.x + 14, y, r.size.x - 28, r.end.y - y - 54.0), "Blue", "blue", strengths.get("blue", {}), max_total, BLUE)
    if not _last_replay_meta.is_empty():
        _text("마지막 계산: %d프레임 / %0.0fms / 최종 t=%0.0f초" % [int(_last_replay_meta.get("frames", 0)), float(_last_replay_meta.get("compute_ms", 0.0)), float(_last_replay_meta.get("final_time_s", 0.0))], Vector2(r.position.x + 14, r.end.y - 24), 10, GOLD, r.size.x - 28)

func _draw_tank_type_side_bars(area: Rect2, title: String, side: String, data: Dictionary, max_total: float, color: Color) -> float:
    _text(title, area.position + Vector2(0, 14), 11, color, area.size.x)
    var types := data.keys()
    types.sort()
    var y := area.position.y + 34.0
    if types.is_empty():
        _text("전차 부대 없음", Vector2(area.position.x + 8, y + 12), 9, MUTED, area.size.x - 16)
        return y + 34.0
    var row_h := 31.0
    for t in types:
        if y + row_h > area.end.y:
            _text("...", Vector2(area.position.x + 8, y + 12), 9, MUTED, area.size.x - 16)
            break
        var entry: Dictionary = data.get(t, {})
        var strength := float(entry.get("strength", 0.0))
        var max_strength: float = max(float(entry.get("max", 0.0)), 0.01)
        var count := int(entry.get("count", 0))
        var label_w := 78.0
        var value_w := 122.0
        var bar := Rect2(area.position.x + label_w, y + 8.0, max(area.size.x - label_w - value_w - 12.0, 48.0), 10.0)
        _text(str(t), Vector2(area.position.x, y + 17.0), 9, TEXT, label_w - 4.0)
        draw_rect(bar, Color(0.12, 0.14, 0.13), true)
        draw_rect(Rect2(bar.position, Vector2(bar.size.x * clamp(strength / max_total, 0.0, 1.0), bar.size.y)), Color(color.r, color.g, color.b, 0.82), true)
        draw_rect(bar, Color(0.25, 0.30, 0.28), false, 1.0)
        var pct: float = 100.0 * strength / max_strength
        _text("%0.0f/%0.0f  %0.0f%%  n=%d" % [strength, max_strength, pct, count], Vector2(bar.end.x + 8.0, y + 17.0), 8, TEXT, value_w)
        y += row_h
    return y

func _tank_type_strengths_from_units(units: Array) -> Dictionary:
    var result := {"red": {}, "blue": {}}
    for unit in units:
        if typeof(unit) != TYPE_DICTIONARY:
            continue
        if str(unit.get("kind", "")) != "tank":
            continue
        var side := str(unit.get("side", ""))
        if side != "red" and side != "blue":
            continue
        var tank_type := str(unit.get("type", "tank"))
        var unit_max: float = max(float(unit.get("max_strength", 0.0)), float(unit.get("strength", 0.0)))
        _remember_tank_type(side, tank_type, unit_max)
        var side_map: Dictionary = result.get(side, {})
        var entry: Dictionary = side_map.get(tank_type, {"strength": 0.0, "max": 0.0, "count": 0})
        entry["strength"] = float(entry.get("strength", 0.0)) + float(unit.get("strength", 0.0))
        entry["max"] = float(entry.get("max", 0.0)) + unit_max
        entry["count"] = int(entry.get("count", 0)) + 1
        side_map[tank_type] = entry
        result[side] = side_map
    for side in ["red", "blue"]:
        var side_map: Dictionary = result.get(side, {})
        for tank_type in side_map.keys():
            var entry: Dictionary = side_map.get(tank_type, {})
            _remember_tank_type(side, str(tank_type), float(entry.get("max", 0.0)))
    return _ensure_known_tank_types(result)

func _remember_tank_type(side: String, tank_type: String, max_strength: float) -> void:
    if side != "red" and side != "blue":
        return
    if tank_type == "":
        return
    var side_known: Dictionary = _known_tank_type_max_by_side.get(side, {})
    side_known[tank_type] = max(float(side_known.get(tank_type, 0.0)), max_strength)
    _known_tank_type_max_by_side[side] = side_known

func _ensure_known_tank_types(strengths: Dictionary) -> Dictionary:
    for side in ["red", "blue"]:
        var side_map: Dictionary = strengths.get(side, {})
        var known: Dictionary = _known_tank_type_max_by_side.get(side, {})
        for tank_type in known.keys():
            if not side_map.has(tank_type):
                side_map[tank_type] = {"strength": 0.0, "max": float(known.get(tank_type, 0.0)), "count": 0}
            else:
                var entry: Dictionary = side_map.get(tank_type, {})
                entry["max"] = max(float(entry.get("max", 0.0)), float(known.get(tank_type, 0.0)))
                side_map[tank_type] = entry
        strengths[side] = side_map
    return strengths

func _max_tank_type_max(strengths: Dictionary) -> float:
    var out := 1.0
    for side in ["red", "blue"]:
        var data: Dictionary = strengths.get(side, {})
        for key in data.keys():
            var entry: Dictionary = data.get(key, {})
            out = max(out, float(entry.get("max", 0.0)))
    return out

func _current_tank_types_sorted() -> Array:
    var found := {}
    for side in ["red", "blue"]:
        var known: Dictionary = _known_tank_type_max_by_side.get(side, {})
        for tank_type in known.keys():
            found[str(tank_type)] = true
    for unit in _state.get("units", []):
        if typeof(unit) == TYPE_DICTIONARY and str(unit.get("kind", "")) == "tank":
            found[str(unit.get("type", "tank"))] = true
    var out := found.keys()
    out.sort()
    return out

func _tank_type_side_from_state(tank_type: String) -> String:
    for side in ["red", "blue"]:
        var known: Dictionary = _known_tank_type_max_by_side.get(side, {})
        if known.has(tank_type):
            return side
    for unit in _state.get("units", []):
        if typeof(unit) == TYPE_DICTIONARY and str(unit.get("kind", "")) == "tank" and str(unit.get("type", "")) == tank_type:
            return str(unit.get("side", ""))
    return _unit_type_side(tank_type)

func _nice_axis_max(value: float) -> float:
    if value <= 10.0:
        return ceil(value)
    var scale := pow(10.0, floor(log(value) / log(10.0)))
    var n := value / scale
    var nice := 1.0
    if n <= 2.0:
        nice = 2.0
    elif n <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * scale

func _format_axis_value(value: float) -> String:
    if value >= 1000.0:
        return "%0.1fk" % (value / 1000.0)
    if value >= 100.0:
        return "%0.0f" % value
    if value >= 10.0:
        return "%0.1f" % value
    return "%0.2f" % value

func _format_time_axis(seconds: float) -> String:
    if seconds >= 3600.0:
        return "%0.1fh" % (seconds / 3600.0)
    if seconds >= 60.0:
        return "%0.0fm" % (seconds / 60.0)
    return "%0.0fs" % seconds

func _draw_help_dialog() -> void:
    var r := Rect2(size * 0.18, size * 0.64)
    _panel(r, Color(0.035, 0.045, 0.048, 0.98), LINE)
    _text("조작 도움말", r.position + Vector2(18, 30), 18, TEXT, r.size.x - 90)
    _button(Rect2(r.end.x - 70, r.position.y + 14, 52, 28), "닫기", "dialog_close")
    var lines := [
        "· 2D/3D 버튼으로 작전지도와 3D 지형을 전환합니다.",
        "· 3D 보기: 가운데 드래그는 카메라 회전, Shift+가운데 드래그는 카메라 이동입니다.",
        "· 마우스 휠은 2D/3D 확대·축소, 2D에서는 가운데 드래그로 지도를 이동합니다.",
        "· 우클릭은 선택 부대의 이동명령을 backend로 전송합니다.",
        "· 파라미터 창에서 종료 조건과 Lanchester k 계수를 직접 조정할 수 있습니다.",
    ]
    var y := r.position.y + 74.0
    for line in lines:
        _text(str(line), Vector2(r.position.x + 24, y), 13, TEXT, r.size.x - 48)
        y += 30

func _view_label() -> String:
    return "3D 지형" if _view_mode == "3d" else "2D 작전지도"

func _tool_label() -> String:
    var labels := {
        "select": "선택",
        "move": "이동",
        "fire": "공격",
        "los": "LOS",
        "road": "도로",
        "rail": "철도",
        "elevation": "고도",
        "edit_position": "위치 편집",
    }
    return str(labels.get(_tool_mode, _tool_mode))

func _intent_label(intent: String) -> String:
    var labels := {
        "move": "이동",
        "attack": "공격",
        "defend": "방어",
        "retreat": "후퇴",
    }
    return str(labels.get(intent, intent))

func _set_unit_order(unit_id: String, intent: String, target_id: String = "") -> void:
    var order := {
        "intent": intent,
        "target_id": target_id,
        "time_s": float(_state.get("time_s", 0.0)),
    }
    _unit_orders[unit_id] = order
    queue_redraw()

func _add_current_order_to_queue() -> void:
    if _orders_locked():
        _status = "시뮬레이션 진행 중: 명령 대기열 변경 잠김"
        return
    var unit := _selected_unit()
    if unit.is_empty():
        _status = "대기열에 넣을 부대를 먼저 선택하세요"
        return
    var uid := str(unit.get("id", ""))
    var order: Dictionary = _unit_orders.get(uid, {"intent": _order_mode})
    var line := "%s - %s - %s" % [_clock_text(), str(unit.get("name", uid)), _intent_label(str(order.get("intent", _order_mode)))]
    _manual_queue.append(line)
    if _manual_queue.size() > 10:
        _manual_queue.pop_front()
    _status = "명령 큐 추가: %s" % line

func _setup_3d_viewport() -> void:
    _viewport_container_3d = SubViewportContainer.new()
    _viewport_container_3d.name = "TrueTerrain3D"
    _viewport_container_3d.stretch = false
    _viewport_container_3d.visible = false
    _viewport_container_3d.mouse_filter = Control.MOUSE_FILTER_IGNORE
    _viewport_container_3d.z_index = -10
    add_child(_viewport_container_3d)

    _viewport_3d = SubViewport.new()
    _viewport_3d.render_target_update_mode = SubViewport.UPDATE_DISABLED
    _viewport_3d.transparent_bg = false
    _viewport_3d.size = Vector2i(1280, 720)
    _viewport_container_3d.add_child(_viewport_3d)

    _terrain_root_3d = Node3D.new()
    _terrain_root_3d.name = "Battlefield3D"
    _viewport_3d.add_child(_terrain_root_3d)
    _combat_root_3d = Node3D.new()
    _combat_root_3d.name = "CombatEffects3D"
    _terrain_root_3d.add_child(_combat_root_3d)

    _camera_3d = Camera3D.new()
    _camera_3d.name = "TerrainCamera"
    _camera_3d.current = true
    _camera_3d.fov = 48.0
    _viewport_3d.add_child(_camera_3d)
    _apply_camera_3d()

    var light := DirectionalLight3D.new()
    light.name = "Sun"
    light.light_energy = 1.9
    light.rotation_degrees = Vector3(-48.0, 30.0, 0.0)
    _viewport_3d.add_child(light)

    var ambient := WorldEnvironment.new()
    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.10, 0.15, 0.17)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.58, 0.62, 0.56)
    env.ambient_light_energy = 0.7
    _camera_3d.environment = env
    var world := World3D.new()
    world.environment = env
    _viewport_3d.world_3d = world
    ambient.environment = env
    _viewport_3d.add_child(ambient)

func _sync_3d_viewport(r: Rect2) -> void:
    if not _viewport_container_3d:
        return
    # The custom Control draws the SubViewport texture itself so 2D overlays
    # can be clamped and layered consistently.  Keeping the container visible
    # as well can double-present the render target and produce block artifacts
    # on some Vulkan drivers during resize/zoom.
    _viewport_container_3d.visible = false
    _viewport_container_3d.position = r.position
    _viewport_container_3d.size = r.size
    var size_changed: bool = _last_3d_view_rect.size != r.size
    if _viewport_3d and size_changed:
        _viewport_3d.size = Vector2i(max(1, int(r.size.x)), max(1, int(r.size.y)))
    _last_3d_view_rect = r
    if not _terrain_mesh_ready and not _terrain_payload.is_empty():
        _build_terrain_mesh_3d()
    if _units_3d_dirty:
        _sync_units_3d()
    if _effects_3d_dirty:
        _sync_combat_effects_3d()
    _apply_camera_3d()

func _mark_3d_dirty(units: bool = true, effects: bool = true) -> void:
    if units:
        _units_3d_dirty = true
    if effects:
        _effects_3d_dirty = true

func _apply_camera_3d() -> void:
    if _camera_3d == null:
        return
    _camera_3d.projection = Camera3D.PROJECTION_PERSPECTIVE
    var yaw := deg_to_rad(_camera_yaw)
    var pitch := deg_to_rad(clamp(_camera_pitch, 12.0, 65.0))
    var horizontal_distance := _camera_distance * cos(pitch)
    _camera_height = _camera_distance * sin(pitch)
    var target := Vector3(_camera_pan.x, 0.0, _camera_pan.y)
    # The 3D terrain X axis is mirrored to match the 2D tactical map.  Mirror
    # the orbit X component as well so camera rotation feels like it turns
    # around the same map-space direction instead of rotating backwards.
    var offset := Vector3(-sin(yaw) * horizontal_distance, _camera_height, -cos(yaw) * horizontal_distance)
    _camera_3d.position = target + offset
    _camera_3d.look_at(target, Vector3.UP)

func _move_camera(action: String) -> void:
    var step := 14.0
    if action == "cam_left":
        _camera_pan.x -= step
    elif action == "cam_right":
        _camera_pan.x += step
    elif action == "cam_forward":
        _camera_pan.y -= step
    elif action == "cam_back":
        _camera_pan.y += step
    elif action == "cam_zoom_in":
        _camera_distance = max(95.0, _camera_distance - 25.0)
    elif action == "cam_zoom_out":
        _camera_distance = min(480.0, _camera_distance + 25.0)
    elif action == "cam_rotate_left":
        _camera_yaw -= 18.0
    elif action == "cam_rotate_right":
        _camera_yaw += 18.0
    elif action == "cam_reset":
        _camera_pan = Vector2.ZERO
        _camera_yaw = 0.0
        _camera_distance = 230.0
        _camera_pitch = 24.0
    _apply_camera_3d()
    _status = "3D 카메라 yaw %0.0f도, pitch %0.0f도, 거리 %0.0f" % [_camera_yaw, _camera_pitch, _camera_distance]

func _build_terrain_mesh_3d() -> void:
    if _terrain_root_3d == null:
        return
    _terrain_cells = _terrain_payload.get("cells", [])
    if _terrain_cells.is_empty():
        return
    for child in _terrain_root_3d.get_children():
        child.queue_free()
    _unit_meshes_3d.clear()
    _combat_root_3d = Node3D.new()
    _combat_root_3d.name = "CombatEffects3D"
    _terrain_root_3d.add_child(_combat_root_3d)

    var vertices := PackedVector3Array()
    var colors := PackedColorArray()
    var uvs := PackedVector2Array()
    var index_by_cell := {}
    var bounds: Array = _terrain_payload.get("bounds", [0.0, 0.0, 1.0, 1.0])
    var min_x := float(bounds[0])
    var min_y := float(bounds[1])
    var max_x := float(bounds[2])
    var max_y := float(bounds[3])
    for cell in _terrain_cells:
        var p := _terrain_cell_to_3d(cell)
        var x := float(cell.get("x", min_x))
        var y := float(cell.get("y", min_y))
        vertices.append(p)
        colors.append(_terrain_color(cell))
        uvs.append(Vector2(clamp((x - min_x) / max(max_x - min_x, 1.0), 0.0, 1.0), clamp(1.0 - ((y - min_y) / max(max_y - min_y, 1.0)), 0.0, 1.0)))
        index_by_cell["%d:%d" % [int(cell.get("row", 0)), int(cell.get("col", 0))]] = vertices.size() - 1

    var indices := PackedInt32Array()
    var rows := int(_terrain_payload.get("rows", 0))
    var cols := int(_terrain_payload.get("cols", 0))
    for row in range(1, rows):
        for col in range(1, cols):
            var a_key := "%d:%d" % [row, col]
            var b_key := "%d:%d" % [row, col + 1]
            var c_key := "%d:%d" % [row + 1, col]
            var d_key := "%d:%d" % [row + 1, col + 1]
            if index_by_cell.has(a_key) and index_by_cell.has(b_key) and index_by_cell.has(c_key) and index_by_cell.has(d_key):
                var a := int(index_by_cell[a_key])
                var b := int(index_by_cell[b_key])
                var c := int(index_by_cell[c_key])
                var d := int(index_by_cell[d_key])
                indices.append_array([a, c, b, b, c, d])

    var arrays := []
    arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX] = vertices
    arrays[Mesh.ARRAY_COLOR] = colors
    arrays[Mesh.ARRAY_TEX_UV] = uvs
    arrays[Mesh.ARRAY_INDEX] = indices
    var mesh := ArrayMesh.new()
    mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

    var material := StandardMaterial3D.new()
    material.vertex_color_use_as_albedo = _actual_map_texture == null
    if _actual_map_texture != null:
        material.albedo_texture = _actual_map_texture
        material.albedo_color = Color(0.92, 0.92, 0.88, 1.0)
    material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    material.roughness = 0.92
    material.cull_mode = BaseMaterial3D.CULL_DISABLED
    var terrain := MeshInstance3D.new()
    terrain.name = "DEM Terrain Mesh"
    terrain.mesh = mesh
    terrain.material_override = material
    _terrain_root_3d.add_child(terrain)
    _add_terrain_base_3d()
    _add_playbox_boundary_3d()
    _terrain_mesh_ready = true
    _sync_units_3d()
    _sync_combat_effects_3d()

func _add_terrain_base_3d() -> void:
    var bounds: Array = _terrain_payload.get("bounds", [0.0, 0.0, 1.0, 1.0])
    var plane := MeshInstance3D.new()
    plane.name = "terrain_dark_base"
    var box := BoxMesh.new()
    var w: float = max((float(bounds[2]) - float(bounds[0])) * TERRAIN_XZ_SCALE * 1.45, 1.0)
    var d: float = max((float(bounds[3]) - float(bounds[1])) * TERRAIN_XZ_SCALE * 1.45, 1.0)
    box.size = Vector3(w, 0.18, d)
    plane.mesh = box
    plane.position = Vector3(0.0, -0.35, 0.0)
    var mat := StandardMaterial3D.new()
    mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.albedo_color = Color(0.055, 0.090, 0.095)
    plane.material_override = mat
    _terrain_root_3d.add_child(plane)

func _terrain_cell_to_3d(cell: Dictionary) -> Vector3:
    var bounds: Array = _terrain_payload.get("bounds", [0.0, 0.0, 1.0, 1.0])
    var mid_x := (float(bounds[0]) + float(bounds[2])) * 0.5
    var mid_y := (float(bounds[1]) + float(bounds[3])) * 0.5
    var min_e := float(_terrain_payload.get("min_elevation_m", 0.0))
    var sx := TERRAIN_XZ_SCALE
    var sy := TERRAIN_ELEV_SCALE
    return Vector3((mid_x - float(cell.get("x", 0.0))) * sx, (float(cell.get("elevation_m", min_e)) - min_e) * sy, (float(cell.get("y", 0.0)) - mid_y) * sx)

func _terrain_color(cell: Dictionary) -> Color:
    if bool(cell.get("water", false)):
        return Color(0.08, 0.22, 0.34)
    if bool(cell.get("road", false)):
        return Color(0.58, 0.50, 0.33)
    if bool(cell.get("rail", false)):
        return Color(0.18, 0.17, 0.15)
    var elev_min := float(_terrain_payload.get("min_elevation_m", 0.0))
    var elev_max := float(_terrain_payload.get("max_elevation_m", elev_min + 1.0))
    var t: float = clamp((float(cell.get("elevation_m", elev_min)) - elev_min) / max(elev_max - elev_min, 0.1), 0.0, 1.0)
    var slope := float(cell.get("slope", cell.get("slope_deg", 0.0)))
    var rough := float(cell.get("roughness", 0.0))
    var c := Color(0.12 + t * 0.54, 0.28 + t * 0.32, 0.11 + t * 0.08)
    c = c.lerp(Color(0.78, 0.62, 0.30), clamp(slope / 28.0, 0.0, 0.34))
    c = c.darkened(clamp(rough * 0.12, 0.0, 0.18))
    return c

func _sync_units_3d() -> void:
    if _terrain_root_3d == null or not _state.has("units"):
        return
    var live := {}
    for unit in _state.get("units", []):
        var uid := str(unit.get("id", ""))
        if uid == "":
            continue
        live[uid] = true
        var mesh: MeshInstance3D = _unit_meshes_3d.get(uid, null)
        if mesh == null:
            mesh = MeshInstance3D.new()
            mesh.name = "unit_%s" % uid
            var box := BoxMesh.new()
            var kind := str(unit.get("kind", "tank"))
            if kind == "artillery":
                box.size = Vector3(2.0, 0.65, 0.9)
            elif kind == "recon":
                box.size = Vector3(1.15, 0.52, 0.75)
            elif kind == "command_post":
                box.size = Vector3(1.8, 0.85, 1.3)
            else:
                box.size = Vector3(1.55, 0.65, 0.95)
            mesh.mesh = box
            var mat := StandardMaterial3D.new()
            mat.albedo_color = _unit_color_3d(unit)
            mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
            mat.emission_enabled = uid == _selected_unit_id
            mat.emission = GOLD
            mat.emission_energy_multiplier = 0.35
            mesh.material_override = mat
            _add_3d_flag_children(mesh)
            _terrain_root_3d.add_child(mesh)
            _unit_meshes_3d[uid] = mesh
        mesh.position = _unit_to_3d(unit)
        var mat2 := mesh.material_override as StandardMaterial3D
        if mat2:
            mat2.albedo_color = _unit_color_3d(unit)
            mat2.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
            mat2.emission_enabled = uid == _selected_unit_id
        _update_3d_flag(mesh, unit)
    for uid in _unit_meshes_3d.keys():
        if not live.has(uid):
            var old: MeshInstance3D = _unit_meshes_3d[uid]
            if old:
                old.queue_free()
            _unit_meshes_3d.erase(uid)
    _units_3d_dirty = false

func _unit_to_3d(unit: Dictionary) -> Vector3:
    return _world_point_to_3d(float(unit.get("x", 0.0)), float(unit.get("y", 0.0)), 1.3)

func _world_point_to_3d(x: float, y: float, lift: float = 0.0) -> Vector3:
    var synthetic := {"x": x, "y": y, "elevation_m": _terrain_height_at(x, y)}
    var p := _terrain_cell_to_3d(synthetic)
    p.y += lift
    return p

func _unit_color_3d(unit: Dictionary) -> Color:
    var base := RED if str(unit.get("side", "")) == "red" else BLUE
    var bounds: Array = _terrain_payload.get("bounds", _state.get("terrain", {}).get("bounds", [0.0, 0.0, 1.0, 1.0]))
    var mid_x := (float(bounds[0]) + float(bounds[2])) * 0.5
    var flank: float = clamp(abs(float(unit.get("x", mid_x)) - mid_x) / max(float(bounds[2]) - float(bounds[0]), 1.0), 0.0, 0.5)
    var elev_min := float(_terrain_payload.get("min_elevation_m", 0.0))
    var elev_max := float(_terrain_payload.get("max_elevation_m", elev_min + 1.0))
    var elev := float(unit.get("elevation_m", _terrain_height_at(float(unit.get("x", 0.0)), float(unit.get("y", 0.0)))))
    var e_t: float = clamp((elev - elev_min) / max(elev_max - elev_min, 0.1), 0.0, 1.0)
    var c := base.lerp(Color(0.95, 0.78, 0.34), e_t * 0.18).lightened(flank * 0.12)
    c.a = _unit_display_alpha(unit)
    return c

func _add_3d_flag_children(mesh: MeshInstance3D) -> void:
    var pole := MeshInstance3D.new()
    pole.name = "flag_pole"
    var pole_box := BoxMesh.new()
    pole_box.size = Vector3(0.08, 3.3, 0.08)
    pole.mesh = pole_box
    var pole_mat := StandardMaterial3D.new()
    pole_mat.albedo_color = Color(0.08, 0.08, 0.06)
    pole.material_override = pole_mat
    pole.position = Vector3(0.0, 2.1, 0.0)
    mesh.add_child(pole)

    var flag := MeshInstance3D.new()
    flag.name = "strength_flag"
    var flag_box := BoxMesh.new()
    flag_box.size = Vector3(1.8, 0.62, 0.08)
    flag.mesh = flag_box
    var flag_mat := StandardMaterial3D.new()
    flag_mat.albedo_color = GREEN
    flag_mat.emission_enabled = true
    flag_mat.emission = GREEN
    flag_mat.emission_energy_multiplier = 0.12
    flag.material_override = flag_mat
    mesh.add_child(flag)

    var label := Label3D.new()
    label.name = "unit_label"
    label.visible = false
    label.pixel_size = 0.032
    label.fixed_size = true
    label.no_depth_test = true
    label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
    label.outline_size = 8
    label.modulate = TEXT
    label.position = Vector3(0.0, 4.55, 0.0)
    mesh.add_child(label)

func _update_3d_flag(mesh: MeshInstance3D, unit: Dictionary) -> void:
    var strength: float = clamp(float(unit.get("normalized_strength", 1.0)), 0.0, 1.0)
    var flag := mesh.get_node_or_null("strength_flag") as MeshInstance3D
    if flag:
        var flag_box := flag.mesh as BoxMesh
        if flag_box:
            flag_box.size = Vector3(2.25, 0.72, 0.08)
            flag.position = Vector3(1.26, 3.85, 0.0)
        var mat := flag.material_override as StandardMaterial3D
        if mat:
            var side_color := RED if str(unit.get("side", "")) == "red" else BLUE
            var c := side_color.lerp(Color(0.08, 0.08, 0.07), 1.0 - strength)
            var alpha: float = max(0.34, _unit_display_alpha(unit))
            mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
            mat.albedo_color = Color(c.r, c.g, c.b, 0.86 * alpha)
            mat.emission = c
    var label := mesh.get_node_or_null("unit_label") as Label3D
    if label:
        var echelon := _unit_echelon(unit)
        var prefix := "RES " if _unit_is_pending_reserve(unit) else ""
        label.text = "%s %s%s\n%s %0.0f%%" % [echelon, prefix, str(unit.get("name", "unit")), str(unit.get("type", "")), strength * 100.0]
        var label_alpha: float = max(0.46, _unit_display_alpha(unit))
        label.modulate = Color(TEXT.r, TEXT.g, TEXT.b, label_alpha)

func _sync_combat_effects_3d() -> void:
    if _combat_root_3d == null or not _state.has("units"):
        return
    for child in _combat_root_3d.get_children():
        child.queue_free()
    for eg in _engagements:
        var a: Dictionary = eg.get("attacker", {})
        var b: Dictionary = eg.get("defender", {})
        var au := _unit_by_id(str(a.get("id", "")))
        var bu := _unit_by_id(str(b.get("id", "")))
        if au.is_empty() or bu.is_empty():
            continue
        _add_line_mesh_to(_combat_root_3d, [_unit_to_3d(au) + Vector3(0, 1.2, 0), _unit_to_3d(bu) + Vector3(0, 1.2, 0)], Color(1.0, 0.42, 0.12, 0.82), "engagement_line")
    var shell_items: Array = _state.get("shells", [])
    var shell_start: int = max(0, shell_items.size() - 24)
    for shell in shell_items.slice(shell_start, shell_items.size()):
        var start: Array = shell.get("start", [])
        var target: Array = shell.get("target", [])
        if start.size() >= 2 and target.size() >= 2:
            _add_shell_arc_3d(
                _combat_root_3d,
                Vector2(float(start[0]), float(start[1])),
                Vector2(float(target[0]), float(target[1])),
                _shell_progress(shell),
                shell
            )
    var drawn := 0
    var selected_id := _selected_unit_id
    for unit in _state.get("units", []):
        if drawn >= 1:
            break
        if str(unit.get("kind", "")) != "artillery":
            continue
        if selected_id != "" and str(unit.get("id", "")) != selected_id:
            continue
        var enemy := _nearest_enemy_unit_for(unit)
        if enemy.is_empty():
            continue
        _add_line_mesh_to(_combat_root_3d, _arc_points_3d(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), Vector2(float(enemy.get("x", 0.0)), float(enemy.get("y", 0.0))), 18.0), Color(1.0, 0.72, 0.18, 0.28), "planned_arc")
        drawn += 1
    var selected := _selected_unit()
    if not selected.is_empty():
        var route := [_unit_to_3d(selected) + Vector3(0, 1.6, 0)]
        for wp in selected.get("waypoints", []):
            if typeof(wp) == TYPE_ARRAY and wp.size() >= 2:
                route.append(_world_point_to_3d(float(wp[0]), float(wp[1]), 1.6))
        if route.size() >= 2:
            _add_line_mesh_to(_combat_root_3d, route, Color(GOLD.r, GOLD.g, GOLD.b, 0.92), "selected_waypoints")
    _effects_3d_dirty = false

func _arc_points_3d(start: Vector2, target: Vector2, height: float) -> Array:
    var points := []
    var steps := 14
    for i in range(steps + 1):
        var t := float(i) / float(steps)
        var xy := start.lerp(target, t)
        var p := _world_point_to_3d(xy.x, xy.y, 2.0)
        p.y += sin(t * PI) * height
        points.append(p)
    return points

func _add_shell_arc_3d(parent: Node3D, start: Vector2, target: Vector2, progress: float, shell: Dictionary) -> void:
    if parent == null:
        return
    var distance_m := start.distance_to(target)
    var height: float = clamp(distance_m * TERRAIN_XZ_SCALE * 0.38, 18.0, 44.0)
    var arc_points := _arc_points_3d(start, target, height)
    var shell_color := Color(1.0, 0.78, 0.16, 0.96)
    var collapsed := _shell_is_visual_instant(shell)
    if not collapsed:
        _add_line_mesh_to(parent, arc_points, Color(1.0, 0.55, 0.08, 0.26), "shell_arc_glow")
        _add_line_mesh_to(parent, arc_points, Color(1.0, 0.82, 0.22, 0.82), "shell_arc_path")
        var traveled := _partial_polyline_points_3d(arc_points, progress)
        if traveled.size() >= 2:
            _add_line_mesh_to(parent, traveled, Color(1.0, 0.96, 0.52, 1.0), "shell_arc_traveled")
        var shell_pos := _point_on_polyline_3d(arc_points, progress)
        _add_shell_marker_3d(parent, shell_pos, shell_color, "shell_marker")
    var impact_radius: float = clamp(float(shell.get("radius_m", 120.0)) * TERRAIN_XZ_SCALE, 1.8, 10.0)
    _add_impact_disc_3d(parent, _world_point_to_3d(target.x, target.y, 0.18), impact_radius, Color(1.0, 0.44, 0.06, 0.40 if collapsed else 0.22), "shell_impact_disc")

func _point_on_polyline_3d(points: Array, ratio: float) -> Vector3:
    if points.is_empty():
        return Vector3.ZERO
    if points.size() == 1:
        return points[0]
    var t: float = clamp(ratio, 0.0, 1.0) * float(points.size() - 1)
    var i: int = clamp(int(floor(t)), 0, points.size() - 2)
    var a: Vector3 = points[i]
    var b: Vector3 = points[i + 1]
    return a.lerp(b, t - float(i))

func _partial_polyline_points_3d(points: Array, ratio: float) -> Array:
    var out := []
    if points.size() < 2:
        return out
    var until_t: float = clamp(ratio, 0.0, 1.0)
    if until_t <= 0.0:
        return out
    out.append(points[0])
    for i in range(points.size() - 1):
        var seg_t0 := float(i) / float(points.size() - 1)
        var seg_t1 := float(i + 1) / float(points.size() - 1)
        if seg_t1 <= until_t:
            out.append(points[i + 1])
            continue
        if seg_t0 < until_t:
            var a: Vector3 = points[i]
            var b: Vector3 = points[i + 1]
            var local_t: float = clamp((until_t - seg_t0) / max(seg_t1 - seg_t0, 0.0001), 0.0, 1.0)
            out.append(a.lerp(b, local_t))
        break
    return out

func _add_shell_marker_3d(parent: Node3D, pos: Vector3, color: Color, name: String) -> void:
    var marker := MeshInstance3D.new()
    marker.name = name
    var sphere := SphereMesh.new()
    sphere.radius = 0.62
    sphere.height = 1.24
    sphere.radial_segments = 16
    sphere.rings = 8
    marker.mesh = sphere
    marker.position = pos
    marker.material_override = _combat_material_3d(color, 1.2, true)
    parent.add_child(marker)
    var light := OmniLight3D.new()
    light.name = "%s_light" % name
    light.light_color = Color(color.r, color.g, color.b)
    light.light_energy = 0.55
    light.omni_range = 9.0
    marker.add_child(light)

func _add_impact_disc_3d(parent: Node3D, pos: Vector3, radius: float, color: Color, name: String) -> void:
    var disc := MeshInstance3D.new()
    disc.name = name
    var cylinder := CylinderMesh.new()
    cylinder.top_radius = radius
    cylinder.bottom_radius = radius
    cylinder.height = 0.08
    cylinder.radial_segments = 48
    disc.mesh = cylinder
    disc.position = pos
    disc.material_override = _combat_material_3d(color, 0.35, true)
    parent.add_child(disc)

func _add_playbox_boundary_3d() -> void:
    var bounds: Array = _terrain_payload.get("bounds", [0.0, 0.0, 1.0, 1.0])
    var min_x := float(bounds[0])
    var min_y := float(bounds[1])
    var max_x := float(bounds[2])
    var max_y := float(bounds[3])
    var pts := [
        _world_point_to_3d(min_x, min_y, 0.55),
        _world_point_to_3d(max_x, min_y, 0.55),
        _world_point_to_3d(max_x, max_y, 0.55),
        _world_point_to_3d(min_x, max_y, 0.55),
        _world_point_to_3d(min_x, min_y, 0.55),
    ]
    _add_line_mesh_to(_terrain_root_3d, pts, Color(0.96, 0.84, 0.34, 0.95), "playbox_boundary")

func _add_line_mesh_to(parent: Node3D, points: Array, color: Color, name: String) -> void:
    if parent == null or points.size() < 2:
        return
    var immediate := ImmediateMesh.new()
    immediate.surface_begin(Mesh.PRIMITIVE_LINES)
    for i in range(points.size() - 1):
        immediate.surface_add_vertex(points[i])
        immediate.surface_add_vertex(points[i + 1])
    immediate.surface_end()
    var mi := MeshInstance3D.new()
    mi.name = name
    mi.mesh = immediate
    mi.material_override = _combat_material_3d(color, 0.45, false)
    parent.add_child(mi)

func _combat_material_3d(color: Color, emission_energy: float = 0.35, no_depth: bool = false) -> StandardMaterial3D:
    var mat := StandardMaterial3D.new()
    mat.albedo_color = color
    mat.emission_enabled = true
    mat.emission = Color(color.r, color.g, color.b)
    mat.emission_energy_multiplier = emission_energy
    mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
    mat.cull_mode = BaseMaterial3D.CULL_DISABLED
    mat.no_depth_test = no_depth
    return mat

func _unit_by_id(unit_id: String) -> Dictionary:
    for unit in _state.get("units", []):
        if str(unit.get("id", "")) == unit_id:
            return unit
    return {}

func _nearest_enemy_unit_for(source: Dictionary) -> Dictionary:
    var best := {}
    var best_d := INF
    var sx := float(source.get("x", 0.0))
    var sy := float(source.get("y", 0.0))
    for unit in _state.get("units", []):
        if str(unit.get("side", "")) == str(source.get("side", "")):
            continue
        if str(unit.get("kind", "")) == "command_post":
            continue
        var dx := float(unit.get("x", 0.0)) - sx
        var dy := float(unit.get("y", 0.0)) - sy
        var d := dx * dx + dy * dy
        if d < best_d:
            best_d = d
            best = unit
    return best

func _terrain_height_at(x: float, y: float) -> float:
    if _terrain_cells.is_empty():
        return float(_terrain_payload.get("min_elevation_m", 0.0))
    var best: Dictionary = _terrain_cells[0]
    var best_d: float = INF
    for cell in _terrain_cells:
        var dx := float(cell.get("x", 0.0)) - x
        var dy := float(cell.get("y", 0.0)) - y
        var d := dx * dx + dy * dy
        if d < best_d:
            best_d = d
            best = cell
    return float(best.get("elevation_m", 0.0))

func _draw_battlefield_3d(r: Rect2) -> void:
    draw_rect(r, Color(0.05, 0.08, 0.09), true)
    if _viewport_3d and _terrain_mesh_ready:
        var tex: Texture2D = _viewport_3d.get_texture()
        if tex:
            draw_texture_rect(tex, r, false)
    else:
        _text("3D 지형 데이터를 준비 중입니다...", r.position + Vector2(24, 42), 16, GOLD, r.size.x - 48)
    draw_rect(r, Color(0.0, 0.0, 0.0, 0.08), false, 2.0)
    var cell_count := _terrain_cells.size()
    _text("3D 지형 / 실제 지도 전장", r.position + Vector2(18, 28), 15, GOLD, 360)
    _text("휠 확대/축소 · 가운데 드래그 회전 · Shift+가운데 드래그 이동 · playbox DEM 기반 지형", r.position + Vector2(18, 50), 11, TEXT, r.size.x - 36)
    _text("DEM 셀 %d개 · 거리 %0.0f · yaw %0.0f도 · pitch %0.0f도 · 3D에서도 교전/포병 마커 표시" % [cell_count, _camera_distance, _camera_yaw, _camera_pitch], r.position + Vector2(18, 72), 10, MUTED, r.size.x - 36)
    if not _terrain_mesh_ready:
        return
    if not _state.has("units"):
        _text("Waiting for Python backend", r.position + Vector2(24, 104), 14, GOLD)
        return
    _draw_3d_unit_overlays(r)
    return


func _draw_3d_unit_overlays(r: Rect2) -> void:
    var units: Array = _state.get("units", [])
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
    _draw_contact_lines_3d(units, bounds, r)
    _draw_fire_mission_lines_3d(units, bounds, r)
    _draw_shell_lines_3d(units, bounds, r)
    for unit in units:
        var projected := _world_to_screen_3d_projected(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), r)
        if not bool(projected.get("visible", false)):
            continue
        var p: Vector2 = projected.get("point", Vector2.ZERO)
        var base_color := RED if str(unit.get("side", "")) == "red" else BLUE
        var alpha := _unit_display_alpha(unit)
        var color := _with_alpha(base_color, alpha)
        var selected := str(unit.get("id", "")) == _selected_unit_id
        if selected:
            _draw_3d_waypoint_overlay(unit, bounds, r)
        var pole_top := p + Vector2(0, -58)
        draw_line(p + Vector2(0, -8), pole_top, Color(0.05, 0.05, 0.04, 0.95 * max(alpha, 0.34)), 2.0)
        var flag_size := Vector2(118, 42) if selected else Vector2(108, 38)
        var flag := Rect2(pole_top + Vector2(-flag_size.x * 0.5, -flag_size.y - 4), flag_size)
        flag = _clamp_rect_to_rect(flag, r.grow(-4.0))
        draw_rect(flag, Color(0.02, 0.025, 0.022, 0.88 * max(alpha, 0.34)), true)
        draw_rect(flag, GOLD if selected else color, false, 1.4)
        var ratio: float = clamp(float(unit.get("strength", 0.0)) / max(float(unit.get("max_strength", 1.0)), 0.01), 0.0, 1.0)
        _unit_glyph(flag.position + Vector2(15, 16), str(unit.get("kind", "tank")), color, 0.68, ratio)
        var text_x := flag.position.x + 32
        var prefix := "RES " if _unit_is_pending_reserve(unit) else ""
        _text(prefix + str(unit.get("name", "unit")), Vector2(text_x, flag.position.y + 15), 9, Color(TEXT.r, TEXT.g, TEXT.b, max(0.52, alpha)), flag.size.x - 38)
        _text("%s  %.0f  %0.0f%%" % [_type_short(str(unit.get("type", ""))), float(unit.get("strength", 0.0)), ratio * 100.0], Vector2(text_x, flag.position.y + 30), 8, Color(MUTED.r, MUTED.g, MUTED.b, max(0.44, alpha)), flag.size.x - 38)

func _draw_3d_waypoint_overlay(unit: Dictionary, bounds: Array, r: Rect2) -> void:
    var current_projected := _world_to_screen_3d_projected(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), r)
    if not bool(current_projected.get("visible", false)):
        return
    var current: Vector2 = current_projected.get("point", Vector2.ZERO)
    var idx := 1
    for wp in unit.get("waypoints", []):
        if typeof(wp) == TYPE_ARRAY and wp.size() >= 2:
            var next_projected := _world_to_screen_3d_projected(Vector2(float(wp[0]), float(wp[1])), r)
            if not bool(next_projected.get("visible", false)):
                current = _clamp_point_to_rect(_world_to_screen_3d(Vector2(float(wp[0]), float(wp[1])), bounds, r), r)
                idx += 1
                continue
            var p: Vector2 = next_projected.get("point", Vector2.ZERO)
            draw_line(_clamp_point_to_rect(current, r), _clamp_point_to_rect(p, r), GOLD, 2.2)
            draw_circle(p, 6.0, GOLD)
            _text(str(idx), _clamp_point_to_rect(p + Vector2(7, -6), r.grow(-10.0)), 9, TEXT)
            current = p
            idx += 1

func _draw_camera_controls(r: Rect2) -> void:
    var panel := Rect2(r.end.x - 248, r.position.y + 12, 232, 118)
    _panel(panel, Color(0.025, 0.035, 0.038, 0.88), LINE)
    _text("3D camera", panel.position + Vector2(12, 20), 12, TEXT, panel.size.x - 24)
    _button(Rect2(panel.position + Vector2(78, 30), Vector2(40, 24)), "Fwd", "cam_forward")
    _button(Rect2(panel.position + Vector2(34, 58), Vector2(40, 24)), "Left", "cam_left")
    _button(Rect2(panel.position + Vector2(78, 58), Vector2(40, 24)), "Back", "cam_back")
    _button(Rect2(panel.position + Vector2(122, 58), Vector2(40, 24)), "Right", "cam_right")
    _button(Rect2(panel.position + Vector2(170, 30), Vector2(24, 24)), "+", "cam_zoom_in")
    _button(Rect2(panel.position + Vector2(198, 30), Vector2(24, 24)), "-", "cam_zoom_out")
    _button(Rect2(panel.position + Vector2(170, 58), Vector2(24, 24)), "-", "cam_rotate_left")
    _button(Rect2(panel.position + Vector2(198, 58), Vector2(24, 24)), "+", "cam_rotate_right")
    _button(Rect2(panel.position + Vector2(34, 88), Vector2(188, 22)), "Reset camera", "cam_reset")


func _draw_2d_zoom_controls(r: Rect2) -> void:
    var panel := Rect2(r.end.x - 166.0, r.position.y + 12.0, 150.0, 88.0)
    _panel(panel, Color(0.025, 0.035, 0.038, 0.88), LINE)
    _text("2D", panel.position + Vector2(12, 20), 12, TEXT, panel.size.x - 24)
    _button(Rect2(panel.position + Vector2(12, 34), Vector2(32, 24)), "+", "map_zoom_in")
    _button(Rect2(panel.position + Vector2(50, 34), Vector2(32, 24)), "-", "map_zoom_out")
    _button(Rect2(panel.position + Vector2(88, 34), Vector2(50, 24)), "100%", "map_zoom_reset")
    _text("휠 확대/축소 · 가운데 드래그 이동", panel.position + Vector2(12, 74), 8, MUTED, panel.size.x - 24)

func _map_zoom_by(factor: float, focal_screen: Vector2 = Vector2(-INF, -INF)) -> void:
    var units: Array = _state.get("units", [])
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
    var has_focal := is_finite(focal_screen.x) and is_finite(focal_screen.y) and _map_rect.has_point(focal_screen)
    var focal_world := _screen_to_world(focal_screen, bounds) if has_focal else Vector2.ZERO
    _map_zoom = clamp(_map_zoom * factor, 0.65, 4.0)
    if has_focal:
        _focus_map_on_screen_world(focal_world, focal_screen, bounds)
    if is_equal_approx(_map_zoom, 1.0):
        _map_pan = Vector2.ZERO
    else:
        _clamp_map_pan(bounds)
    _status = "2D 배율 %d%%" % int(round(_map_zoom * 100.0))

func _focus_map_on_screen_world(focal_world: Vector2, focal_screen: Vector2, bounds: Array) -> void:
    var pad := 26.0
    var min_x := float(bounds[0])
    var min_y := float(bounds[1])
    var max_x := float(bounds[2])
    var max_y := float(bounds[3])
    var base_center := Vector2((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)
    var half: Vector2 = Vector2(max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)) * 0.5 / max(_map_zoom, 0.1)
    var draw_w: float = max(_map_rect.size.x - pad * 2.0, 1.0)
    var draw_h: float = max(_map_rect.size.y - pad * 2.0, 1.0)
    var tx: float = clamp((focal_screen.x - _map_rect.position.x - pad) / draw_w, 0.0, 1.0)
    var ty_world: float = clamp((_map_rect.position.y + _map_rect.size.y - pad - focal_screen.y) / draw_h, 0.0, 1.0)
    var desired_center := Vector2(focal_world.x + (0.5 - tx) * half.x * 2.0, focal_world.y + (0.5 - ty_world) * half.y * 2.0)
    _map_pan = desired_center - base_center
    _clamp_map_pan(bounds)

func _map_pan_pixels(delta: Vector2) -> void:
    var units: Array = _state.get("units", [])
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
    var view_bounds := _map_view_bounds(bounds)
    var world_w: float = max(float(view_bounds[2]) - float(view_bounds[0]), 1.0)
    var world_h: float = max(float(view_bounds[3]) - float(view_bounds[1]), 1.0)
    var pad := 26.0
    _map_pan.x -= delta.x / max(_map_rect.size.x - pad * 2.0, 1.0) * world_w
    _map_pan.y += delta.y / max(_map_rect.size.y - pad * 2.0, 1.0) * world_h
    _clamp_map_pan(bounds)

func _clamp_map_pan(bounds: Array) -> void:
    var min_x := float(bounds[0])
    var min_y := float(bounds[1])
    var max_x := float(bounds[2])
    var max_y := float(bounds[3])
    var world_w: float = max(max_x - min_x, 1.0)
    var world_h: float = max(max_y - min_y, 1.0)
    var limit_x := world_w * 0.45
    var limit_y := world_h * 0.45
    _map_pan.x = clamp(_map_pan.x, -limit_x, limit_x)
    _map_pan.y = clamp(_map_pan.y, -limit_y, limit_y)

func _map_view_bounds(bounds: Array) -> Array:
    var min_x := float(bounds[0])
    var min_y := float(bounds[1])
    var max_x := float(bounds[2])
    var max_y := float(bounds[3])
    var center := Vector2((min_x + max_x) * 0.5, (min_y + max_y) * 0.5) + _map_pan
    var half: Vector2 = Vector2(max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)) * 0.5 / max(_map_zoom, 0.1)
    return [center.x - half.x, center.y - half.y, center.x + half.x, center.y + half.y]

func _project_3d_norm(norm: Vector2, r: Rect2) -> Vector2:
    var depth: float = clamp(norm.y, 0.0, 1.0)
    var horizon_y := r.position.y + r.size.y * 0.34
    var ground_bottom := r.end.y - 18.0
    var y: float = lerp(horizon_y, ground_bottom, pow(depth, 0.72))
    var lane_w: float = lerp(r.size.x * 0.25, r.size.x * 0.86, depth)
    var x: float = r.position.x + r.size.x * 0.5 + (norm.x - 0.5) * lane_w
    return Vector2(x, y)


func _world_to_screen_3d(point: Vector2, bounds: Array, r: Rect2 = Rect2()) -> Vector2:
    var target := r if r.size.x > 0.0 else _map_rect
    if _camera_3d != null and _viewport_3d != null:
        var world3 := _world_point_to_3d(point.x, point.y, 2.2)
        if not _camera_3d.is_position_behind(world3):
            var p := _camera_3d.unproject_position(world3)
            if p.x >= -80.0 and p.y >= -80.0 and p.x <= float(_viewport_3d.size.x) + 80.0 and p.y <= float(_viewport_3d.size.y) + 80.0:
                return target.position + p
    var min_x := float(bounds[0])
    var min_y := float(bounds[1])
    var max_x := float(bounds[2])
    var max_y := float(bounds[3])
    var nx: float = clamp((point.x - min_x) / max(max_x - min_x, 1.0), 0.0, 1.0)
    var ny: float = clamp(1.0 - ((point.y - min_y) / max(max_y - min_y, 1.0)), 0.0, 1.0)
    return _project_3d_norm(Vector2(nx, ny), target)

func _world_to_screen_3d_projected(point: Vector2, r: Rect2) -> Dictionary:
    if _camera_3d == null or _viewport_3d == null:
        return {"visible": r.has_point(point), "point": point}
    var world3 := _world_point_to_3d(point.x, point.y, 2.2)
    if _camera_3d.is_position_behind(world3):
        return {"visible": false, "point": Vector2.ZERO}
    var local := _camera_3d.unproject_position(world3)
    var viewport_rect := Rect2(Vector2.ZERO, Vector2(float(_viewport_3d.size.x), float(_viewport_3d.size.y)))
    if not viewport_rect.grow(2.0).has_point(local):
        return {"visible": false, "point": r.position + local}
    return {"visible": true, "point": r.position + local}

func _clamp_point_to_rect(point: Vector2, r: Rect2) -> Vector2:
    return Vector2(clamp(point.x, r.position.x, r.end.x), clamp(point.y, r.position.y, r.end.y))

func _map_draw_line(a: Vector2, b: Vector2, color: Color, width: float) -> Array:
    var clipped := _clip_segment_to_rect(a, b, _map_rect)
    if clipped.size() == 2:
        draw_line(clipped[0], clipped[1], color, width)
    return clipped

func _clip_segment_to_rect(a: Vector2, b: Vector2, r: Rect2) -> Array:
    var p: Array = [-(b.x - a.x), b.x - a.x, -(b.y - a.y), b.y - a.y]
    var q: Array = [a.x - r.position.x, r.end.x - a.x, a.y - r.position.y, r.end.y - a.y]
    var u1: float = 0.0
    var u2: float = 1.0
    for i in range(4):
        var pi := float(p[i])
        var qi := float(q[i])
        if is_zero_approx(pi):
            if qi < 0.0:
                return []
        else:
            var t := qi / pi
            if pi < 0.0:
                u1 = max(u1, t)
            else:
                u2 = min(u2, t)
            if u1 > u2:
                return []
    var d := b - a
    return [a + d * u1, a + d * u2]

func _clamp_rect_to_rect(rect: Rect2, bounds: Rect2) -> Rect2:
    var out := rect
    if out.size.x > bounds.size.x:
        out.size.x = bounds.size.x
    if out.size.y > bounds.size.y:
        out.size.y = bounds.size.y
    out.position.x = clamp(out.position.x, bounds.position.x, bounds.end.x - out.size.x)
    out.position.y = clamp(out.position.y, bounds.position.y, bounds.end.y - out.size.y)
    return out


func _world_to_screen_current(point: Vector2, bounds: Array) -> Vector2:
    if _view_mode == "3d":
        return _world_to_screen_3d(point, bounds)
    return _world_to_screen(point, bounds)

func _unit_symbol_3d(pos: Vector2, unit: Dictionary, color: Color, selected: bool) -> void:
    var depth_scale: float = clamp((pos.y - _map_rect.position.y) / max(_map_rect.size.y, 1.0), 0.35, 1.0)
    var w: float = lerp(22.0, 54.0, depth_scale)
    var h: float = lerp(10.0, 24.0, depth_scale)
    var r := Rect2(pos - Vector2(w / 2.0, h), Vector2(w, h))
    var top := r.position + Vector2(0, -h * 0.55)
    var box := [r.position, Vector2(r.end.x, r.position.y), Vector2(r.end.x + w * 0.18, top.y), Vector2(top.x + w * 0.18, top.y)]
    if selected:
        draw_arc(pos, w * 0.85, 0, TAU, 48, GOLD, 2.0)
    draw_colored_polygon(box, Color(color.r * 0.40, color.g * 0.40, color.b * 0.40, 0.96))
    draw_rect(r, Color(color.r, color.g, color.b, 0.88), true)
    draw_rect(r, color, false, 1.3)
    draw_line(r.position + Vector2(w * 0.18, h * 0.25), r.end - Vector2(w * 0.18, h * 0.25), color.lightened(0.35), 1.2)
    _text(str(unit.get("name", "unit")), pos + Vector2(w * 0.55, -h * 0.45), 9, TEXT, 88)

func _draw_contact_lines_3d(units: Array, bounds: Array, r: Rect2) -> void:
    var by_id := {}
    for u in units:
        by_id[str(u.get("id", ""))] = u
    for eg in _engagements:
        var a: Dictionary = eg.get("attacker", {})
        var b: Dictionary = eg.get("defender", {})
        var aid := str(a.get("id", ""))
        var bid := str(b.get("id", ""))
        if not by_id.has(aid) or not by_id.has(bid):
            continue
        var au: Dictionary = by_id[aid]
        var bu: Dictionary = by_id[bid]
        var p1 := _world_to_screen_3d(Vector2(float(au.get("x", 0.0)), float(au.get("y", 0.0))), bounds, r)
        var p2 := _world_to_screen_3d(Vector2(float(bu.get("x", 0.0)), float(bu.get("y", 0.0))), bounds, r)
        var selected := aid == _selected_unit_id or bid == _selected_unit_id
        draw_line(p1, p2, Color(1.0, 0.60, 0.10, 0.88 if selected else 0.42), 3.0 if selected else 1.4)

func _draw_fire_mission_lines_3d(units: Array, bounds: Array, r: Rect2) -> void:
    var by_id := {}
    for u in units:
        by_id[str(u.get("id", ""))] = u
    for mission in _state.get("fire_missions", []):
        var artillery: Dictionary = by_id.get(str(mission.get("artillery_id", "")), {})
        if artillery.is_empty():
            continue
        var target_point := Vector2.ZERO
        var target_data = mission.get("target", null)
        if typeof(target_data) == TYPE_ARRAY and target_data.size() >= 2:
            target_point = Vector2(float(target_data[0]), float(target_data[1]))
        elif by_id.has(str(mission.get("target_id", ""))):
            var target: Dictionary = by_id[str(mission.get("target_id", ""))]
            target_point = Vector2(float(target.get("x", 0.0)), float(target.get("y", 0.0)))
        else:
            continue
        var p_art := _world_to_screen_3d(Vector2(float(artillery.get("x", 0.0)), float(artillery.get("y", 0.0))), bounds, r)
        var p_target := _world_to_screen_3d(target_point, bounds, r)
        draw_line(p_art, p_target, Color(1.0, 0.86, 0.18, 0.44), 1.6)
        draw_circle(p_target, 6.0, Color(1.0, 0.86, 0.18, 0.35))
        var detector: Dictionary = by_id.get(str(mission.get("detector_id", "")), {})
        var hq: Dictionary = by_id.get(str(mission.get("hq_id", "")), {})
        if not detector.is_empty():
            var p_det := _world_to_screen_3d(Vector2(float(detector.get("x", 0.0)), float(detector.get("y", 0.0))), bounds, r)
            if not hq.is_empty():
                var p_hq := _world_to_screen_3d(Vector2(float(hq.get("x", 0.0)), float(hq.get("y", 0.0))), bounds, r)
                draw_line(p_det, p_hq, Color(0.45, 0.92, 1.0, 0.34), 1.2)
                draw_line(p_hq, p_art, Color(0.45, 0.92, 1.0, 0.26), 1.2)
            else:
                draw_line(p_det, p_art, Color(0.45, 0.92, 1.0, 0.26), 1.2)

func _draw_shell_lines_3d(_units: Array, bounds: Array, r: Rect2) -> void:
    var shell_items: Array = _state.get("shells", [])
    if shell_items.is_empty():
        return
    var start_index: int = max(0, shell_items.size() - 20)
    for shell in shell_items.slice(start_index, shell_items.size()):
        var start_data: Array = shell.get("start", [])
        var target_data: Array = shell.get("target", [])
        if start_data.size() < 2 or target_data.size() < 2:
            continue
        var start_world := Vector2(float(start_data[0]), float(start_data[1]))
        var target_world := Vector2(float(target_data[0]), float(target_data[1]))
        var p_start := _world_to_screen_3d(start_world, bounds, r)
        var p_target := _world_to_screen_3d(target_world, bounds, r)
        var arc_height: float = clamp(p_start.distance_to(p_target) * 0.16, 24.0, 96.0)
        var arc_points := _shell_arc_points_2d(p_start, p_target, arc_height)
        var progress := _shell_progress(shell)
        var p_shell := _point_on_polyline(arc_points, progress)
        var collapsed := _shell_is_visual_instant(shell)
        if not collapsed:
            _draw_shell_arc_segments_screen(arc_points, r, Color(0.05, 0.025, 0.0, 0.62), 5.0, 1.0)
            _draw_shell_arc_segments_screen(arc_points, r, Color(1.0, 0.78, 0.16, 0.42), 3.0, 1.0)
            _draw_shell_arc_segments_screen(arc_points, r, Color(1.0, 0.95, 0.46, 0.98), 2.2, progress)
        if not collapsed and r.grow(-8.0).has_point(p_shell):
            draw_circle(p_shell, 7.0, Color(1.0, 0.55, 0.08, 0.28))
            draw_circle(p_shell, 4.0, Color(1.0, 0.84, 0.24, 0.96))
        if r.grow(-10.0).has_point(p_target):
            draw_circle(p_target, 13.0, Color(1.0, 0.38, 0.06, 0.22 if collapsed else 0.08))
            draw_arc(p_target, 14.0, 0.0, TAU, 30, Color(1.0, 0.48, 0.08, 0.76 if collapsed else 0.58), 2.0)

func _draw_shell_arc_segments_screen(points: Array, clip_rect: Rect2, color: Color, width: float, until_ratio: float = 1.0) -> void:
    if points.size() < 2:
        return
    var until_t: float = clamp(until_ratio, 0.0, 1.0)
    for i in range(points.size() - 1):
        var seg_t0 := float(i) / float(points.size() - 1)
        var seg_t1 := float(i + 1) / float(points.size() - 1)
        if seg_t0 >= until_t:
            break
        var a: Vector2 = points[i]
        var b: Vector2 = points[i + 1]
        if seg_t1 > until_t:
            var local_t: float = clamp((until_t - seg_t0) / max(seg_t1 - seg_t0, 0.0001), 0.0, 1.0)
            b = a.lerp(b, local_t)
        if clip_rect.has_point(a) or clip_rect.has_point(b):
            draw_line(a, b, color, width)

func _handle_keyboard_shortcut(event: InputEventKey) -> bool:
    if not event.pressed or event.echo or _active_dialog != "":
        return false
    match event.keycode:
        KEY_S:
            _handle_action("tool_select")
            return true
        KEY_M:
            _handle_action("tool_move")
            return true
        KEY_F:
            _handle_action("tool_fire")
            return true
        KEY_1:
            _handle_action("view_2d")
            return true
        KEY_2:
            _handle_action("view_3d")
            return true
        KEY_SPACE:
            _handle_action("toggle_play")
            return true
    return false

func _begin_scrollbar_drag(target: String, position: Vector2) -> bool:
    var track := _oob_scroll_track if target == "oob" else _file_scroll_track
    var knob := _oob_scroll_knob if target == "oob" else _file_scroll_knob
    var max_scroll := _oob_scroll_max if target == "oob" else _file_scroll_max
    if max_scroll <= 0.0 or track.size.y <= 0.0:
        return false
    if not track.grow(6.0).has_point(position) and not knob.grow(6.0).has_point(position):
        return false
    _scroll_drag_target = target
    _scroll_drag_offset = position.y - knob.position.y if knob.grow(6.0).has_point(position) else knob.size.y * 0.5
    _update_scrollbar_drag(position)
    return true

func _update_scrollbar_drag(position: Vector2) -> void:
    if _scroll_drag_target == "":
        return
    var track := _oob_scroll_track if _scroll_drag_target == "oob" else _file_scroll_track
    var knob := _oob_scroll_knob if _scroll_drag_target == "oob" else _file_scroll_knob
    var max_scroll := _oob_scroll_max if _scroll_drag_target == "oob" else _file_scroll_max
    var travel: float = max(track.size.y - knob.size.y, 1.0)
    var ratio: float = clamp((position.y - _scroll_drag_offset - track.position.y) / travel, 0.0, 1.0)
    if _scroll_drag_target == "oob":
        _scroll_left_oob = ratio * max_scroll
    else:
        _file_dialog_scroll = ratio * max_scroll
    queue_redraw()

func _end_scrollbar_drag(target: String = "") -> void:
    if target == "" or _scroll_drag_target == target:
        _scroll_drag_target = ""
        _scroll_drag_offset = 0.0

func _handle_file_dialog_scroll_input(event: InputEvent) -> bool:
    if _active_dialog != "file_dialog":
        return false
    if event is InputEventMouseMotion and _scroll_drag_target == "file":
        _update_scrollbar_drag(event.position)
        return true
    if event is InputEventMouseButton:
        if event.button_index == MOUSE_BUTTON_LEFT and not event.pressed and _scroll_drag_target == "file":
            _end_scrollbar_drag("file")
            return true
        if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
            _file_dialog_scroll = max(0.0, _file_dialog_scroll - 1.0)
            queue_redraw()
            return true
        if event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
            _file_dialog_scroll = min(_file_scroll_max, _file_dialog_scroll + 1.0)
            queue_redraw()
            return true
        if event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
            return _begin_scrollbar_drag("file", event.position)
    return false

func _gui_input(event: InputEvent) -> void:
    if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT]:
        if _handle_pointer_click(event.position, event.button_index):
            accept_event()


func _input(event: InputEvent) -> void:
    # While the grid-size text box has focus, let it consume typing (don't fire hotkeys).
    if _grid_size_input and _grid_size_input.has_focus() and event is InputEventKey:
        return
    if event is InputEventKey:
        if _handle_file_dialog_key(event):
            get_viewport().set_input_as_handled()
            return
        if _handle_matrix_key(event):
            get_viewport().set_input_as_handled()
            return
        if _handle_parameter_key(event):
            get_viewport().set_input_as_handled()
            return
        if _handle_keyboard_shortcut(event):
            get_viewport().set_input_as_handled()
            return
    if event is InputEventMouseButton and _event_log_rect.has_point(event.position):
        if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
            _event_log_scroll = max(0, _event_log_scroll - 1)
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
        elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
            _event_log_scroll = min(_event_log_max_scroll, _event_log_scroll + 1)
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
    if _handle_file_dialog_scroll_input(event):
        get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseMotion and _timeline_seek_dragging:
        _seek_replay_from_timeline(event.position)
        get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed and _timeline_seek_dragging:
        _timeline_seek_dragging = false
        get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseMotion and _scroll_drag_target == "oob":
        _update_scrollbar_drag(event.position)
        get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed and _scroll_drag_target == "oob":
        _end_scrollbar_drag("oob")
        get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseButton and _left_rect.has_point(event.position):
        if event.button_index == MOUSE_BUTTON_LEFT and event.pressed and _begin_scrollbar_drag("oob", event.position):
            get_viewport().set_input_as_handled()
            return
        if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
            _scroll_left_oob = max(0.0, _scroll_left_oob - 1.0)
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
        elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
            _scroll_left_oob += 1.0
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
    if _view_mode == "2d" and event is InputEventMouseButton and _map_rect.has_point(event.position):
        if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
            _map_zoom_by(1.15, event.position)
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
        elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
            _map_zoom_by(1.0 / 1.15, event.position)
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
        elif event.button_index == MOUSE_BUTTON_MIDDLE:
            _map_dragging = event.pressed
            _map_drag_last = event.position
            get_viewport().set_input_as_handled()
            return
    if _view_mode == "2d" and event is InputEventMouseMotion and _map_dragging:
        var delta_2d: Vector2 = event.position - _map_drag_last
        _map_drag_last = event.position
        _map_pan_pixels(delta_2d)
        queue_redraw()
        get_viewport().set_input_as_handled()
        return
    if _view_mode == "3d" and event is InputEventMouseButton and _map_rect.has_point(event.position):
        if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
            _move_camera("cam_zoom_in")
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
        elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
            _move_camera("cam_zoom_out")
            get_viewport().set_input_as_handled()
            queue_redraw()
            return
        elif event.button_index == MOUSE_BUTTON_MIDDLE:
            _camera_dragging = event.pressed
            _camera_drag_last = event.position
            get_viewport().set_input_as_handled()
            return
    if _view_mode == "3d" and event is InputEventMouseMotion and _camera_dragging:
        var delta: Vector2 = event.position - _camera_drag_last
        _camera_drag_last = event.position
        if Input.is_key_pressed(KEY_SHIFT):
            _camera_pan += Vector2(-delta.x, delta.y) * 0.18
        else:
            _camera_yaw += delta.x * 0.36
            _camera_pitch = clamp(_camera_pitch - delta.y * 0.22, 12.0, 65.0)
        _apply_camera_3d()
        queue_redraw()
        get_viewport().set_input_as_handled()
        return
    if event is InputEventMouseButton and event.pressed:
        if _handle_pointer_click(event.position, event.button_index):
            get_viewport().set_input_as_handled()
            return

func _seek_replay_from_timeline(position: Vector2) -> void:
    if _replay_frames.is_empty() or _timeline_seek_rect.size.x <= 0.0:
        return
    var ratio: float = clamp((position.x - _timeline_seek_rect.position.x) / max(_timeline_seek_rect.size.x, 1.0), 0.0, 1.0)
    var index: int = int(round(ratio * float(max(_replay_frames.size() - 1, 0))))
    _playing = false
    _replay_playing = false
    _set_replay_index(index)
    _status = "리플레이 이동: %d/%d 프레임" % [_replay_index + 1, _replay_frames.size()]

func _handle_pointer_click(position: Vector2, button_index: int) -> bool:
    if button_index == MOUSE_BUTTON_LEFT and not _replay_frames.is_empty() and _timeline_seek_rect.has_point(position):
        _timeline_seek_dragging = true
        _seek_replay_from_timeline(position)
        return true
    for i in range(_buttons.size() - 1, -1, -1):
        var b: Dictionary = _buttons[i]
        var rect: Rect2 = b.get("rect", Rect2())
        if rect.has_point(position):
            _handle_action(str(b.get("action", "")))
            return true
    if _active_dialog == "file_dialog" and button_index == MOUSE_BUTTON_LEFT and _begin_scrollbar_drag("file", position):
        return true
    if _active_dialog != "":
        return true
    if _map_rect.has_point(position) and _state.has("units"):
        var units: Array = _state.get("units", [])
        var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
        if button_index == MOUSE_BUTTON_LEFT:
            if _selected_unit_id != "" and _tool_mode == "edit_position":
                if _orders_locked():
                    _status = "시뮬레이션 진행 중: 위치 편집 잠김"
                    queue_redraw()
                    return true
                var world_pos := _screen_to_world_current(position, bounds)
                BackendClient.command_unit(_selected_unit_id, {"position": [world_pos.x, world_pos.y], "intent": "edit_position", "priority": "normal"})
                _set_selected_unit_local_position(world_pos)
                _status = "부대 위치 수정: %s → %.0f, %.0f" % [_selected_unit_id, world_pos.x, world_pos.y]
                queue_redraw()
                return true
            if _selected_unit_id != "" and _tool_mode in ["fire", "attack"]:
                if _orders_locked():
                    _status = "시뮬레이션 진행 중: 자세/표적 변경 잠김"
                    queue_redraw()
                    return true
                var target_id := _nearest_enemy(position, units, bounds, _selected_unit_id)
                if target_id != "":
                    _set_unit_order(_selected_unit_id, "attack", target_id)
                    BackendClient.command_unit(_selected_unit_id, {"intent": "attack", "target_id": target_id, "priority": "high"})
                    _status = "공격 표적 지정: %s -> %s" % [_selected_unit_id, target_id]
                return true
            _selected_unit_id = _nearest_unit(position, units, bounds)
            _mark_3d_dirty(false, true)
            _status = "선택: %s" % _selected_unit_id
            queue_redraw()
            return true
        elif button_index == MOUSE_BUTTON_RIGHT and _selected_unit_id != "":
            if _orders_locked():
                _status = "시뮬레이션 진행 중: 경유점 편집 잠김"
                queue_redraw()
                return true
            var world := _screen_to_world_current(position, bounds)
            BackendClient.command_unit(_selected_unit_id, {"append_waypoint": [world.x, world.y], "intent": "move", "priority": "normal"})
            _append_selected_unit_local_waypoint(world)
            _set_unit_order(_selected_unit_id, "move", "")
            _status = "경유점 추가: %s → %.0f, %.0f" % [_selected_unit_id, world.x, world.y]
            queue_redraw()
            return true
    return false

func _set_selected_unit_local_position(world: Vector2) -> void:
    for unit in _state.get("units", []):
        if str(unit.get("id", "")) == _selected_unit_id:
            unit["x"] = world.x
            unit["y"] = world.y
            unit["elevation_m"] = _terrain_height_at(world.x, world.y)
            _mark_3d_dirty(true, true)
            break

func _append_selected_unit_local_waypoint(world: Vector2) -> void:
    for unit in _state.get("units", []):
        if str(unit.get("id", "")) == _selected_unit_id:
            var waypoints: Array = unit.get("waypoints", [])
            waypoints.append([world.x, world.y])
            unit["waypoints"] = waypoints
            _mark_3d_dirty(false, true)
            break

func _pop_selected_unit_local_waypoint() -> void:
    for unit in _state.get("units", []):
        if str(unit.get("id", "")) == _selected_unit_id:
            var waypoints: Array = unit.get("waypoints", [])
            if not waypoints.is_empty():
                waypoints.pop_back()
            unit["waypoints"] = waypoints
            _mark_3d_dirty(false, true)
            break

func _clear_selected_unit_local_waypoints() -> void:
    for unit in _state.get("units", []):
        if str(unit.get("id", "")) == _selected_unit_id:
            unit["waypoints"] = []
            _mark_3d_dirty(false, true)
            break

func _button_center(action: String) -> Vector2:
    for b in _buttons:
        if str(b.get("action", "")) == action:
            var rect: Rect2 = b.get("rect", Rect2())
            return rect.get_center()
    return Vector2(-1, -1)

func _run_input_smoke() -> void:
    _input_smoke_frames += 1
    if _input_smoke_real_start_ms == 0:
        _input_smoke_real_start_ms = Time.get_ticks_msec()
    if not _backend_live:
        if Time.get_ticks_msec() - _input_smoke_real_start_ms > 15000:
            _finish_input_smoke(false, "backend_not_live")
        return
    if not _input_smoke_started:
        _input_smoke_start_time = float(_state.get("time_s", 0.0))
        _input_smoke_started = true
    if _buttons.size() > 0 and _input_smoke_action_index < _input_smoke_actions.size():
        var action := str(_input_smoke_actions[_input_smoke_action_index])
        var center := _button_center(action)
        if center.x >= 0.0:
            var ok := _handle_pointer_click(center, MOUSE_BUTTON_LEFT)
            _input_smoke_executed.append({"action": action, "ok": ok})
            if action == "step":
                _input_smoke_clicked = ok
            _input_smoke_action_index += 1
        else:
            _input_smoke_executed.append({"action": action, "ok": false, "reason": "button_not_found"})
            _input_smoke_action_index += 1
    if _input_smoke_clicked and float(_state.get("time_s", 0.0)) > _input_smoke_start_time:
        _finish_input_smoke(true, "ui_buttons_and_step_advanced_time")
    elif Time.get_ticks_msec() - _input_smoke_real_start_ms > 25000:
        _finish_input_smoke(false, "timeout_waiting_for_step")

func _finish_input_smoke(ok: bool, reason: String) -> void:
    var result := {
        "ok": ok,
        "reason": reason,
        "clicked": _input_smoke_clicked,
        "buttons": _buttons.size(),
        "start_time_s": _input_smoke_start_time,
        "end_time_s": float(_state.get("time_s", -1.0)),
        "actions": _input_smoke_executed,
        "view_mode": _view_mode,
        "tool_mode": _tool_mode,
        "order_mode": _order_mode,
        "status": "captured",
    }
    var file := FileAccess.open(_input_smoke_path, FileAccess.WRITE)
    if file:
        file.store_string(JSON.stringify(result))
    get_tree().quit(0 if ok else 1)

func _add_operator_unit() -> void:
    var units: Array = _state.get("units", [])
    var bounds: Array = _state.get("terrain", {}).get("bounds", _bounds_from_units(units))
    var template: Dictionary = _unit_type_options[_selected_unit_type_index]
    var side := str(template.get("side", _active_oob_side))
    var x := (float(bounds[0]) + float(bounds[2])) * 0.5
    var y := (float(bounds[1]) + float(bounds[3])) * 0.5
    if not _selected_unit().is_empty():
        var unit := _selected_unit()
        if str(unit.get("side", side)) == side:
            x = float(unit.get("x", x)) + 180.0
            y = float(unit.get("y", y)) + 180.0
    var kind := str(template.get("kind", "tank"))
    var strength := float(template.get("strength", 12.0))
    var new_name := "신규 %s %02d" % [str(template.get("label", "부대")), units.size() + 1]
    var echelon := str(_add_unit_echelon_options[_add_unit_echelon_index])
    var payload := {
        "name": new_name,
        "side": side,
        "kind": kind,
        "type": str(template.get("type", "custom_tank")),
        "echelon": echelon,
        "position": [x, y],
        "strength": strength,
        "max_strength": strength,
        "detection_range_m": float(template.get("detection_range_m", 2400.0)),
        "command_range_m": float(template.get("command_range_m", 5000.0)),
        "lanchester_range_m": float(template.get("lanchester_range_m", 1800.0)),
        "speed_mps": float(template.get("speed_mps", 8.0)),
        "armor": float(template.get("armor", 1.0)),
        "color": "#d84a3e" if side == "red" else "#6299eb",
    }
    if kind == "artillery":
        payload["fire_rate_per_min"] = float(template.get("fire_rate_per_min", 2.0))
        payload["shell_damage"] = float(template.get("shell_damage", 1.2))
        payload["shell_range_m"] = float(template.get("shell_range_m", 9000.0))
        payload["shell_speed_mps"] = float(template.get("shell_speed_mps", 420.0))
        payload["shell_dispersion_m"] = float(template.get("shell_dispersion_m", 140.0))
        payload["ammo_remaining"] = int(template.get("ammo_remaining", 24))
    if _add_unit_as_reserve:
        var trigger_ratio := float(_add_unit_reserve_ratio_options[_add_unit_reserve_ratio_index])
        payload["active_after_s"] = 999999.0
        payload["present_after_s"] = 999999.0
        payload["detectable_after_s"] = 999999.0
        payload["targetable_after_s"] = 999999.0
        payload["maneuver_after_s"] = 999999.0
        payload["engage_after_s"] = 999999.0
        payload["activation_phase"] = "operator_reserve"
        payload["activation_label"] = "사용자 예비부대: %s %s 손실 %.0f%% 시 투입" % [side.to_upper(), kind, trigger_ratio * 100.0]
        payload["visible_before_activation"] = true
        payload["reserve_trigger_side"] = side
        payload["reserve_trigger_kind"] = "tank" if kind != "artillery" else "artillery"
        payload["reserve_trigger_loss_ratio"] = trigger_ratio
        payload["reserve_triggered"] = false
    _pending_added_unit_name = new_name
    _status = "운용자 추가 부대 생성 요청: %s" % str(template.get("label", "부대"))
    BackendClient.add_unit(payload)

func _load_dump_file(path: String, config: bool) -> void:
    if not FileAccess.file_exists(path):
        _status = "No dump file found: %s" % path
        return
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        _status = "Cannot open dump file: %s" % path
        return
    var parsed = JSON.parse_string(file.get_as_text())
    if typeof(parsed) != TYPE_DICTIONARY:
        _status = "Dump JSON parse failed: %s" % path
        return
    if config:
        BackendClient.load_config({
            "parameters": parsed.get("parameters", {}),
            "lanchester_matrix": parsed.get("lanchester_matrix", {}),
        })
        _status = "Config 불러오기 요청: %s" % path
    else:
        BackendClient.load_state({"state": parsed.get("state", parsed)})
        _status = "State 불러오기 요청: %s" % path

func _handle_action(action: String) -> void:
    if action == "toggle_play":
        if _replay_playing:
            _replay_playing = false
            _status = "Paused - replay"
            queue_redraw()
            return
        _replay_autoplay_after_generate = false
        _playing = not _playing
        _step_timer = 0.0
        _status = "Running - live simulation" if _playing else "Paused - live simulation"
    elif action == "reset":
        _playing = false
        _replay_playing = false
        _replay_frames.clear()
        _replay_index = -1
        _replay_autoplay_after_generate = false
        _pending_replay_back = false
        _replay_calculating = false
        _last_replay_meta.clear()
        _history.clear()
        _unit_orders.clear()
        _manual_queue.clear()
        _status = "Reset requested"
        BackendClient.reset()
    elif action == "state":
        _status = "상태 새로고침 요청"
        BackendClient.request_state()
        BackendClient.request_events()
        BackendClient.request_parameters()
        BackendClient.request_lanchester_matrix()
    elif action == "fullscreen":
        var mode := DisplayServer.window_get_mode()
        if mode == DisplayServer.WINDOW_MODE_FULLSCREEN or mode == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN:
            DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
            _status = "창모드"
        else:
            DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
            _status = "전체화면"
    elif action == "toggle_battle_view":
        _battle_view_expanded = not _battle_view_expanded
        _status = "전장 확대 보기" if _battle_view_expanded else "기본 전장 보기"
    elif action == "view_2d":
        _view_mode = "2d"
        _set_3d_update_enabled(false)
        _status = "2D map mode"
    elif action == "view_3d":
        _view_mode = "3d"
        _set_3d_update_enabled(true)
        _status = "3D 지형 모드"
    elif action == "dialog_params":
        _active_dialog = "params"
        _status = "파라미터 창 열림"
    elif action == "dialog_help":
        _active_dialog = "help"
        _status = "도움말 창 열림"
    elif action == "dialog_engagement_graph":
        _active_dialog = "engagement_graph"
        _status = "교전 그래프"
    elif action == "dialog_stats":
        _active_dialog = "stats"
        _status = "통계"
    elif action == "dialog_close":
        _active_dialog = ""
        _file_dialog_mode = ""
        _editing_file_name = false
        _editing_parameter_key = ""
        _parameter_input_buffer = ""
        _editing_matrix_key = ""
        _matrix_input_buffer = ""
    elif action == "file_name_edit":
        _editing_file_name = true
        _status = "저장 파일명 편집"
    elif action == "file_save_confirm":
        var save_name := _safe_save_name()
        var save_kind := _file_dialog_kind()
        if save_kind == "config":
            _pending_named_dump_kind = "config"
            _pending_named_dump_name = save_name
            BackendClient.dump_config()
            _status = "Config 저장 중: %s" % save_name
        elif save_kind == "state":
            _pending_named_dump_kind = "state"
            _pending_named_dump_name = save_name
            BackendClient.dump_state()
            _status = "State 저장 중: %s" % save_name
        else:
            _save_unitset_named(save_name)
        _active_dialog = ""
        _file_dialog_mode = ""
        _editing_file_name = false
    elif action.begins_with("file_load|"):
        var parts := action.split("|")
        if parts.size() >= 3:
            _load_named_file(str(parts[1]), str(parts[2]))
    elif action.begins_with("file_delete|"):
        var parts := action.split("|")
        if parts.size() >= 3:
            _delete_named_file(str(parts[1]), str(parts[2]))
    elif action == "file_unitset_save":
        _open_file_dialog("unitset_save")
    elif action == "file_unitset_load":
        _open_file_dialog("unitset_load")
    elif action == "param_commit":
        _commit_parameter_input()
    elif action.begins_with("param_edit|"):
        _start_parameter_edit(action.split("|")[1])
    elif action == "map_zoom_in":
        _map_zoom_by(1.15)
    elif action == "map_zoom_out":
        _map_zoom_by(1.0 / 1.15)
    elif action == "map_zoom_reset":
        _map_zoom = 1.0
        _map_pan = Vector2.ZERO
        _status = "2D 작전지도"
    elif action.begins_with("cam_"):
        _move_camera(action)
    elif action.begins_with("matrix_edit|"):
        var parts := action.split("|")
        if parts.size() >= 3:
            _start_matrix_edit(str(parts[1]), str(parts[2]))
    elif action.begins_with("matrix|"):
        _handle_matrix_action(action)
    elif action.begins_with("select_unit|"):
        _selected_unit_id = str(action.split("|")[1])
        _mark_3d_dirty(false, true)
        var unit := _selected_unit()
        if not unit.is_empty():
            _active_oob_side = str(unit.get("side", _active_oob_side))
        _status = "선택 부대: %s" % _selected_unit_id
    elif action == "oob_red":
        _active_oob_side = "red"
        _ensure_unit_type_matches_active_side()
        _scroll_left_oob = 0.0
    elif action == "oob_blue":
        _active_oob_side = "blue"
        _ensure_unit_type_matches_active_side()
        _scroll_left_oob = 0.0
    elif action.begins_with("tool_"):
        _tool_mode = action.substr(5)
        if _tool_mode == "fire":
            _order_mode = "attack"
        elif _tool_mode == "move":
            _order_mode = "move"
        _status = "도구 선택: %s" % _tool_label()
    elif action.begins_with("order_"):
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 자세 변경 잠김"
            queue_redraw()
            return
        _order_mode = action.substr(6)
        if _order_mode == "attack":
            _tool_mode = "fire"
        elif _order_mode == "move":
            _tool_mode = "move"
        if _selected_unit_id != "":
            _set_unit_order(_selected_unit_id, _order_mode, "")
            BackendClient.command_unit(_selected_unit_id, {"intent": _order_mode, "priority": "normal"})
        _status = "명령 적용: %s" % _intent_label(_order_mode)
    elif action == "queue_add":
        _add_current_order_to_queue()
    elif action == "queue_clear":
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 명령 큐 변경 잠김"
            queue_redraw()
            return
        _manual_queue.clear()
        _unit_orders.clear()
        _status = "명령 큐 초기화"
    elif action == "replay_generate":
        _request_replay_precompute(false)
    elif action == "replay_play":
        _playing = false
        if _replay_playing:
            _replay_playing = false
            _status = "Paused - replay"
            queue_redraw()
            return
        if _replay_frames.is_empty():
            _status = "Replay 프레임 없음: 먼저 사전계산합니다"
            _request_replay_precompute(true)
        else:
            if _replay_index < 0 or _replay_index >= _replay_frames.size() - 1:
                _set_replay_index(0)
            _replay_playing = true
            _replay_timer = 0.0
            _status = "Replay 실행 중"
    elif action == "replay_back":
        _playing = false
        _replay_playing = false
        _replay_autoplay_after_generate = false
        if not _replay_frames.is_empty():
            _set_replay_index(max(0, _replay_index - 1))
        else:
            _pending_replay_back = true
            _status = "Replay 프레임 요청"
            BackendClient.request_replay()
    elif action == "delete_unit":
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 부대 편집 잠김"
            queue_redraw()
            return
        if _selected_unit_id != "":
            BackendClient.delete_unit(_selected_unit_id)
            for i in range(_state.get("units", []).size() - 1, -1, -1):
                if str(_state.get("units", [])[i].get("id", "")) == _selected_unit_id:
                    _state.get("units", []).remove_at(i)
                    break
            _status = "부대 삭제 요청: %s" % _selected_unit_id
            _selected_unit_id = ""
    elif action == "add_unit":
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 부대 편집 잠김"
            queue_redraw()
            return
        _add_operator_unit()
    elif action == "unit_type_next":
        _cycle_unit_type(1)
        _status = "추가 부대 유형: %s" % str(_unit_type_options[_selected_unit_type_index].get("label", ""))
    elif action == "unit_type_prev":
        _cycle_unit_type(-1)
        _status = "추가 부대 유형: %s" % str(_unit_type_options[_selected_unit_type_index].get("label", ""))
    elif action == "add_reserve_toggle":
        _add_unit_as_reserve = not _add_unit_as_reserve
        _status = "예비부대 추가: %s" % ("ON" if _add_unit_as_reserve else "OFF")
    elif action == "add_reserve_ratio":
        _add_unit_reserve_ratio_index = (_add_unit_reserve_ratio_index + 1) % _add_unit_reserve_ratio_options.size()
        _status = "예비 투입 기준: 본대 손실 %.0f%%" % (float(_add_unit_reserve_ratio_options[_add_unit_reserve_ratio_index]) * 100.0)
    elif action == "add_echelon":
        _add_unit_echelon_index = (_add_unit_echelon_index + 1) % _add_unit_echelon_options.size()
        _status = "부대 규모 표식: %s" % str(_add_unit_echelon_options[_add_unit_echelon_index])
    elif action == "edit_position":
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 위치 편집 잠김"
            queue_redraw()
            return
        _tool_mode = "edit_position"
        _status = "부대 위치 편집 모드"
    elif action == "waypoint_append":
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 경유점 편집 잠김"
            queue_redraw()
            return
        _tool_mode = "move"
        _order_mode = "move"
        _status = "경유점 편집 모드"
    elif action == "waypoint_remove_last":
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 경유점 편집 잠김"
            queue_redraw()
            return
        if _selected_unit_id != "":
            _pop_selected_unit_local_waypoint()
            BackendClient.command_unit(_selected_unit_id, {"remove_last_waypoint": true, "intent": "move"})
            _status = "마지막 경유점 제거"
    elif action == "waypoint_clear":
        if _orders_locked():
            _status = "시뮬레이션 진행 중: 경유점 편집 잠김"
            queue_redraw()
            return
        if _selected_unit_id != "":
            _clear_selected_unit_local_waypoints()
            BackendClient.command_unit(_selected_unit_id, {"waypoints": [], "intent": "move"})
            _status = "선택 부대 경유점 전체 제거"
    elif action == "config_dump":
        _open_file_dialog("config_save")
    elif action == "config_load":
        _open_file_dialog("config_load")
    elif action == "state_dump":
        _open_file_dialog("state_save")
    elif action == "state_load":
        _open_file_dialog("state_load")
    elif action.begins_with("param_"):
        var direction := 0
        var key := ""
        if action.ends_with("_inc"):
            direction = 1
            key = action.substr(6, action.length() - 10)
        elif action.ends_with("_dec"):
            direction = -1
            key = action.substr(6, action.length() - 10)
        if direction != 0 and key != "":
            _change_parameter(key, direction)
    elif action == "toggle_detection_ranges":
        _show_detection_ranges = not _show_detection_ranges
        _status = "탐지 범위 표시: %s" % ("ON" if _show_detection_ranges else "OFF")
    elif action == "step":
        if not _replay_frames.is_empty():
            _playing = false
            _replay_playing = false
            _set_replay_index(min(_replay_index + 1, _replay_frames.size() - 1))
        else:
            _status = "Step 요청 - +%0.0fs" % STEP_SECONDS
            BackendClient.step(STEP_SECONDS, 1)
    elif action.begins_with("speed_"):
        _speed_index = int(action.split("_")[1])
        if _replay_playing:
            _replay_timer = min(_replay_timer, _replay_frame_interval())
        _status = "실시간 재생속도 x%0.1f" % float(_speeds[_speed_index])
    elif action.begins_with("replay_fps_"):
        _replay_fps_index = clamp(int(action.split("_")[2]), 0, _replay_fps_options.size() - 1)
        if _replay_playing:
            _replay_timer = min(_replay_timer, _replay_frame_interval())
        _status = "리플레이 FPS: %d" % int(_replay_fps_options[_replay_fps_index])
    queue_redraw()

func _on_state_received(state: Dictionary) -> void:
    _backend_live = true
    _state = state
    if _state.has("contacts"):
        _engagements = _state.get("contacts", [])
    if _pending_added_unit_name != "" and _state.has("units"):
        for unit in _state.get("units", []):
            if str(unit.get("name", "")) == _pending_added_unit_name:
                _selected_unit_id = str(unit.get("id", ""))
                _active_oob_side = str(unit.get("side", _active_oob_side))
                _pending_added_unit_name = ""
                break
    var selected_exists := false
    for unit in _state.get("units", []):
        if str(unit.get("id", "")) == _selected_unit_id:
            selected_exists = true
            break
    if not selected_exists:
        _selected_unit_id = ""
    if _selected_unit_id == "" and _state.has("units") and not _state.get("units", []).is_empty():
        _selected_unit_id = str(_state.get("units", [])[0].get("id", ""))
    var summary: Dictionary = _state.get("summary", {})
    _append_history_sample(_state)
    if _state.has("parameters"):
        _parameters = _state.get("parameters", _parameters)
    if _state.has("lanchester_matrix"):
        _lanchester_matrix = _state.get("lanchester_matrix", _lanchester_matrix)
    _history_from_replay = false
    if _precompute_replay_on_start and not _precompute_replay_requested and _state.has("units"):
        _precompute_replay_requested = true
        _request_replay_precompute(false)
    _status = "Backend 상태 수신: %s units / t=%0.0fs" % [str(_state.get("units", []).size()), float(_state.get("time_s", 0.0))]
    BackendClient.request_events()
    BackendClient.request_engagements()
    _mark_3d_dirty(true, true)
    queue_redraw()

func _on_events_received(events_payload: Dictionary) -> void:
    _events = events_payload.get("events", [])
    queue_redraw()

func _on_parameters_received(parameters_payload: Dictionary) -> void:
    _parameters = parameters_payload.get("values", _parameters)
    _parameter_schema = parameters_payload.get("schema", _parameter_schema)
    if parameters_payload.has("lanchester_matrix"):
        _on_matrix_received(parameters_payload.get("lanchester_matrix", {}))
    queue_redraw()

func _on_matrix_received(matrix_payload: Dictionary) -> void:
    _lanchester_payload = matrix_payload
    _lanchester_matrix = matrix_payload.get("matrix", _lanchester_matrix)
    queue_redraw()


func _replay_frame_interval() -> float:
    if not _replay_frames.is_empty():
        return 1.0 / max(float(_replay_fps_options[_replay_fps_index]), 1.0)
    return max(0.016, REPLAY_FRAME_INTERVAL / max(float(_speeds[_speed_index]), 0.1))

func _playback_rate_label() -> String:
    if not _replay_frames.is_empty():
        return "리플레이 %d FPS" % int(_replay_fps_options[_replay_fps_index])
    return "실시간 x%0.1f / dt %s" % [float(_speeds[_speed_index]), _format_duration_log(STEP_SECONDS)]
func _replay_status_text() -> String:
    if _replay_frames.is_empty() or _replay_index < 0:
        return "리플레이 준비"
    var base := "리플레이 프레임 %d/%d ? t=%s" % [_replay_index + 1, _replay_frames.size(), _format_time_axis(float(_state.get("time_s", 0.0)))]
    if bool(_last_replay_meta.get("ended", false)):
        base += " ? 종료: %s" % str(_last_replay_meta.get("end_reason", "terminal"))
    return base
func _in_replay_view() -> bool:
    return not _replay_frames.is_empty() and _replay_index >= 0

func _restore_frame_combat_overlays(frame: Dictionary) -> void:
    # A precomputed replay frame is the source of truth while seeking/playing.
    # Contacts are embedded in the frame payload, whereas live mode also has a
    # separate /engagements request. Sync from the frame to avoid stale live
    # engagement responses hiding replay contacts.
    _engagements = frame.get("contacts", [])

func _set_replay_index(index: int, redraw: bool = true, update_status: bool = true) -> void:
    if _replay_frames.is_empty():
        _replay_index = -1
        return
    _replay_index = clamp(index, 0, _replay_frames.size() - 1)
    var frame = _replay_frames[_replay_index]
    if typeof(frame) == TYPE_DICTIONARY:
        _state = frame
        _restore_frame_combat_overlays(frame)
        if update_status:
            _status = _replay_status_text()
        if not _history_from_replay:
            _append_history_sample(_state)
        _mark_3d_dirty(true, true)
        if redraw:
            queue_redraw()

func _advance_replay(delta: float) -> void:
    if _replay_frames.is_empty():
        _replay_playing = false
        return
    _replay_timer -= delta
    if _replay_timer > 0.0:
        return
    var interval := _replay_frame_interval()
    if _replay_index < 0:
        _set_replay_index(0)
        _replay_timer = interval
        return
    var advanced := 0
    while _replay_timer <= 0.0 and advanced < REPLAY_MAX_FRAMES_PER_TICK:
        if _replay_index >= _replay_frames.size() - 1:
            _replay_playing = false
            _status = _replay_status_text()
            queue_redraw()
            return
        _set_replay_index(_replay_index + 1, false, false)
        _replay_timer += interval
        advanced += 1
    if advanced > 0:
        _status = _replay_status_text()
        queue_redraw()
    if _replay_timer < -interval:
        _replay_timer = 0.0

func _set_3d_update_enabled(enabled: bool) -> void:
    if _viewport_3d == null:
        return
    _viewport_3d.render_target_update_mode = SubViewport.UPDATE_ALWAYS if enabled else SubViewport.UPDATE_DISABLED

func _on_replay_received(replay_payload: Dictionary) -> void:
    _replay_frames = replay_payload.get("replay_frames", [])
    _replay_playing = false
    _replay_calculating = false
    _last_replay_meta = replay_payload.get("metadata", {})
    if _replay_frames.is_empty():
        _status = "No replay frames"
        queue_redraw()
        return
    var metadata: Dictionary = _last_replay_meta
    var index := 0
    if _pending_replay_back:
        index = max(0, _replay_frames.size() - 2)
        _pending_replay_back = false
    _set_replay_index(index)
    if bool(metadata.get("precomputed", false)):
        _rebuild_history_from_replay()
    if bool(metadata.get("precomputed", false)):
        if bool(metadata.get("ended", false)) and int(metadata.get("frames_returned", _replay_frames.size())) < int(metadata.get("frames_requested", _replay_frames.size())):
            _status = "Replay ended: %d/%d frames · %s · %0.0fms" % [_replay_frames.size(), int(metadata.get("frames_requested", _replay_frames.size())), str(metadata.get("end_reason", "terminal")), float(metadata.get("compute_ms", 0.0))]
        else:
            _status = "Precompute done: %d frames / %0.0fms" % [_replay_frames.size(), float(metadata.get("compute_ms", 0.0))]
    if _replay_autoplay_after_generate:
        _replay_autoplay_after_generate = false
        if _replay_index < 0 or _replay_index >= _replay_frames.size() - 1:
            _set_replay_index(0, false, false)
        _replay_playing = true
        _replay_timer = 0.0
        _status = "Replay 실행 중"
    queue_redraw()

func _on_terrain_received(terrain_payload: Dictionary) -> void:
    _terrain_payload = terrain_payload
    _terrain_cells = terrain_payload.get("cells", [])
    _terrain_mesh_ready = false
    if _view_mode == "3d":
        _build_terrain_mesh_3d()
    _mark_3d_dirty(true, true)
    queue_redraw()

func _on_engagements_received(engagements_payload: Dictionary) -> void:
    if _in_replay_view() and _state.has("contacts"):
        _engagements = _state.get("contacts", [])
    else:
        _engagements = engagements_payload.get("engagements", [])
    _mark_3d_dirty(false, true)
    queue_redraw()

func _on_config_dump_received(config_payload: Dictionary) -> void:
    _last_dump = config_payload
    if _pending_named_dump_kind == "config" and _pending_named_dump_name != "":
        var path := _save_json_named("config", _pending_named_dump_name, config_payload)
        _status = "Config saved: %s" % path
        _pending_named_dump_kind = ""
        _pending_named_dump_name = ""
    else:
        var file := FileAccess.open("user://wargame_config_dump.json", FileAccess.WRITE)
        if file:
            file.store_string(JSON.stringify(config_payload, "    "))
            _status = "Config 저장: user://wargame_config_dump.json"
    queue_redraw()

func _on_state_dump_received(state_payload: Dictionary) -> void:
    _last_dump = state_payload
    if _pending_named_dump_kind == "state" and _pending_named_dump_name != "":
        var path := _save_json_named("state", _pending_named_dump_name, state_payload)
        _status = "State 저장: %s" % path
        _pending_named_dump_kind = ""
        _pending_named_dump_name = ""
    else:
        var file := FileAccess.open("user://wargame_state_dump.json", FileAccess.WRITE)
        if file:
            file.store_string(JSON.stringify(state_payload, "    "))
            _status = "State 저장: user://wargame_state_dump.json"
    queue_redraw()

func _on_backend_error(message: String) -> void:
    _replay_calculating = false
    _status = message
    queue_redraw()

func _panel(r: Rect2, fill: Color, border: Color) -> void:
    draw_rect(r, fill, true)
    draw_rect(r, border, false, 1.0)

func _button(r: Rect2, label: String, action: String, active: bool = false) -> void:
    var hit_rect := r.grow(4.0)
    _buttons.append({"rect": hit_rect, "action": action})
    _panel(r, Color(0.10, 0.20, 0.09) if active else Color(0.08, 0.10, 0.11), GREEN if active else Color(0.22, 0.26, 0.27))
    var font := _default_font()
    var scaled_size := _font_size(12)
    var text_size := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, scaled_size)
    _text(label, r.position + Vector2(max(4.0, (r.size.x - text_size.x) / 2.0), (r.size.y + text_size.y) / 2.0 - 2.0), 12, TEXT, r.size.x - 8.0)

func _ui_scale() -> float:
    if size.x <= 0.0 or size.y <= 0.0:
        return 1.0
    return clamp(min(size.x / BASE_VIEWPORT.x, size.y / BASE_VIEWPORT.y), MIN_UI_SCALE, MAX_UI_SCALE)

func _font_size(font_size: int) -> int:
    return int(round(float(font_size) * _ui_scale()))

func _text(text: String, pos: Vector2, font_size: int = 12, color: Color = TEXT, max_width: float = -1.0, align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT) -> void:
    var scaled_size := _font_size(font_size)
    var label := text
    var width := max_width
    if max_width > 0.0:
        label = _fit_text(text, max_width, scaled_size)
    var font := _default_font()
    var shadow_alpha: float = 0.82 if color.a > 0.85 else color.a * 0.82
    var shadow := Color(TEXT_SHADOW.r, TEXT_SHADOW.g, TEXT_SHADOW.b, shadow_alpha)
    draw_string(font, pos + Vector2(1.0, 1.0), label, align, width, scaled_size, shadow)
    draw_string(font, pos + Vector2(-0.45, 0.0), label, align, width, scaled_size, Color(color.r, color.g, color.b, color.a * 0.38))
    draw_string(font, pos + Vector2(0.55, 0.0), label, align, width, scaled_size, Color(color.r, color.g, color.b, color.a * 0.72))
    draw_string(font, pos + Vector2(0.0, -0.35), label, align, width, scaled_size, Color(color.r, color.g, color.b, color.a * 0.28))
    draw_string(font, pos, label, align, width, scaled_size, color)

func _fit_text(text: String, max_width: float, font_size: int) -> String:
    if max_width <= 0.0:
        return text
    var font := _default_font()
    if font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x <= max_width:
        return text
    var label := text
    while label.length() > 1 and font.get_string_size(label + "...", HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x > max_width:
        label = label.substr(0, label.length() - 1)
    return label + "..."

func _polyline(points: Array, color: Color, width: float) -> void:
    for i in range(points.size() - 1):
        draw_line(points[i], points[i + 1], color, width)

func _draw_star(pos: Vector2, color: Color) -> void:
    draw_colored_polygon([pos + Vector2(0, -15), pos + Vector2(5, -5), pos + Vector2(16, -4), pos + Vector2(8, 4), pos + Vector2(10, 15), pos, pos + Vector2(-10, 15), pos + Vector2(-8, 4), pos + Vector2(-16, -4), pos + Vector2(-5, -5)], color)
    draw_circle(pos, 4, GOLD)

func _draw_cross(pos: Vector2, color: Color) -> void:
    draw_circle(pos, 8, Color(color.r, color.g, color.b, 0.25))
    draw_line(pos + Vector2(-8, 0), pos + Vector2(8, 0), color, 1.5)
    draw_line(pos + Vector2(0, -8), pos + Vector2(0, 8), color, 1.5)

func _unit_strength_ratio(unit: Dictionary) -> float:
    if unit.has("normalized_strength"):
        return clamp(float(unit.get("normalized_strength", 1.0)), 0.0, 1.0)
    return clamp(float(unit.get("strength", 0.0)) / max(float(unit.get("max_strength", 1.0)), 0.01), 0.0, 1.0)

func _draw_oval(center: Vector2, rx: float, ry: float, color: Color, width: float = 1.2) -> void:
    var pts := PackedVector2Array()
    for i in range(33):
        var a := TAU * float(i) / 32.0
        pts.append(center + Vector2(cos(a) * rx, sin(a) * ry))
    draw_polyline(pts, color, width, true)

func _unit_echelon(unit: Dictionary) -> String:
    var explicit := str(unit.get("echelon", unit.get("echelon_label", ""))).strip_edges()
    if explicit != "":
        return explicit
    var kind := str(unit.get("kind", "tank"))
    if kind == "artillery":
        return "III"
    if kind == "command_post":
        return "XXXX" if str(unit.get("side", "")) == "red" else "XXX"
    return "I"

func _draw_echelon_marker(r: Rect2, echelon: String, color: Color, selected: bool = false) -> void:
    if echelon == "":
        return
    var marker_color := GOLD if selected else Color(color.r, color.g, color.b, max(color.a, 0.34))
    var marker_size := 9
    var marker_width: float = max(r.size.x * 1.4, 34.0)
    var marker_pos := Vector2(r.get_center().x - marker_width * 0.5, r.position.y - 7.0)
    _text(echelon, marker_pos, marker_size, marker_color, marker_width, HORIZONTAL_ALIGNMENT_CENTER)

func _draw_app6_icon(r: Rect2, kind: String, color: Color, strength_ratio: float = 1.0, selected: bool = false, echelon: String = "") -> void:
    var ratio: float = clamp(strength_ratio, 0.0, 1.0)
    var alpha: float = clamp(color.a, 0.0, 1.0)
    var empty_fill := Color(0.94, 0.95, 0.90, 0.90 * max(alpha, 0.34))
    var live_fill := Color(color.r, color.g, color.b, 0.30 * max(alpha, 0.34))
    draw_rect(r, empty_fill, true)
    var live_h: float = r.size.y * ratio
    if live_h > 0.0:
        draw_rect(Rect2(r.position + Vector2(0.0, r.size.y - live_h), Vector2(r.size.x, live_h)), live_fill, true)
    if ratio < 0.995:
        var water_y: float = r.position.y + r.size.y - live_h
        draw_line(Vector2(r.position.x + 1.0, water_y), Vector2(r.end.x - 1.0, water_y), Color(0.08, 0.08, 0.06, 0.42 * max(alpha, 0.45)), 1.0)
        draw_rect(Rect2(r.position, Vector2(r.size.x, max(0.0, water_y - r.position.y))), Color(0.02, 0.02, 0.018, 0.14 * max(alpha, 0.45)), true)
    draw_rect(r, GOLD if selected else Color(color.r, color.g, color.b, max(alpha, 0.34)), false, 1.7)

    var ink := Color(0.04, 0.045, 0.04, 0.94 * max(alpha, 0.42))
    var c := r.get_center()
    if kind == "artillery":
        draw_circle(c, max(2.0, min(r.size.x, r.size.y) * 0.105), ink)
    elif kind == "recon":
        draw_line(c + Vector2(-r.size.x * 0.25, 0), c + Vector2(r.size.x * 0.25, 0), ink, 1.5)
        draw_line(c + Vector2(0, -r.size.y * 0.30), c + Vector2(0, r.size.y * 0.30), ink, 1.5)
        draw_circle(c, max(1.8, min(r.size.x, r.size.y) * 0.075), ink)
    elif kind == "command_post":
        draw_line(c + Vector2(0, -r.size.y * 0.34), c + Vector2(0, r.size.y * 0.34), ink, 1.7)
    else:
        _draw_oval(c, r.size.x * 0.30, r.size.y * 0.25, ink, 1.5)
    _draw_echelon_marker(r, echelon, color, selected)

func _unit_glyph(pos: Vector2, kind: String, color: Color, scale: float = 1.0, strength_ratio: float = 1.0, echelon: String = "") -> void:
    var r := Rect2(pos - Vector2(13, 9) * scale, Vector2(26, 18) * scale)
    _draw_app6_icon(r, kind, color, strength_ratio, false, echelon)

func _stat_bar(pos: Vector2, width: float, label: String, value: float, max_value: float, color: Color) -> void:
    _text(label, pos + Vector2(0, 12), 10, MUTED)
    var bar := Rect2(pos + Vector2(70, 3), Vector2(width - 120, 10))
    draw_rect(bar, Color(0.02, 0.02, 0.02), true)
    draw_rect(Rect2(bar.position, Vector2(bar.size.x * clamp(value / max(max_value, 1.0), 0.0, 1.0), bar.size.y)), color, true)
    _text("%0.0f" % value, pos + Vector2(width - 42, 12), 10, TEXT)

func _history_line(plot: Rect2, key: String, color: Color, initial: float) -> void:
    var max_t: float = max(float(_history[-1].get("time", 1.0)), 1.0)
    var prev := Vector2.ZERO
    for i in range(_history.size()):
        var item: Dictionary = _history[i]
        var p := Vector2(plot.position.x + (float(item.get("time", 0.0)) / max_t) * plot.size.x, plot.end.y - (float(item.get(key, initial)) / max(initial, 1.0)) * plot.size.y)
        if i > 0:
            draw_line(prev, p, color, 2.0)
        prev = p

func _slider(pos: Vector2, width: float, label: String, value: float, note: String) -> void:
    _text(label, pos, 10, TEXT)
    _text(note, pos + Vector2(width - 96, 0), 9, MUTED)
    var y := pos.y + 14
    draw_line(Vector2(pos.x, y), Vector2(pos.x + width, y), Color(0.25, 0.28, 0.26), 3)
    draw_line(Vector2(pos.x, y), Vector2(pos.x + width * value, y), GOLD, 3)
    draw_circle(Vector2(pos.x + width * value, y), 6, GOLD)

func _legend(r: Rect2) -> void:
    _panel(r, Color(0.04, 0.045, 0.040, 1.0), Color(0.18, 0.20, 0.18))
    _text("Legend", r.position + Vector2(10, 18), 12, TEXT)
    var y := r.position.y + 40
    for item in [["High", Color(0.78, 0.64, 0.20)], ["Low", Color(0.14, 0.32, 0.13)], ["Engage", Color(1.0, 0.56, 0.08)], ["Waypoint", GOLD], ["Observe", Color(0.55, 0.78, 1.0)]]:
        draw_line(Vector2(r.position.x + 12, y), Vector2(r.position.x + 42, y), item[1], 2)
        _text(item[0], Vector2(r.position.x + 50, y + 4), 10, TEXT)
        y += 21

func _scale_bar(r: Rect2) -> void:
    var base := Vector2(r.position.x + 24, r.end.y - 32)
    draw_line(base, base + Vector2(160, 0), Color.WHITE, 2)
    for i in range(5):
        var x := base.x + i * 40
        draw_line(Vector2(x, base.y - 7), Vector2(x, base.y + 7), Color.WHITE, 1)
        _text(str(i * 500), Vector2(x - 8, base.y - 12), 10, Color.WHITE)
    _text("m", base + Vector2(170, 4), 10, Color.WHITE)
    _text("N", Vector2(r.end.x - 26, r.position.y + 36), 14, Color.WHITE)

func _units_by_side(side: String) -> Array:
    var out := []
    for unit in _state.get("units", []):
        if str(unit.get("side", "")) == side:
            out.append(unit)
    return out

func _count_kind(units: Array, kind: String) -> int:
    var c := 0
    for unit in units:
        if str(unit.get("kind", "")) == kind:
            c += 1
    return c

func _sum_strength(units: Array) -> float:
    var total := 0.0
    for unit in units:
        total += float(unit.get("strength", 0.0))
    return total

func _sum_pending_reserve_strength(units: Array) -> float:
    var total := 0.0
    for unit in units:
        if _unit_is_pending_reserve(unit):
            total += float(unit.get("strength", 0.0))
    return total

func _type_short(t: String) -> String:
    return t.replace("_", " ")

func _selected_unit() -> Dictionary:
    for unit in _state.get("units", []):
        if str(unit.get("id", "")) == _selected_unit_id:
            return unit
    return {}

func _bounds_from_units(units: Array) -> Array:
    if units.is_empty():
        return [0.0, 0.0, 1.0, 1.0]
    var min_x := INF
    var min_y := INF
    var max_x := -INF
    var max_y := -INF
    for unit in units:
        var x := float(unit.get("x", 0.0))
        var y := float(unit.get("y", 0.0))
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
    return [min_x, min_y, max_x, max_y]

func _world_to_screen(point: Vector2, bounds: Array) -> Vector2:
    var pad := 26.0
    var vb := _map_view_bounds(bounds)
    var min_x := float(vb[0])
    var min_y := float(vb[1])
    var max_x := float(vb[2])
    var max_y := float(vb[3])
    var x: float = _map_rect.position.x + pad + ((point.x - min_x) / max(max_x - min_x, 1.0)) * max(_map_rect.size.x - pad * 2.0, 1.0)
    var y: float = _map_rect.position.y + _map_rect.size.y - pad - ((point.y - min_y) / max(max_y - min_y, 1.0)) * max(_map_rect.size.y - pad * 2.0, 1.0)
    return Vector2(x, y)

func _screen_to_world(point: Vector2, bounds: Array) -> Vector2:
    var pad := 26.0
    var vb := _map_view_bounds(bounds)
    var min_x := float(vb[0])
    var min_y := float(vb[1])
    var max_x := float(vb[2])
    var max_y := float(vb[3])
    var x: float = min_x + ((point.x - _map_rect.position.x - pad) / max(_map_rect.size.x - pad * 2.0, 1.0)) * (max_x - min_x)
    var y: float = min_y + ((_map_rect.position.y + _map_rect.size.y - pad - point.y) / max(_map_rect.size.y - pad * 2.0, 1.0)) * (max_y - min_y)
    return Vector2(x, y)


func _screen_to_world_3d(point: Vector2, bounds: Array) -> Vector2:
    if _camera_3d == null or _viewport_3d == null:
        return _screen_to_world(point, bounds)
    var local := point - _map_rect.position
    local.x = clamp(local.x, 0.0, float(_viewport_3d.size.x))
    local.y = clamp(local.y, 0.0, float(_viewport_3d.size.y))
    var origin := _camera_3d.project_ray_origin(local)
    var direction := _camera_3d.project_ray_normal(local)
    if abs(direction.y) < 0.0001:
        return _screen_to_world(point, bounds)
    var t := -origin.y / direction.y
    if t < 0.0:
        return _screen_to_world(point, bounds)
    var hit := origin + direction * t
    var mid_x := (float(bounds[0]) + float(bounds[2])) * 0.5
    var mid_y := (float(bounds[1]) + float(bounds[3])) * 0.5
    var x: float = clamp(mid_x - hit.x / max(TERRAIN_XZ_SCALE, 0.0001), float(bounds[0]), float(bounds[2]))
    var y: float = clamp(mid_y + hit.z / max(TERRAIN_XZ_SCALE, 0.0001), float(bounds[1]), float(bounds[3]))
    return Vector2(x, y)

func _screen_to_world_current(point: Vector2, bounds: Array) -> Vector2:
    if _view_mode == "3d":
        return _screen_to_world_3d(point, bounds)
    return _screen_to_world(point, bounds)

func _nearest_unit(point: Vector2, units: Array, bounds: Array) -> String:
    var best_id := ""
    var best_dist := INF
    for unit in units:
        var pos := _world_to_screen_current(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), bounds)
        var dist := point.distance_to(pos)
        if dist < best_dist:
            best_dist = dist
            best_id = str(unit.get("id", ""))
    return best_id

func _nearest_enemy(point: Vector2, units: Array, bounds: Array, friendly_id: String) -> String:
    var friendly_side := ""
    for unit in units:
        if str(unit.get("id", "")) == friendly_id:
            friendly_side = str(unit.get("side", ""))
            break
    var best_id := ""
    var best_dist := INF
    for unit in units:
        if str(unit.get("side", "")) == friendly_side or str(unit.get("kind", "")) == "command_post":
            continue
        var pos := _world_to_screen_current(Vector2(float(unit.get("x", 0.0)), float(unit.get("y", 0.0))), bounds)
        var dist := point.distance_to(pos)
        if dist < best_dist:
            best_dist = dist
            best_id = str(unit.get("id", ""))
    return best_id

func _clock_text() -> String:
    var total_min := 7 * 60 + int(float(_state.get("time_s", 0.0)) / 60.0)
    return "%02d:%02d" % [int(total_min / 60) % 24, total_min % 60]


func _event_message_ko(e: Dictionary) -> String:
    var cat := str(e.get("category", "event"))
    var unit_name := _unit_name_for_event(str(e.get("unit_id", "")))
    var target_name := _unit_name_for_event(str(e.get("target_id", "")))
    var data: Dictionary = e.get("data", {})
    if cat == "detection":
        return "탐지 보고: %s -> %s, 거리 %.0fm" % [unit_name, target_name, float(data.get("distance_m", data.get("range_m", 0.0)))]
    if cat == "intel_relay":
        return "정보 중계: %s 정찰보고 -> 지휘소 -> WTA" % unit_name
    if cat == "artillery_target":
        return "WTA 표적지정: %s 포병표적 선정" % target_name
    if cat == "shell_launch":
        return "포탄 발사: %s -> %s, 비과시간 %s" % [unit_name, target_name, _format_duration_log(float(data.get("travel_s", data.get("delay_s", 0.0))))]
    if cat == "shell_impact":
        return "포탄 착탄: %s 피해/제압 효과" % target_name
    if cat == "engagement_start":
        return "교전 시작: %s vs %s, %.0fm" % [unit_name, target_name, float(data.get("range_m", 0.0))]
    if cat == "engagement_end":
        return "교전 종료: %s / %s 접촉 이탈" % [unit_name, target_name]
    if cat == "destroyed":
        return "격파: %s 전투에서 제외" % unit_name
    if cat == "unit_added":
        return "신규 부대 추가: %s" % unit_name
    if cat == "parameters":
        return "모델 파라미터 변경"
    if cat == "load":
        return "저장 상태 불러오기"
    return str(e.get("message", "event"))

func _unit_name_for_event(unit_id: String) -> String:
    if unit_id == "":
        return "이벤트"
    var unit := _unit_by_id(unit_id)
    if unit.is_empty():
        return unit_id
    return str(unit.get("name", unit_id))

func _event_time(seconds: float) -> String:
    var day := int(floor(seconds / 86400.0))
    var total_min := 7 * 60 + int(seconds / 60.0)
    return "D+%d %02d:%02d" % [day, int(total_min / 60) % 24, total_min % 60]

func _format_duration_log(seconds: float) -> String:
    var s: float = max(seconds, 0.0)
    if s >= 86400.0:
        return "%0.1f일" % (s / 86400.0)
    if s >= 3600.0:
        return "%0.1f시간" % (s / 3600.0)
    if s >= 60.0:
        return "%0.0f분" % ceil(s / 60.0)
    if s <= 0.0:
        return "0분"
    return "1분 미만만"
