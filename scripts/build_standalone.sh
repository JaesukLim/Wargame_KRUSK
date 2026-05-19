#!/usr/bin/env bash
set -euo pipefail
PY=${PYTHON:-python3}
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
$PY -m pip install -e . pyinstaller
$PY -m PyInstaller --noconfirm --clean --name wargame_kursk --paths src --collect-data wargame --add-data "DEM_data_1:DEM_data_1" src/wargame/main.py
echo "Build complete under dist/wargame_kursk. Cross-OS builds must be run on the target OS or CI runner."
