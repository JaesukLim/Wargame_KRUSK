#!/usr/bin/env bash
set -euo pipefail

GODOT_BIN="${GODOT_BIN:-}"
GODOT_VERSION="${GODOT_VERSION:-4.6.2}"
GODOT_STATUS="${GODOT_STATUS:-stable}"
PRESET="${PRESET:-macOS}"
PROJECT_DIR="${PROJECT_DIR:-godot}"
OUTPUT_DIR="${OUTPUT_DIR:-dist/godot-macos}"
OUTPUT_NAME="${OUTPUT_NAME:-WargameKRUSK-macos.zip}"
SKIP_DOWNLOAD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --godot-bin)
      GODOT_BIN="$2"
      shift 2
      ;;
    --godot-version)
      GODOT_VERSION="$2"
      shift 2
      ;;
    --godot-status)
      GODOT_STATUS="$2"
      shift 2
      ;;
    --preset)
      PRESET="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --output-name)
      OUTPUT_NAME="$2"
      shift 2
      ;;
    --skip-download)
      SKIP_DOWNLOAD=1
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

VERSION_TAG="${GODOT_VERSION}-${GODOT_STATUS}"
TEMPLATE_VERSION="${GODOT_VERSION}.${GODOT_STATUS}"
TOOL_ROOT="$REPO_ROOT/.omx/tools/godot-$VERSION_TAG-macos"
DOWNLOAD_ROOT="$REPO_ROOT/.omx/downloads"
mkdir -p "$TOOL_ROOT" "$DOWNLOAD_ROOT" "$REPO_ROOT/$OUTPUT_DIR"

download_if_missing() {
  local url="$1"
  local path="$2"
  if [[ -f "$path" ]]; then
    return
  fi
  if [[ "$SKIP_DOWNLOAD" == "1" ]]; then
    echo "Missing $path and --skip-download was specified." >&2
    exit 1
  fi
  echo "Downloading $url"
  curl -L "$url" -o "$path"
}

if [[ -z "$GODOT_BIN" ]]; then
  candidate="$(find "$TOOL_ROOT" -path "*/Godot.app/Contents/MacOS/Godot" -type f 2>/dev/null | head -n 1 || true)"
  if [[ -n "$candidate" ]]; then
    GODOT_BIN="$candidate"
  fi
fi

if [[ -z "$GODOT_BIN" ]]; then
  editor_zip="$DOWNLOAD_ROOT/Godot_v${GODOT_VERSION}-${GODOT_STATUS}_macos.universal.zip"
  editor_url="https://github.com/godotengine/godot-builds/releases/download/$VERSION_TAG/Godot_v${GODOT_VERSION}-${GODOT_STATUS}_macos.universal.zip"
  download_if_missing "$editor_url" "$editor_zip"
  rm -rf "$TOOL_ROOT/Godot.app"
  unzip -q -o "$editor_zip" -d "$TOOL_ROOT"
  GODOT_BIN="$TOOL_ROOT/Godot.app/Contents/MacOS/Godot"
fi

if [[ ! -x "$GODOT_BIN" ]]; then
  echo "Godot executable not found or not executable: $GODOT_BIN" >&2
  exit 1
fi

TEMPLATE_DIR="$HOME/Library/Application Support/Godot/export_templates/$TEMPLATE_VERSION"
RELEASE_TEMPLATE="$TEMPLATE_DIR/macos.zip"
if [[ ! -f "$RELEASE_TEMPLATE" ]]; then
  if [[ "$SKIP_DOWNLOAD" == "1" ]]; then
    echo "Missing export templates at $TEMPLATE_DIR and --skip-download was specified." >&2
    exit 1
  fi
  mkdir -p "$TEMPLATE_DIR"
  tpz="$DOWNLOAD_ROOT/Godot_v${GODOT_VERSION}-${GODOT_STATUS}_export_templates.tpz"
  template_url="https://github.com/godotengine/godot-builds/releases/download/$VERSION_TAG/Godot_v${GODOT_VERSION}-${GODOT_STATUS}_export_templates.tpz"
  download_if_missing "$template_url" "$tpz"
  extract_root="$DOWNLOAD_ROOT/templates-$VERSION_TAG"
  rm -rf "$extract_root"
  mkdir -p "$extract_root"
  unzip -q -o "$tpz" -d "$extract_root"
  cp -R "$extract_root/templates/." "$TEMPLATE_DIR/"
fi

OUTPUT_PATH="$REPO_ROOT/$OUTPUT_DIR/$OUTPUT_NAME"
rm -f "$OUTPUT_PATH"

echo "Using Godot: $GODOT_BIN"
echo "Using export template: $RELEASE_TEMPLATE"
echo "Exporting preset '$PRESET' to $OUTPUT_PATH"
"$GODOT_BIN" --headless --path "$PROJECT_DIR" --export-release "$PRESET" "$OUTPUT_PATH"

if [[ ! -f "$OUTPUT_PATH" ]]; then
  echo "Expected macOS export archive was not created: $OUTPUT_PATH" >&2
  exit 1
fi

echo "macOS Godot build ready: $OUTPUT_PATH"
