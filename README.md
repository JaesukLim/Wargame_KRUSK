# Wargame KRUSK

쿠르스크 / 프로호로프카 전역을 대상으로 한 부대 단위 워게임 시뮬레이션입니다. Godot 4 클라이언트와 Python localhost 백엔드로 구성됩니다.

## 구조

- **Python 백엔드** (`src/wargame`)
  - 결정론적 시뮬레이션 상태, 지형/시나리오 로딩, 탐지, 포병, Lanchester 교전을 담당합니다.
  - FastAPI로 localhost HTTP / WebSocket API를 제공합니다.
- **Godot 4 클라이언트** (`godot/`)
  - 렌더링과 조작 인터페이스를 담당합니다.
  - Python 백엔드의 `http://127.0.0.1:8765` 및 `ws://127.0.0.1:8765/ws/state`와 통신합니다.

## 시뮬레이션 문서

이 문서는 코드에 구현된 **시뮬레이션 모델만** 설명합니다. 렌더링, UI 배치, 조작 편의 기능 같은 표현 계층의 세부사항은 제외했습니다.

### 1. 부대 구성 및 아이콘 정의

#### 진영

| 코드 값 | 의미 |
| --- | --- |
| `red` | 소련군 / Red force |
| `blue` | 독일군 / Blue force |

`Side.opponent`는 반대 진영을 반환합니다.

#### 부대 종류

| 코드 값 | 시뮬레이션 역할 | 전술 표기 의미 |
| --- | --- | --- |
| `tank` | 직사 화력 장갑 부대. 전차 간 Lanchester 교전 대상입니다. | 전차 / 장갑 중대 표식 |
| `artillery` | 곡사화기 부대. WTA 화력 임무를 받아 지연 후 포탄을 발사합니다. | 포병 / 곡사화력 표식 |
| `command` | 지휘소 / HQ. 정찰 보고를 포병으로 중계합니다. 상태 payload에서는 `command_post`로 export됩니다. | 지휘소 / HQ 표식 |
| `recon` | 정찰 / 관측 부대. HQ와 포병으로 전달될 수 있는 탐지 보고를 생성합니다. | 정찰 / 관측 표식 |

`kind` 문자열은 느슨하게 정규화됩니다.

- `recon`, `scout`, `observe`, `observer` → `recon`
- `cmd`, `command`, `hq` → `command`
- `art` 포함 → `artillery`
- 그 외 → `tank`

#### 기본 Prokhorovka 전투 서열

기본 시나리오(`src/wargame/scenarios/prokhorovka_default.json`)는 개별 차량이 아니라 집계 단위 부대를 모델링합니다.

| 진영 | 전차 부대 | 포병 부대 | 정찰 부대 | 지휘소 | 주요 장비/유형 |
| --- | ---: | ---: | ---: | ---: | --- |
| Red | 32 | 4 | 1 | 1 | `T-34`, `T-70`, `M-30`, `Razvedka`, `HQ` |
| Blue | 14 | 6 | 1 | 1 | `Tiger_I`, `PzIII`, `PzIV`, `leFH18`, `Aufklaerung`, `HQ` |

기본 부대 규모:

| 시나리오 필드 | 값 |
| --- | --- |
| `tank_unit` | `company` |
| `artillery_unit` | `regiment` |
| `strength` | 집계 전투력으로 사용하는 차량/포문 수 |

#### 시나리오 부대 정의 필드

| 필드 | 의미 | 기본값 / 비고 |
| --- | --- | --- |
| `name` | 사람이 읽는 부대명 | `unit` |
| `side` | `red` 또는 `blue`. `a` / `side_a`도 red로 처리되고, 그 외 문자열은 blue가 됩니다. | `red` |
| `kind` | 부대 역할 | `tank` |
| `type` / `unit_type` | Lanchester 행렬 조회에 쓰이는 장비/차종 분류 | `default_tank` |
| `position` | 초기 `[x, y]` 지도 좌표, 단위는 m | `[0, 0]` |
| `strength` | 현재 집계 전투력 | `100.0` |
| `max_strength` | 초기 / 최대 집계 전투력 | `strength` |
| `speed_mps` | 지형 비용 적용 전 기본 이동 속도 | `18.0` |
| `detection_range_m` | 탐지 모델에서 사용하는 최대 스캔 거리 | `2200.0` |
| `command_range_m` | 탐지자-HQ-포병 중계에 사용하는 통신 거리 | `3000.0` |
| `lanchester_range_m` | 전차 직사 교전 거리 | `1500.0` |
| `lanchester_kill_rate` | `Unit.lanchester_kills`에 로드됩니다. 현재 직사 교전은 pairwise 행렬을 사용하므로 직접 사용되지 않습니다. | `0.0` |
| `armor` | 방호/장갑 스칼라로 상태에 저장됩니다. 현재 직사 피해 계산은 Lanchester 행렬 값을 사용합니다. | `1.0` |
| `morale` | 직사 교전에서 피로/효율 계수로 사용됩니다. | `1.0` |
| `path` | 경유점 목록 `[[x, y], ...]` | `[]`. `kind == tank`인 부대는 시나리오 로드 시 진영별 하드코딩 destination과 산포된 중간 경유점 1개로 자동 덮어쓰기됩니다(자세한 내용은 5절 참고). |
| `path_loop` | true이면 마지막 경유점 이후 처음으로 반복합니다. | `false` |
| `color` | 클라이언트에 export되는 부대 색상 | `#ffffff` |
| `fire_range_m` | 전차 전용 필드. 현재 전차 교전 계산에는 사용되지 않습니다. | `None` |
| `fire_rate_per_min` | 포병 발사 속도. 재장전 시간은 `60 / fire_rate_per_min`입니다. | `None`, 발사 시 fallback `2.0` |
| `shell_damage` | 거리/면적/런타임 보정 전 포탄 기본 피해량 | 포병 발사에 필요 |
| `shell_range_m` | 포병 최대 사거리 | 포병 발사에 필요 |
| `shell_speed_mps` | 탄도 비행 시간 계산에 쓰이는 포탄 속도 | 포병 발사에 필요 |
| `shell_dispersion_m` | 명중 정확도와 탄착 피해권 반경 계산에 쓰이는 산포 | fallback `150.0` |
| `ammo_limit` / `ammo_remaining` | 남은 포병 탄약 | `None`이면 무제한 |

### 2. 시뮬레이션 관련 인수, 상태 변수

#### 전역 시뮬레이션 설정

`src/wargame/config/default.yaml`에 정의됩니다.

| 필드 | 기본값 | 현재 사용 여부 | 의미 |
| --- | ---: | --- | --- |
| `simulation.random_seed` | `19430712` | 사용 | 확률적 탐지와 대포병 RNG의 seed입니다. |
| `simulation.ticks_per_second` | `30` | 정의됨, 백엔드 step 루프에서는 직접 사용하지 않음 | 고정 tick 시뮬레이션 설정 의도 |
| `simulation.fixed_dt` | `0.2` | 정의됨, API step 루프에서는 직접 사용하지 않음 | 고정 timestep 의도. Headless/API 호출은 별도 `dt`를 전달합니다. |
| `simulation.duration_seconds` | `600` | API 종료조건은 아님 | 과거/기본 duration 값. Headless는 CLI `--duration`을 사용합니다. |

#### 탐지 설정

| 필드 | 기본값 | 의미 |
| --- | ---: | --- |
| `base_probability` | `0.86` | 보정 전 기본 탐지 확률 |
| `max_detection_range_m` | `3500` | config에는 있으나 현재 탐지는 각 부대의 `detection_range_m`을 사용합니다. |
| `probabilistic` | `true` | true이면 seeded random draw가 `confidence`를 통과해야 보고가 생성됩니다. |
| `min_confidence_to_report` | `0.05` | 이 confidence 미만 보고는 폐기됩니다. |
| `range_decay_power` | `0.85` | 거리 감소식에 적용되는 지수 |
| `blocked_los_factor` | `0.35` | 지형 LOS가 막혔을 때 confidence에 곱하는 계수 |
| `fire_event_bonus` | `0.18` | 목표가 최근 발포했을 때 주는 confidence 보너스 |
| `fire_event_memory_s` | `35` | 발포 이벤트 보너스 유지 시간 |
| `terrain_modifiers` | plain `1.0`, hill `0.92`, mountain `0.78`, water `0.9`, forest `0.8`, urban `0.9` | 목표 지형에 따른 탐지 보정 |
| `altitude_modifiers` | low `0.8`, mid `0.9`, high `1.0` | 관측자 고도 band에 따른 보정 |

#### 전투 설정

| 필드 | 기본값 | 의미 |
| --- | ---: | --- |
| `combat.lanchester_range_m` | `1800` | 전역 직사 교전 거리 상한. 실제 접촉 거리는 양측 부대 거리값과 이 값의 최솟값입니다. |
| `combat.default_k_attacker` | `0.0025` | 행렬 항목이 없을 때 사용하는 fallback `k` |
| `combat.default_k_defender` | `0.0025` | 반대 방향 행렬 항목이 없을 때 사용하는 fallback `k` |
| `combat.terrain_damping` | plain `1.0`, hill `0.93`, mountain `0.82`, water `0.0` | 직사 교전에서 발사 측의 지형 효율 계수 |

#### 지휘 / WTA 설정

| 필드 | 기본값 | 의미 |
| --- | ---: | --- |
| `command.require_hq_for_artillery_tasking` | `true` | HQ가 존재하면 정찰 보고가 detector → HQ → artillery 경로로 중계되어야 합니다. HQ가 없으면 구형 시나리오 호환을 위해 진영 공유 탐지 fallback을 허용합니다. |
| `command.relay_log_interval_s` | `20` | 같은 detector-HQ-target 조합의 반복 intel relay 이벤트 최소 간격 |
| `command.detection_log_interval_s` | `25` | 같은 detector-target 조합의 반복 detection 이벤트 최소 간격 |

#### 런타임 조정 파라미터

| 파라미터 | 기본값 | 범위 | step | 시뮬레이션 용도 |
| --- | ---: | --- | ---: | --- |
| `direct_fire_scale` | `1.0` | `0.1`-`3.0` | `0.1` | 직사 Lanchester `k`에 곱합니다. |
| `combat_speed_scale` | `0.60` | `0.25`-`2.0` | `0.05` | 직사 교전 소모 속도에 추가로 곱합니다. |
| `artillery_delay_s` | `240.0` | `25.0`-`600.0` | `15.0` | 포탄 발사부터 탄착까지의 최소 지연 시간 |
| `artillery_damage_scale` | `1.0` | `0.1`-`3.0` | `0.1` | 포탄 피해와 대포병 피해에 곱합니다. |
| `target_area_scale` | `1.0` | `0.25`-`4.0` | `0.25` | 값이 커지면 피해권 반경은 증가하고 피해 밀도는 감소합니다. |

#### Lanchester 행렬

`simulation.lanchester.kill_matrix`는 공격자-목표 nested table입니다.

```yaml
kill_matrix:
  AttackerType:
    TargetType: k_value
```

- 행렬은 **방향성을 갖습니다.** 대칭 행렬이 아닙니다.
- `T-34 -> PzIV`와 `PzIV -> T-34`는 별도 계수입니다.
- 런타임 patch 시 장비의 진영을 추론할 수 있으면 같은 편 전차 type 간 수정은 거부됩니다.
- 런타임 schema: `min=0.0`, `max=0.02`, `step=0.0001`.
- 전차 접촉에서 어느 한 방향이라도 누락되면 양방향 모두 기본값을 사용합니다.

#### 런타임 상태 변수

| 객체 | 필드 | 의미 |
| --- | --- | --- |
| `BattleField` | `time_s` | 현재 시뮬레이션 시간, 초 단위 |
| `BattleField` | `units` | unit id 기준 활성 부대 dictionary |
| `BattleField` | `shells` | shell id 기준 활성/탄착 포탄 record |
| `BattleField` | `contacts` | 활성 직사 전차 교전 pair |
| `BattleField` | `event_log` | 최대 500개로 제한되는 event log |
| `BattleField` | `replay_frames` | 최대 900개로 제한되는 sampling state history |
| `BattleField` | `contact_history` | pair별 교전 전투력 history. pair당 최대 360 sample |
| `BattleField` | `fire_missions` | artillery unit id 기준 현재 WTA 포병 임무 |
| `Unit` | `reload_timer` | 포병 재장전 countdown |
| `Unit` | `waypoint_eps_m` | 경유점 도착 판정 허용 오차. 기본 `10.0` m |
| `Unit` | `last_fired_at` | 마지막 직사/곡사 발포 시각. 탐지 fire-event bonus에 사용됩니다. |
| `Unit` | `current_order` | 마지막으로 수락된 command payload |
| `ShellImpact` | `launch_time`, `impact_time`, `remaining_time()` | DES 방식 delayed shell timing |
| `ShellImpact` | `accuracy`, `radius_m`, `damage` | launch 시점에 계산된 포탄 품질, 피해권 반경, 기본 피해량 |

#### 지형 변수

기본 시나리오의 지형은 `DEM_data_1/prokhorovka_terrain_250m.csv`에서 로드됩니다.

| 지형 필드 | 의미 |
| --- | --- |
| `row`, `col` | grid index |
| `x_m`, `y_m` | 미터 단위 좌표 |
| `lat`, `lon` | 존재할 경우 지리 참조값 |
| `elev_m` | 고도 |
| `slope_deg` | 경사 |
| `roughness_m` | 국지 roughness |
| `local_relief_m` | 국지 기복 |
| `landform_code`, `landform_name` | 탐지/전투 보정에 쓰이는 지형 분류. 이동 비용도 `landform_name`에서 산출합니다(아래). |
| `move_cost_infantry`, `move_cost_vehicle` | CSV에 저장되지만 런타임 이동 비용 계산에는 사용되지 않습니다. `terrain.py`의 `SPEED_MULT_BY_LANDFORM` 표가 우선합니다. |
| `water` | true이면 해당 셀은 하천으로 취급되어 기본 속도의 20%로 통과합니다(과거의 무한 차단 동작은 제거되었습니다). |
| `road`, `rail`, `antitank_ditch` | export되는 지형 속성입니다. 현재 CSV 이동 비용 외 별도 이동 보정으로는 쓰이지 않습니다. |

### 3. 교전 논리(전차)

직사 교전은 살아있는 적대 전차 부대 pair에 대해서만 해결됩니다.

1. 서로 다른 진영의 살아있는 전차 pair를 순회합니다.
2. 거리 `d`를 계산합니다.
3. 접촉 거리를 계산합니다.

   ```text
   contact_distance = min(
       attacker.lanchester_range_m or default_lanchester_range_m,
       defender.lanchester_range_m or default_lanchester_range_m,
       default_lanchester_range_m,
   )
   ```

4. `d > contact_distance`이면 pair를 제외합니다.
5. 최소 한 방향의 탐지가 필요합니다. attacker가 defender를 보거나 defender가 attacker를 봐야 합니다.
6. pairwise kill rate를 결정합니다.
   - `k_uv = matrix[attacker.type][defender.type]`
   - `k_vu = matrix[defender.type][attacker.type]`
   - 둘 중 하나라도 없으면 `default_k_attacker`, `default_k_defender`를 사용합니다.
7. 지형 및 거리 보정을 계산합니다.

   ```text
   terrain_u = attacker 위치의 terrain_damping
   terrain_v = defender 위치의 terrain_damping
   range_factor = max(0.25, 1 - d / (contact_distance * 1.5))
   effective_fire_scale = direct_fire_scale * combat_speed_scale
   ```

8. 구현된 Lanchester step을 적용합니다.

   ```text
   attacker_loss = k_vu * range_factor * effective_fire_scale * defender_strength * dt * terrain_v * defender_morale
   defender_loss = k_uv * range_factor * effective_fire_scale * attacker_strength * dt * terrain_u * attacker_morale

   attacker_strength = max(0, attacker_strength - attacker_loss)
   defender_strength = max(0, defender_strength - defender_loss)
   ```

9. 양측 부대의 `last_fired_at`은 현재 시간으로 갱신됩니다.
10. contact record는 range, last losses, last effective `k`, terrain factor, strength history를 포함해 생성 또는 갱신됩니다.
11. 거리/탐지/접촉 조건이 더 이상 충족되지 않으면 stale contact가 제거됩니다.

이동과의 상호작용: 활성 직사 교전에 들어간 부대는 위치를 고정합니다. waypoint list는 보존되며, 교전이 끊긴 뒤 이동을 재개할 수 있습니다.

### 4. 교전 논리(포병) - 곡사화기 모델링, 피해평가 함수

구현된 곡사화력 모델은 집계 포병, 지연 탄착, WTA 임무 할당, 면적 피해, 대포병 위험을 포함합니다.

#### WTA 임무 할당 체계

포병은 `_resolve_artillery`에서 목표를 직접 scan하지 않습니다. 정찰 원천 보고를 사용합니다.

```text
정찰/관측 탐지 -> 아군 HQ 중계 -> 포병 WTA 임무 할당 -> 지연 후 포탄 탄착
```

각 살아있는 포병 부대에 대해:

1. `shell_range_m`이 없는 포병은 제외합니다.
2. 살아있는 적 전차만 후보로 고려합니다.
3. `recon_only=True` 조건의 best commanded detection report가 필요합니다.
4. 지휘 중계가 요구되고 HQ가 존재하면 다음 링크 조건을 만족해야 합니다.

   ```text
   distance(detector, HQ) <= max(detector.command_range_m, HQ.command_range_m)
   distance(HQ, artillery) <= max(HQ.command_range_m, artillery.command_range_m)
   ```

5. HQ가 없으면 구형 시나리오 호환을 위해 진영 공유 보고 fallback을 허용합니다.
6. 후보 목표는 artillery `shell_range_m` 안에 있어야 합니다.
7. greedy WTA score는 다음과 같습니다.

   ```text
   target_value = target.strength / max(target.max_strength, 1)
   score = detection_confidence * (0.65 + target_value) / max(distance(artillery, target), 1)
   ```

8. score가 가장 높은 목표가 임무를 받습니다.
9. 같은 artillery가 같은 target을 45초 이내에 이미 할당받았다면, 새 로그 없이 기존 임무를 유지합니다.

fire mission은 artillery id, target id/name, 할당된 target position, detector id/name, HQ id/name, confidence, reported distance, LOS flag, terrain factor, altitude factor, range factor, fire-event bonus, assigned time을 저장합니다.

#### 발사 및 포탄 생성

포병은 다음 조건을 만족할 때 발사합니다.

- 살아있음
- reload timer가 0
- 유효한 fire mission이 있음
- 목표가 존재하고 살아있으며 적군임
- 임무 목표 지점이 `shell_range_m` 안에 있음
- `shell_speed_mps`, `shell_damage`, `shell_range_m`이 정의되어 있음
- `ammo_remaining`이 `None`이거나 0보다 큼

발사 시점 계산:

```text
ballistic_travel = distance(launcher, aim_point) / max(shell_speed_mps, 1)
travel = max(2, artillery_delay_s, ballistic_travel)
range_factor = max(0.2, 1 - distance / shell_range_m)
dispersion_penalty = max(0.35, 1 - shell_dispersion_m / max(distance, 1))
accuracy = clamp(detection_confidence * range_factor * dispersion_penalty, 0.05, 1.0)
radius_m = clamp(shell_dispersion_m * sqrt(target_area_scale) * 1.6, 75, 650)
damage = shell_damage * range_factor * artillery_damage_scale / target_area_scale
```

발사 후:

- `ShellImpact` record가 생성됩니다.
- `last_fired_at`이 갱신됩니다.
- finite ammo이면 `ammo_remaining`이 1 감소합니다.
- `reload_timer = 60 / fire_rate_per_min`가 적용됩니다. fallback rate는 `2.0` rounds/minute입니다.
- 대포병 resolution을 시도합니다.

#### 탄착 및 피해평가

`time_s >= impact_time`이 되면, 포탄은 impact point 기준 `radius_m` 안에 있는 모든 살아있는 적 부대를 평가합니다.

```text
falloff = max(0, 1 - distance_to_impact / radius)
area_factor = 0.25 + 0.75 * falloff
if unit is intended target:
    area_factor = max(area_factor, 0.85)
unit_damage = shell.damage * shell.accuracy * area_factor
unit.strength = max(0, unit.strength - unit_damage)
```

이는 Carleton식 집계 면적효과 근사입니다. 피해는 impact point에서 가장 높고 beaten zone 바깥쪽으로 갈수록 감소하며, 파편 피해 floor를 유지합니다.

#### 대포병

포병이 발사한 뒤, 적 포병 중 살아있고 자기 `shell_range_m` 안에 launcher를 포함하는 부대가 반응할 수 있습니다.

```text
responder = 가장 가까운 eligible enemy artillery
probability = min(0.65, 0.12 + detection_confidence * 0.35)
base_damage = max(0.05, responder.shell_damage * 0.08)
damage = base_damage * artillery_damage_scale
```

seeded random draw가 성공하면, 발사한 포병 부대의 `strength`가 `damage`만큼 감소합니다.

#### Damage-state export

각 부대는 손실 strength로부터 근사적인 4-state aggregate damage state를 export합니다.

```text
lost = max(0, max_strength - strength)
killed = 0.55 * lost
mobility_kill = 0.25 * lost
firepower_kill = 0.20 * lost
no_kill = max(strength, 0)
```

### 5. 이동 논리

이동은 waypoint 기반이며 지형 이동 비용을 반영합니다.

1. 파괴된 부대는 이동하지 않습니다.
2. 현재 직사 교전 중인 부대는 이동하지 않습니다.
3. waypoint가 없으면 위치를 유지합니다.
4. 현재 목표는 `movement_path.current_target()`입니다.
5. 목표까지의 거리가 `<= waypoint_eps_m`이면 다음 waypoint로 진행합니다. 기본값은 `10 m`입니다.
6. 현재 위치의 terrain cell에서 이동 비용을 읽습니다(`terrain.movement_cost`).
   - 비용은 `landform_name`과 `water` boolean에서 산출됩니다. 보병/차량 동일하게 적용됩니다.
   - 기본 속도 배율표(`SPEED_MULT_BY_LANDFORM`, `terrain.py`): plain `1.0`, hill `0.8`, forest `0.7`, urban `1.0`, mountain `0.5`, landform `water` `0.2`.
   - `water == True`인 셀은 하천으로 처리되어 배율 `0.2`(비용 5.0)를 사용합니다.
7. 위치는 다음만큼 전진합니다.

   ```text
   effective_speed = speed_mps / movement_cost
   step_distance = effective_speed * dt
   ```

8. waypoint를 지나치지 않도록 이동량은 clamp됩니다.
9. `path_loop`가 true이면 마지막 waypoint 이후 index가 0으로 돌아갑니다. false이면 마지막 waypoint에 머뭅니다.

전차 부대 자동 경로 할당(`sim_runner.py`):

- 시나리오 로드 직후, `kind == tank`인 모든 부대의 `movement_path`는 `[산포된 중간 경유점, 진영별 destination]` 두 점으로 덮어쓰기됩니다. 시나리오 JSON에 명시된 `path`는 전차에 대해 무시됩니다.
- 하드코딩 destination(`sim_runner.RED_DESTINATION`, `sim_runner.BLUE_DESTINATION`): Red는 `(2700, 3950)`(블루 스폰 중앙), Blue는 `(12000, 15000)`(플레이박스 북동쪽).
- 중간 경유점은 출발지와 destination의 중점에 진격 방향에 수직인 lateral scatter `±1500 m`와 axis-jitter `±500 m`를 더해 생성됩니다. 재현성을 위해 `simulation.random_seed`로 seeded RNG를 사용합니다.
- artillery / command / recon 부대의 `path`는 자동 덮어쓰기 대상이 아니며 시나리오 JSON 값을 그대로 사용합니다.

unit command 입력:

| Command field | 효과 |
| --- | --- |
| `waypoints` | 전체 waypoint list를 교체합니다. |
| `position` | 위치를 직접 설정합니다. 시나리오 편집/state load에 사용됩니다. |
| `append_waypoint` | waypoint 하나를 추가합니다. |
| `remove_last_waypoint` | 마지막 waypoint가 있으면 제거합니다. |
| `intent` | `current_order`에 저장됩니다. `move`, `attack`, `defend`, `retreat` 등 문자열을 받습니다. |
| `target_id` | command 대상 참조로 저장됩니다. |
| `priority` | command 우선순위로 저장됩니다. |
| `execute_at_s` | 예약 실행 시간으로 저장됩니다. |

### 6. 탐지 논리

탐지는 살아있는 적대 부대 모든 pair 사이에서 평가됩니다.

후보 제외 조건:

- 같은 부대: 제외
- 같은 진영: 제외
- 거리가 관측자 `detection_range_m`보다 큼: 제외

confidence 계산:

```text
range_factor = max(0, 1 - distance / observer.detection_range_m) ^ range_decay_power
terrain_factor = terrain_modifiers[target_cell.landform_name]
altitude_factor = altitude_modifiers[observer_elevation_band]
confidence = base_probability * range_factor * terrain_factor * altitude_factor
if LOS blocked:
    confidence *= blocked_los_factor
if target fired within fire_event_memory_s:
    confidence += fire_event_bonus
confidence = clamp(confidence, 0, 1)
```

보고 생성 조건:

- `confidence < min_confidence_to_report`이면 폐기
- `probabilistic`이 true이면 `rng.random() <= confidence`일 때만 보고 생성
- 생성된 보고는 detector id, target id, confidence, distance, LOS, terrain factor, altitude factor, range factor, fire-event bonus를 저장합니다.

LOS 모델:

- 관측자와 목표 사이의 지형 profile을 sampling합니다.
- 관측자와 목표 높이는 기본적으로 지형고도 + `2.5 m`입니다.
- sampling terrain point가 관측자 눈높이와 목표 높이를 잇는 직선보다 `1.5 m` 초과로 높으면 시야가 차단됩니다.

고도 band:

- terrain elevation을 min/max elevation 사이에서 normalize합니다.
- `< 0.33` → `low`; `< 0.66` → `mid`; 그 이상은 `high`.

### 7. 종료조건

백엔드 종료조건은 진영별 살아있는 전차 수입니다.

| 조건 | `winner` | `end_reason` |
| --- | --- | --- |
| Red 전차 수 `<= 0` 그리고 Blue 전차 수 `<= 0` | `draw` | `no_tanks` |
| Red 전차 수 `<= 0` | `blue` | `red_tanks_destroyed` |
| Blue 전차 수 `<= 0` | `red` | `blue_tanks_destroyed` |
| 그 외 | `None` | `None` |

step loop 동작:

- API `step`은 살아있는 부대가 없거나 `is_terminal()`이 true이면 조기 종료합니다.
- 현재 시뮬레이션은 `duration_seconds`에 도달했다는 이유만으로 종료되지 않습니다.
- Headless 모드는 요청된 duration이 끝나거나 살아있는 부대가 없어질 때까지 실행됩니다.
- Timeline progress는 `timeline.expected_duration_s`가 설정되어 있으면 그 값을 사용하고, 없으면 `3600 s`로 fallback합니다.

### 8. 추적하는 통계량

#### Summary 통계

`summary` 아래에 export됩니다.

| 필드 | 의미 |
| --- | --- |
| `active_units` | 살아있는 부대 수 |
| `red_strength` | red 부대 `strength` 합계 |
| `blue_strength` | blue 부대 `strength` 합계 |
| `active_contacts` | 활성 직사 교전 수 |
| `ended` | 종료 flag |
| `winner` | `red`, `blue`, `draw`, 또는 `None` |
| `end_reason` | 종료 사유 문자열 |
| `red_tanks`, `blue_tanks` | 진영별 살아있는 전차 수 |
| `expected_duration_s` | timeline 기준 duration |
| `progress_ratio` | 종료 시 `1.0`, 그 외에는 `time_s / expected_duration_s`이며 최대 `0.98` |
| `current_frame` | `int(time_s / 30)` |
| `total_frames` | `int(expected_duration_s / 30)`, 최소 1 |

#### 부대별 통계

각 unit에 대해 export됩니다.

- `id`, `name`, `side`, `kind`, `type`
- `x`, `y`, `elevation_m`
- `strength`, `max_strength`, `normalized_strength`
- `morale`, `speed_mps`, `armor`
- `detection_range_m`, `command_range_m`, `lanchester_range_m`
- `ammo_remaining`
- `waypoints`
- `order`
- `damage_state`

#### 직사 교전 통계

`contacts` 및 `/engagements`로 export됩니다.

- contact id
- attacker / defender 요약 정보
- `started_at` 및 `active_seconds`
- 현재 `range_m`
- 마지막 attacker / defender 손실량
- 양방향 마지막 effective `k` 값
- attacker / defender terrain factor
- law label: `Lanchester Square Law`
- engagement payload 기준 최근 strength history 120개 sample

내부적으로 `contact_history`는 pair당 최대 360개 sample을 유지합니다.

#### 포병 통계

`shells` 및 `fire_missions`로 export됩니다.

- shell id, launcher id, target id
- shell 시작점과 목표점
- shell damage, accuracy, radius, impact time, remaining time, kind
- 현재 WTA mission의 target, detector, HQ, confidence, reported distance, LOS, terrain/altitude/range factor, fire-event bonus, assignment time

#### Event log 및 replay

현재 시뮬레이션에서 발생시키는 event category는 다음과 같습니다.

- `unit_added`, `unit_removed`, `destroyed`
- `command_post`, `unit_command`
- `detection`, `intel_relay`
- `engagement_start`, `engagement_end`
- `artillery_target`, `shell_launch`, `shell_impact`, `counter_battery`
- `parameters`, `load`

Event log는 최근 500개로 제한됩니다. Replay frame은 최소 2초 간격으로 sampling되며 최근 900개 frame만 유지합니다.

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Python 백엔드 실행

```powershell
.\.venv\Scripts\python.exe -m wargame.main --mode serve --host 127.0.0.1 --port 8765
```

Smoke endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/state
Invoke-RestMethod -Method Post -ContentType 'application/json' -Body '{"dt":30.0,"steps":1}' http://127.0.0.1:8765/step
```

## Godot 클라이언트 실행

1. Godot 4를 엽니다.
2. `godot/project.godot`를 import/open합니다.
3. Python 백엔드를 먼저 시작합니다.
4. Godot main scene을 실행합니다.

## Godot standalone client 패키징

repository root에서 Windows standalone Godot client를 빌드합니다.

```powershell
.\scripts\build_godot_windows.ps1
```

산출물:

- `dist\godot\WargameKRUSK.exe`
- `dist\godot\WargameKRUSK.pck`
- `dist\godot\WargameKRUSK-windows-x86_64.zip`

실행 순서는 동일합니다. Python 백엔드를 먼저 시작한 뒤 exported executable을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m wargame.main --mode serve --host 127.0.0.1 --port 8765
.\dist\godot\WargameKRUSK.exe
```

## 백엔드 API 계약

시뮬레이션 관련 endpoint만 나열합니다.

- `GET /health` - 백엔드 상태 및 부대 수
- `GET /state` - compact live simulation snapshot
- `GET /terrain` - 시뮬레이션 client가 사용하는 terrain payload
- `GET /engagements` - 활성 직사 교전 통계
- `GET /events` - event log
- `GET /state/replay` - live state payload와 분리된 replay frame
- `GET /state/dump` / `POST /state/load` - 전체 시뮬레이션 state 저장/로드
- `GET /config/dump` / `POST /config/load` - runtime simulation parameter 및 Lanchester matrix 저장/로드
- `GET /parameters` / `PATCH /parameters` - runtime 조정 가능 model parameter
- `GET /lanchester/matrix` / `PATCH /lanchester/matrix` - runtime attacker-vs-defender `k` matrix
- `POST /reset` - startup config/scenario로 시뮬레이션 재생성. 빈 body 허용
- `POST /step` - 시뮬레이션 진행. Body: `{ "dt": 30.0, "steps": 1 }`; `dt`는 `>0` 및 `<=600`, `steps`는 `1`-`600`
- `POST /command/unit/{unit_id}` - unit intent / waypoint command 전달
- `POST /units` - 집계 simulation unit 추가
- `POST /units/{unit_id}/delete` - 집계 simulation unit 및 관련 shell/contact/fire mission 제거
- `WS /ws/state` - `state`, `step`, `reset`, `set_parameters`, `set_lanchester_matrix`, `add_unit`, `load_state`, `load_config`, `delete_unit`, `command_unit` message를 받습니다.

## Headless 시뮬레이션

```powershell
.\.venv\Scripts\python.exe -m wargame.main --mode headless --duration 10 --dt 0.2 --out .omx\artifacts\headless.json
```

CLI simulation 인수:

| 인수 | 의미 |
| --- | --- |
| `--config` | 선택적 override config file path |
| `--scenario` | 선택적 override scenario file path |
| `--mode` | `serve`, `headless`, 또는 `tune` |
| `--duration` | Headless duration, 초 단위 |
| `--dt` | Headless simulation timestep |
| `--out` | Headless JSON history 출력 경로 |

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall src tests
```

## Repository hygiene

Godot이 현재 렌더링/runtime 클라이언트이므로 Python GUI renderer와 standalone build script skeleton은 제거되었습니다. `__pycache__`, `*.egg-info`, `.godot/`, build output, local virtual environment, IDE file, local Godot editor distribution 같은 생성물은 ignore됩니다.
