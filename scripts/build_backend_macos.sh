#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="dist/backend-macos"
OUTPUT_NAME="WargameKRUSKBackend"
PYTHON_EXE=""
CLEAN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --output-name)
      OUTPUT_NAME="$2"
      shift 2
      ;;
    --python)
      PYTHON_EXE="$2"
      shift 2
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "$PYTHON_EXE" ]]; then
  if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_EXE="$REPO_ROOT/.venv/bin/python"
  else
    PYTHON_EXE="python3"
  fi
fi

if ! "$PYTHON_EXE" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller not found; installing build dependencies into the active Python environment..."
  "$PYTHON_EXE" -m pip install -e ".[build]"
fi

if [[ "$CLEAN" == "1" ]]; then
  rm -rf "$REPO_ROOT/build/pyinstaller-backend-macos" "$REPO_ROOT/$OUTPUT_DIR"
fi

mkdir -p "$REPO_ROOT/$OUTPUT_DIR" "$REPO_ROOT/build/pyinstaller-backend-macos" "$REPO_ROOT/build/pyinstaller-spec-macos"

echo "Building macOS standalone Python backend..."
"$PYTHON_EXE" -m PyInstaller \
  --noconfirm \
  --clean \
  --name "$OUTPUT_NAME" \
  --onefile \
  --console \
  --paths "$REPO_ROOT/src" \
  --distpath "$REPO_ROOT/$OUTPUT_DIR" \
  --workpath "$REPO_ROOT/build/pyinstaller-backend-macos" \
  --specpath "$REPO_ROOT/build/pyinstaller-spec-macos" \
  --add-data "$REPO_ROOT/src/wargame/config:wargame/config" \
  --add-data "$REPO_ROOT/src/wargame/scenarios:wargame/scenarios" \
  --add-data "$REPO_ROOT/DEM_data_1:DEM_data_1" \
  --collect-submodules uvicorn \
  --collect-submodules uvicorn.protocols \
  --collect-submodules uvicorn.lifespan \
  --collect-submodules uvicorn.loops \
  --collect-submodules watchfiles \
  --hidden-import yaml \
  "$REPO_ROOT/src/wargame/main.py"

chmod +x "$REPO_ROOT/$OUTPUT_DIR/$OUTPUT_NAME"
echo "Standalone macOS backend ready: $REPO_ROOT/$OUTPUT_DIR/$OUTPUT_NAME"
