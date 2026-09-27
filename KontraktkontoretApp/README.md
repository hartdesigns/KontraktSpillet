# Kontraktkontoret — iPad-app

En færdig til App Store klar version af spillet i `../index.html`. Appen er en tynd Swift-wrapper (WKWebView) omkring spillet — selve spillet er uændret undtagen tre ting:

- **Fonts er indlejret** — de 16 WOFF2-filer, som web-versionen loader fra Google Fonts, ligger som base64 inde i `Kontraktkontoret/Resources/game.html`. Appen virker derfor **100 % offline** og indsamler **ingen data** — det bedste mulige privatliv for en børneapp.
- **Zoom er slået fra** (viewport + `touch-action`), så layoutet er stabilt på iPad.
- **Ingen tekstvalg / tryk-længde-menu** — spillet skal føles som et spil, ikke en webside.
- En tekst er justeret: "gemmes automatisk **i browseren**" → "gemmes automatisk".

Den oprindelige web-version (`index.html`) er **ikke** rørt ved.

## Filer

| Sti | Indhold |
|---|---|
| `Kontraktkontoret/KontraktkontoretApp.swift` | Appen (SwiftUI, én fil) |
| `Kontraktkontoret/GameView.swift` | WKWebView-wrapperen + "papir"-baggrunden |
| `Kontraktkontoret/Resources/game.html` | Spillet med indlejrede fonts (genereret fil, ~1 MB) |
| `Kontraktkontoret/Assets.xcassets/` | App-ikon + launch-farve |
| `Kontraktkontoret/Info.plist` | Metadata: dansk, alle iPad-orienteringer, iPad-kun |
| `project.yml` | XcodeGen-spec — **projektet genereres fra denne fil** |
| `Tools/embed-fonts.py` | Regenererer `game.html` ud fra `index.html` |
| `Tools/AppIcon.svg` + `Tools/make-icon.sh` | App-ikonet: Chef Bo med GODKENDT-stempel (1024×1024) |

> `.xcodeproj`-filen er genereret af [XcodeGen](https://github.com/yonaskolb/XcodeGen). Rediger `project.yml` og kør `xcodegen generate` — ikke pbxproj'et.

## Kør det lokalt

1. Åbn `Kontraktkontoret.xcodeproj` i Xcode.
2. **Signing & Capabilities**: Vælg dit eget team. (Et gratis Apple-ID er nok til testing; til selve App Store kræves et betalende Developer-konto — se nedenfor.)
3. Vælg en iPad-simulator og tryk **⌘R**.

## Hvis du opdaterer spillet (index.html)

```bash
cd KontraktkontoretApp
python3 Tools/embed-fonts.py ../index.html Kontraktkontoret/Resources/game.html
```

(Det kræver internet den ene gang for at hente fonts fra Google Fonts. Derefter er alt offline igen.)

Til et nyt app-ikon (ret i `Tools/AppIcon.svg`, kræver Google Chrome):

```bash
sh Tools/make-icon.sh Kontraktkontoret/Assets.xcassets/AppIcon.appiconset/AppIcon.png
```

## Udgiv i App Store (gratis app)

### 1. Developer-konto
Du skal bruge en **Apple Developer Program**-konto (99 USD/år) for at kunne udgive. Opret den på <https://developer.apple.com/programs/>. Med et almindeligt Apple-ID kan du derimod teste frit på simulator og egen enhed.

### 2. Bundle-ID og signering
I Xcode: **Target → Signing & Capabilities** → vælg din konto. Bundle-ID'en er `dk.hartdesigns.kontraktkontoret` — skift den, hvis den kolliderer med noget, du allerede har registreret.

### 3. Arkivér
**Product → Archive** i Xcode (vælg "Any iOS Device (arm64)") → **Distribute App → App Store Connect** → følg skridtene. Appen lander så i App Store Connect.

### 4. App Store Connect (appstoreconnect.apple.com)
- **Mine apps → + → Ny app** → platform **iPad**
- **Navn**: `Kontraktkontoret` (16 tegn, inden for 30-tegns-grænsen)
- **Sprog**: Dansk
- **Pris og tilgængelighed**: **Gratis** + Danmark (eller hele verden)
- **Aldersvurdering**: **4+** — spillet indeholder intet voldeligt, sordid eller andet, der giver højere rating. Ingen købeknaper, ingen chat, ingen socialt.
- **App-privatliv**: **"Ingen data indsamles"** — appen er fuldt offline: ingen netværk, ingen analytics, ingen reklamer. (Derfor skal du heller ikke uploade en privatlivspolitik.)
- **Kategorier**: **Uddannelse** (og/eller underholdning).
  - **Tippet: Vælg "Børn"-kategorien** — appen leverer fuldt op til kravene: ingen reklamer, ingen in-app-køb, ingen sociale funktioner, ingen links ud af appen, og al indhold er fastlåst i appen.
- **Indhold rettigheder**: Intet tredjepartsindhold at godkende.

### 5. Skærmbilleder (krav for iPad-app)
Kør appen i simulatoren og tag skærmbilleder i de krævede størrelser:

```bash
# 11" iPad: 1668 × 2388 px    |    12.9"/13" iPad: 2048 × 2732 px
xcrun simctl io <enheds-id> screenshot billede.png
```

(`xcrun simctl list devices` viser ids. Simulatoren renderer i netop den pixelstørrelse, App Store kræver.)

### 6. App-ikon til butikken
`AppIcon.png` i asset-kataloget er allerede **1024×1024 uden afrunding** — præcis det, App Store Connect kræver til butiksikonet.

### 7. Indsend til review
Skriv i **review-bemærkningen** (også på engelsk), fx:

> Kontraktkontoret is a fully offline, single-player office game for kids.
> Players read customer orders, fill in contracts and get them stamped
> by the office boss. No network access, no ads, no in-app purchases,
> no user-generated content. Progress is saved privately on the device.

Og så: **Submit**.

## Bemærkninger

- **"Designed for iPad"**: Appen er målrettet iPad (`TARGETED_DEVICE_FAMILY = 2`). Den dukker alligevel automatisk op på iPhone i App Store som "Designed for iPad". Vil du støtte iPhone nativt, så sæt `TARGETED_DEVICE_FAMILY` til `1,2` i Xcode (Target → General).
- **Spar for livet**: Spillets save ligger i WebKit's lager på enheden. Hvis barnet sletter appen, forsvinder fremskridtet — det er den eksisterende adfærd i spillet (localStorage).
- **Minimum iOS 15** — dækker de fleste skolers/børnenes iPads (2017+).
