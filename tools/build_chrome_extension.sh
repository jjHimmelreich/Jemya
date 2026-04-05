#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EXT_DIR="$SCRIPT_DIR/jam-ya-autofade-extension"
MANIFEST_FILE="$EXT_DIR/manifest.json"
EXT_VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$MANIFEST_FILE" | head -n 1)"

if [[ -z "$EXT_VERSION" ]]; then
	echo "[build] Could not read extension version from $MANIFEST_FILE" >&2
	exit 1
fi

OUT_ZIP="$SCRIPT_DIR/jam-ya-autofade-v${EXT_VERSION}-release.zip"

# Usage:
#   ./build_chrome_extension.sh
#   ./build_chrome_extension.sh --with-frontend-build
#   RUN_FRONTEND_BUILD=1 ./build_chrome_extension.sh
RUN_FRONTEND_BUILD="${RUN_FRONTEND_BUILD:-0}"
if [[ "${1:-}" == "--with-frontend-build" ]]; then
	RUN_FRONTEND_BUILD="1"
fi

if [[ "$RUN_FRONTEND_BUILD" == "1" ]]; then
	echo "[build] Running frontend production build..."
	(
		cd "$REPO_ROOT/frontend"
		npm run build
	)
fi

echo "[build] Packaging Chrome extension..."
(
	cd "$EXT_DIR"
	rm -f "$OUT_ZIP"
	zip -r "$OUT_ZIP" . \
		--exclude "screenshots/*" \
		--exclude "*.git*" \
		--exclude "*.DS_Store"
)

echo "[build] Done: $OUT_ZIP"