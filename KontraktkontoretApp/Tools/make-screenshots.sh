#!/bin/bash
# Tager App Store-skærmbilleder fra iPad-simulatorer.
#
# Kører appen (og to "demo"-byggerier, der selv trykker på knapper) og
# optager 4 billeder pr. størrelse: titel, intro, kontor og butik.
# Resultatet lander i ../Screenshots/ (præcis de størrelser App Store Connect kræver:
# 11" = 1668×2388, 13" = 2048×2732).
#
# Forudsætning: Appen er bygget (xcodebuild eller Xcode).
set -euo pipefail
cd "$(dirname "$0")/.."

# Find den nyeste built .app
APP=$(ls -dt "$HOME"/Library/Developer/Xcode/DerivedData/Kontraktkontoret-*/Build/Products/Debug-iphonesimulator/Kontraktkontoret.app 2>/dev/null | head -1 || true)
[ -n "$APP" ] || { echo "Fejl: Ingen bygget app fundet. Byg den først (fx via xcodebuild)."; exit 1; }
echo "App: $APP"

sim_id() { xcrun simctl list devices | grep -E "$1" | head -1 | grep -oE '[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}' | head -1; }
S11=$(sim_id "iPad Pro 11-inch")
S13=$(sim_id "iPad Pro 13-inch")
[ -n "$S11" ] && [ -n "$S13" ] || { echo "Fejl: Manglende iPad Pro-simulatorer (11\"/13\")."; exit 1; }
echo "11\": $S11   13\": $S13"

OUT="$PWD/Screenshots"
mkdir -p "$OUT"

# Sluk eventuelle kørte simulatorer for rent bord
xcrun simctl list devices | grep -E "Booted" | grep -oE '[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}' | while read -r d; do
  xcrun simctl shutdown "$d" 2>/dev/null || true
done

# --- Demo-byggerier: samme app, men game.html med et autopilot-script, der selv trykker på knapper ---
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
python3 - "$APP" "$WORK" <<'EOF'
import re, shutil, sys
app, work = sys.argv[1], sys.argv[2]
html = open(app + "/game.html", encoding="utf-8").read()

def demo(clicks):
    js = "<script>\n(function(){\nfunction c(t){var b=document.querySelectorAll('button');for(var i=0;i<b.length;i++){if(b[i].textContent.indexOf(t)!==-1){b[i].click();return true}}return false}\n"
    for ms, t in clicks:
        js += "setTimeout(function(){c('%s')},%d);\n" % (t, ms)
    js += "})();\n</script>\n</body>"
    return html.replace("</body>", js, 1)

for name, clicks in [
    ("office", [(1200, "Start arbejdsdagen"), (5200, "Åbn skranken")]),
    ("shop",   [(1200, "Kontorbutikken")]),
]:
    d = work + "/" + name + ".app"
    shutil.copytree(app, d)
    open(d + "/game.html", "w", encoding="utf-8").write(demo(clicks))
    import subprocess
    subprocess.run(["codesign", "-s", "-", "--force", "--deep", d], check=True)
    print("demo-app:", d)
EOF

shot() { # $1=simulator  $2=app  $3=filnavn  $4=vent-sec
  xcrun simctl install "$1" "$2"
  xcrun simctl terminate "$1" dk.hartdesigns.kontraktkontoret 2>/dev/null || true
  xcrun simctl launch "$1" dk.hartdesigns.kontraktkontoret > /dev/null
  sleep "$4"
  xcrun simctl io "$1" screenshot "$3" > /dev/null
  echo "  $3"
}

boot_and_shoot() { # $1=simulator-id  $2=mappe-suffiks
  local sim=$1 suf=$2
  xcrun simctl boot "$sim"
  echo "== $suf =="
  shot "$sim" "$APP"           "$OUT/$suf-titel.png"  6
  shot "$sim" "$WORK/office.app" "$OUT/$suf-intro.png" 6   # viser intro (start klik ved 1.2s)
  shot "$sim" "$WORK/shop.app"   "$OUT/$suf-butik.png"  5
  # office: genstart demo-appen og vent længere, så skranken er åbnet
  xcrun simctl install "$sim" "$WORK/office.app"
  xcrun simctl terminate "$sim" dk.hartdesigns.kontraktkontoret 2>/dev/null || true
  xcrun simctl launch "$sim" dk.hartdesigns.kontraktkontoret > /dev/null
  sleep 13
  xcrun simctl io "$sim" screenshot "$OUT/$suf-kontor.png" > /dev/null
  echo "  $suf-kontor.png"
  # Stil den rigtige app tilbage (ingen skærmbillede — bare geninstaller og sluk)
  xcrun simctl install "$sim" "$APP"
  xcrun simctl terminate "$sim" dk.hartdesigns.kontraktkontoret 2>/dev/null || true
  xcrun simctl shutdown "$sim"
}

boot_and_shoot "$S11" "ipad-11"
boot_and_shoot "$S13" "ipad-13"

# M4-iPad-simulatorer renderer i en let højere opløsning (2420/2752) end
# App Stores krav (2388/2732) — skalér til præcis størrelse (< 1 %, usynligt).
echo "== Skalérer til App Store-størrelser =="
for f in "$OUT"/ipad-11-*.png; do sips -z 2388 1668 "$f" >/dev/null; done
for f in "$OUT"/ipad-13-*.png; do sips -z 2732 2048 "$f" >/dev/null; done

echo "== Størrelser =="
for f in "$OUT"/*.png; do
  sips -g pixelWidth -g pixelHeight "$f" | awk -v f="$f" '/pixel/{printf "%s: ", $2} END{print f}'
done
echo "Færdig: $OUT"
