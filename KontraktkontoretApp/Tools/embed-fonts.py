#!/usr/bin/env python3
"""Embedder Google Fonts som base64-data-URI'er i spillet, så det kører 100% offline.

Bruges til at generere App/Resources/game.html fra index.html.
"""
import base64
import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")

# Kilde: index.html (Google Fonts <link>)
GAME_URL = ("https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700"
            "&family=Nunito:wght@600;700;800&family=Patrick+Hand&family=Caveat:wght@600"
            "&family=Gochi+Hand&family=Special+Elite&family=Permanent+Marker"
            "&family=Courier+Prime:wght@700&family=Indie+Flower&display=swap")

# Dansk dækker med 'latin' (æ ø å) + 'latin-ext' (helt sikkerhed).
KEEP_RANGES = (
    "U+0000-00FF",  # latin
    "U+0100-02BA",  # latin-ext
)


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=60).read()
    return data if binary else data.decode("utf-8")


def main(src_path, out_path):
    html = open(src_path, encoding="utf-8").read()

    css = fetch(GAME_URL)

    # Splitt css'en i @font-face-blocke
    blocks = re.findall(r"@font-face\s*\{[^}]*\}", css)
    if not blocks:
        sys.exit("Kunne ikke finde @font-face-blocke i Google Fonts CSS")

    new_blocks, seen_urls = [], {}
    for b in blocks:
        m = re.search(r"unicode-range:\s*([^;]+);", b)
        if not m:
            continue
        rng = m.group(1)
        if not any(rng.startswith(k) for k in KEEP_RANGES):
            continue  # skip cyrillic, greek, vietnamese, hebrew m.m.
        um = re.search(r"url\((https://[^)]+)\)", b)
        if not um:
            continue
        url = um.group(1)
        if url not in seen_urls:
            b64 = base64.b64encode(fetch(url, binary=True)).decode("ascii")
            seen_urls[url] = "data:font/woff2;base64," + b64
        new_blocks.append(b.replace(url, seen_urls[url]))

    style = "<style>\n/* Fonts er indlejret, så spillet kører offline */\n" + "\n".join(new_blocks) + "\n</style>\n"

    # Erstatt <link>-tagene (3 stk) med style-blokken
    links = re.findall(r'<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>\n?', html)
    if len(links) != 3:
        sys.exit(f"Forventede 3 Google Fonts <link>-tags, fandt {len(links)}")
    for i, l in enumerate(links):
        html = html.replace(l, style if i == 0 else "", 1)

    # App-ordvalg: "i browseren" giver ingen mening i en app
    html = html.replace(
        "Spillet gemmes automatisk i browseren.",
        "Spillet gemmes automatisk.",
        1,
    )

    # Viewport: spild ikke tid med zoom (det ødelægger spillets layout)
    html = html.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">',
        1,
    )

    # iPad-politser: ingen tekstvalg/kallout, ingen double-tap-zoom, ingen gummiband
    guard = """<style>
/* App-politser (indspredes i spillet) */
html,body{-webkit-user-select:none;-moz-user-select:none;user-select:none;-webkit-touch-callout:none}
*{touch-action:manipulation}
input{-webkit-user-select:text;user-select:text}
</style>
</head>"""
    html = html.replace("</head>", guard, 1)

    open(out_path, "w", encoding="utf-8").write(html)
    kb = len(html.encode("utf-8")) / 1024
    print(f"OK: {len(new_blocks)} @font-face-blocke, {len(seen_urls)} unikke woff2-filer ({kb:.0f} kB i alt) -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
