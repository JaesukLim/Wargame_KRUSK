# Wargame_KRUSK

Python-based unit-level wargame simulator for Kursk / Prokhorovka.

## Implemented scope

- DEM_data_1 CSV terrain loading, movement cost, and LOS checks
- Default Prokhorovka scenario based on the supplied initial design files
  - BLUE: 14 tank companies + 6 artillery regiments
  - RED: 32 tank companies + 4 artillery regiments
  - Unit-level aggregate combat power, not platform-by-platform modeling
- Scanned probabilistic detection model
  - range decay, terrain modifier, altitude modifier, fire-event bonus
  - seeded RNG for reproducibility
- Tank engagements via Lanchester Square Law and vehicle-type kill matrix
- Artillery fire support based on friendly reconnaissance contacts
- Pygame 2D view
  - NATO-like unit markers
  - internal water-level style strength gauge
  - clickable engagement lines with Lanchester/shell details
- Panda3D 3D view scaffold
- JSON/YAML configuration for parameters and custom scenarios
- Grid-search tuning script
- Windows/macOS standalone build script skeletons

## Environment

Recommended local interpreter: Python 3.12. The local `.venv` is now recreated with Python 3.12 and includes Pygame/Panda3D GUI dependencies.

```powershell
.\setup_venv.ps1
.\.venv\Scripts\Activate.ps1
```

Manual setup:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

Headless smoke test:

```powershell
.\.venv\Scripts\python.exe -m wargame.main --mode headless --duration 120 --dt 0.5 --out run.json
```

2D Pygame:

```powershell
.\.venv\Scripts\python.exe -m wargame.main --mode play --renderer pygame
```

3D Panda3D:

```powershell
.\.venv\Scripts\python.exe -m wargame.main --mode play --renderer panda3d
```

Grid search:

```powershell
.\.venv\Scripts\python.exe -m wargame.tools.grid_search --config src\wargame\config\default.yaml --duration 300 --dt 0.5 --out results.csv
```

## Main files

- `src/wargame/config/default.yaml`: global parameters
- `src/wargame/scenarios/prokhorovka_default.json`: default deployment/path scenario
- `src/wargame/core/detection.py`: scanned detection model
- `src/wargame/core/lanchester.py`: Lanchester Square Law
- `src/wargame/core/battlefield.py`: tick orchestration
- `src/wargame/render/pygame_renderer.py`: 2D UI/UX
- `src/wargame/render/panda3d_renderer.py`: 3D view scaffold

## Standalone build

PyInstaller should be run on the target OS. Build Windows on Windows and macOS on macOS.

```powershell
.\scripts\build_standalone.ps1
```

macOS/Linux:

```bash
bash scripts/build_standalone.sh
```
