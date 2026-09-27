#!/bin/sh
# Tegner app-ikonet (1024×1024, uden afrunding og uden alpha) ud fra Tools/AppIcon.svg.
# Chef Bo jubler, mens GODKENDT-stemplet smækker ned. Ret i AppIcon.svg og kør scriptet igen.
#
# Brug: sh Tools/make-icon.sh [out.png]
# Kræver Google Chrome (bruges uden vindue til at tegne SVG'en).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-AppIcon.png}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TMP="$(mktemp -d)"
{ printf '<!doctype html><html><head><style>html,body{margin:0}svg{display:block}</style></head><body>'
  cat "$DIR/AppIcon.svg"
  printf '</body></html>'; } > "$TMP/icon.html"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1024,1024 \
  --screenshot="$TMP/icon.png" "file://$TMP/icon.html" 2>/dev/null
cp "$TMP/icon.png" "$OUT"
rm -rf "$TMP"
echo "OK: skrev $OUT"
