#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="dist/standalone-macos"
SKIP_DOWNLOAD=0
CLEAN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --skip-download)
      SKIP_DOWNLOAD=1
      shift
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

backend_args=(--clean)
godot_args=()
if [[ "$CLEAN" == "1" ]]; then
  rm -rf "$REPO_ROOT/$OUTPUT_DIR"
fi
if [[ "$SKIP_DOWNLOAD" == "1" ]]; then
  godot_args+=(--skip-download)
fi

"$SCRIPT_DIR/build_backend_macos.sh" "${backend_args[@]}"
"$SCRIPT_DIR/build_godot_macos.sh" "${godot_args[@]}"

mkdir -p "$REPO_ROOT/$OUTPUT_DIR"
rm -rf "$REPO_ROOT/$OUTPUT_DIR/WargameKRUSK.app"

EXPORT_ZIP="$REPO_ROOT/dist/godot-macos/WargameKRUSK-macos.zip"
if [[ ! -f "$EXPORT_ZIP" ]]; then
  echo "Godot macOS export archive missing: $EXPORT_ZIP" >&2
  exit 1
fi

tmp_extract="$(mktemp -d)"
trap 'rm -rf "$tmp_extract"' EXIT
unzip -q -o "$EXPORT_ZIP" -d "$tmp_extract"

app_path="$(find "$tmp_extract" -maxdepth 2 -name "*.app" -type d | head -n 1 || true)"
if [[ -z "$app_path" ]]; then
  echo "No .app bundle found inside $EXPORT_ZIP" >&2
  exit 1
fi
cp -R "$app_path" "$REPO_ROOT/$OUTPUT_DIR/WargameKRUSK.app"

backend_src="$REPO_ROOT/dist/backend-macos/WargameKRUSKBackend"
backend_dst="$REPO_ROOT/$OUTPUT_DIR/WargameKRUSK.app/Contents/MacOS/WargameKRUSKBackend"
if [[ ! -f "$backend_src" ]]; then
  echo "macOS backend executable missing: $backend_src" >&2
  exit 1
fi
cp "$backend_src" "$backend_dst"
chmod +x "$backend_dst"

cat > "$REPO_ROOT/$OUTPUT_DIR/README_STANDALONE_MACOS.txt" <<'EOF'
Wargame KRUSK macOS standalone package

?ㅽ뻾:
  - WargameKRUSK.app ???ㅽ뻾?⑸땲??
  - ???대? Contents/MacOS/WargameKRUSKBackend 諛깆뿏?쒕뒗 Godot ?대씪?댁뼵?멸? ?먮룞?쇰줈 ?쒖옉?⑸땲??

二쇱쓽:
  - unsigned 鍮뚮뱶?대?濡?macOS Gatekeeper媛 李⑤떒?섎㈃ Finder ?고겢由?> ?닿린瑜??ъ슜?섍굅??
    媛쒕컻/?뚯뒪???섍꼍?먯꽌 xattr -dr com.apple.quarantine WargameKRUSK.app ???ㅽ뻾?섏꽭??
  - 諛고룷??notarization/signing? 蹂꾨룄 Apple Developer ?몄쬆?쒓? ?꾩슂?⑸땲??
EOF

package_zip="$REPO_ROOT/dist/WargameKRUSK-macos-standalone.zip"
rm -f "$package_zip"
(cd "$REPO_ROOT/$OUTPUT_DIR" && zip -qr "$package_zip" WargameKRUSK.app README_STANDALONE_MACOS.txt)

echo "Combined macOS standalone package ready: $REPO_ROOT/$OUTPUT_DIR"
echo "Combined macOS archive ready: $package_zip"

