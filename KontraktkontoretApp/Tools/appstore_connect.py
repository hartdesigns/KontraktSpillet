#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fylder App Store Connect ud via App Store Connect API.

Forudsætninger (one-time, manuelt):
  1. Apple Developer-konto (krav 1 i README.md)
  2. API-nøgle oprettet i appstoreconnect.apple.com (Brugere og adgang → Integrationer → Nøgler)
     → udfyld asc/config.json
  3. App-optagelsen er oprettet i webbet (Apps → + → Ny app)

Brug:
  python3 Tools/appstore_connect.py check     # vis appens status (ændrer intet)
  python3 Tools/appstore_connect.py setup     # fyld alle metadata ud (idempotent)
  python3 Tools/appstore_connect.py submit    # tilknyt build + indsend til review
  python3 Tools/appstore_connect.py submit --send   # …og send den faktiske review-submission
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt  # pyjwt (ES256 via cryptography)

BASE = "https://api.appstoreconnect.apple.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # KontraktkontoretApp/

# ---------------------------------------------------------------------------
# Indhold (alt på dansk — klar til kopi-indsætning)
# ---------------------------------------------------------------------------
NAME = "Kontraktkontoret"
SUBTITLE = "Læs. Udfyld. Stempel."
KEYWORDS = "kontor, kontrakt, læsning, stempel, chef, papir, job, skole, børn, leg"
PROMO = "Dit allerførste job! Læs kunderne, udfyld kontrakter og få dem stemplet af den lidt tossede Chef Bo."
DESCRIPTION = """Har du nogensinde drømt om at arbejde på et kontor? Nu kan du — i Kontraktkontoret, dit allerførste rigtige job!

Du er den nye medarbejder på et lille kontor, hvor papiret er i højsæde. Kunderne stormer ind med hver sin sag, og dit job er at læse deres sedge, udfylde kontrakten helt rigtigt — og så vente spændt på, at Chef Bo slår sit store stempel.

SÅDAN VIRKER DIT JOB:
• Læs kunden og talebøblerne GODT efter. Også da, når ordene pludselig skifter mening!
• Udfyld kontrakten med rigtigt navn, ydelse, varighed, dato og pris.
• Chef Bo undersøger det hele gennem sit forstørrelsesglas.
• GODKENDT giver penge og stjerner — og penge giver pynt.
• I kontorbutikken kan du købe kaffemaskiner, kaktusser, plakater og meget mere, som du kan pynte dit kontor med.

Hver dag kommer nye kunder — og de bliver mere og mere kræsne. Hvor langt kan du nå?

PERFEKT TIL BØRN:
• Øver læsning, opmærksomhed og tålmodighed — på en sjov og blid måde.
• 100 % offline: Ingen internetforbindelse, ingen reklamer, ingen køb, ingen chat. Alt indhold medfølger appen.
• Ingen rigtige tabere: Der er aldrig nogen, der taber — der er bare flere kunder, du kan hjælpe.

Godt arbejde, medarbejder!"""

REVIEW_NOTES = """Single-player, fully offline office game for kids. The player reads a customer's order, fills in a contract with the correct details, and the office boss stamps it. The app is 100% offline: no network access, no ads, no in-app purchases, no social features, no sign-in. Progress is saved on the device. Nothing to configure — just start playing.

Enkeltspiller-kontorspil for børn, fuldt offline. Spilleren læser en kundes bestilling, udfylder en kontrakt med de rette oplysninger, og kontorchefen stempler den. Ingen netværk, reklamer, køb eller sociale funktioner. Fremskridt gemmes på enheden."""

# Aldersvurdering: alt "Ingen" → 4+
AGE_RATING_ALL_NONE = {
    "advertising": False,
    "alcoholTobaccoOrDrugUseOrReferences": "NONE",
    "contests": "NONE",
    "gambling": False,
    "gamblingSimulated": "NONE",
    "gunsOrOtherWeapons": "NONE",
    "healthOrWellnessTopics": False,
    "kidsAgeBand": "FIVE_AND_UNDER",
    "lootBox": False,
    "medicalOrTreatmentInformation": "NONE",
    "messagingAndChat": False,
    "parentalControls": False,
    "profanityOrCrudeHumor": "NONE",
    "ageAssurance": False,
    "sexualContentGraphicAndNudity": "NONE",
    "sexualContentOrNudity": "NONE",
    "horrorOrFearThemes": "NONE",
    "matureOrSuggestiveThemes": "NONE",
    "unrestrictedWebAccess": False,
    "userGeneratedContent": False,
    "violenceCartoonOrFantasy": "NONE",
    "violenceRealisticProlongedGraphicOrSadistic": "NONE",
    "violenceRealistic": "NONE",
    # NB: ageRatingOverride (deprecated) må IKKE sættes samtidig med V2.
    "ageRatingOverrideV2": "NONE",
    "koreaAgeRatingOverride": "NONE",
}

# Webbet repræsenterer "dansk" som "da" (ikke "da-DK").
LOCALE = "da"

# Skærmbilleder: (filnavn i Screenshots/, display-type i App Store)
SCREENSHOTS = [
    ("ipad-11-titel.png", "APP_IPAD_PRO_3GEN_11", "APP_IPAD_PRO_11"),
    ("ipad-11-intro.png", "APP_IPAD_PRO_3GEN_11", "APP_IPAD_PRO_11"),
    ("ipad-11-kontor.png", "APP_IPAD_PRO_3GEN_11", "APP_IPAD_PRO_11"),
    ("ipad-11-butik.png", "APP_IPAD_PRO_3GEN_11", "APP_IPAD_PRO_11"),
    ("ipad-13-titel.png", "APP_IPAD_PRO_129", "APP_IPAD_PRO_13"),
    ("ipad-13-intro.png", "APP_IPAD_PRO_129", "APP_IPAD_PRO_13"),
    ("ipad-13-kontor.png", "APP_IPAD_PRO_129", "APP_IPAD_PRO_13"),
    ("ipad-13-butik.png", "APP_IPAD_PRO_129", "APP_IPAD_PRO_13"),
]


# ---------------------------------------------------------------------------
# Konfiguration + API-klient
# ---------------------------------------------------------------------------
CFG_PATH = os.path.join(ROOT, "asc", "config.json")


def load_config():
    path = CFG_PATH
    if not os.path.exists(path):
        sys.exit(
            "Fandt ingen asc/config.json. Kopier asc/config.example.json til "
            "asc/config.json og udfyld issuerId, keyId, privateKey og contactEmail."
        )
    cfg = json.load(open(path))
    if "FILL" in str(cfg.get("issuerId", "")):
        sys.exit("asc/config.json er kun skabelonen — udfyld nøgle- og kontakt-oplysningerne.")
    return cfg


class Api:
    def __init__(self, cfg):
        self.cfg = cfg
        self.token = None
        self.token_exp = 0
        self.failures = []   # trin der fejlede (med Apple's fejlbesked)
        self.wins = []       # trin der lykkedes
        self.manual = []     # ting brugeren skal gøre i webbet

    def _new_token(self):
        now = int(time.time())
        key = self.cfg["privateKey"]
        if not key.startswith("-----"):
            p = key if os.path.isabs(key) else os.path.join(os.path.dirname(CFG_PATH), key)
            p = os.path.expanduser(p)
            if not os.path.exists(p):
                p = os.path.join(HERE, "..", "asc", key)
            key = open(p).read()
        # NB: Den nye IRIS-API kræver 'aud' i PAYLOAD, ikke i header
        # (header-aud giver 401 NOT_AUTHORIZED selv med korrekt nøgle).
        self.token = jwt.encode(
            {"iss": self.cfg["issuerId"], "iat": now - 10, "exp": now + 900,
             "aud": "appstoreconnect-v1"},
            key, algorithm="ES256",
            headers={"kid": self.cfg["keyId"]})

    def call(self, method, path, body=None):
        if self.token is None or time.time() > self.token_exp - 120:
            self._new_token()
            self.token_exp = int(time.time()) + 900
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            BASE + path, data=data, method=method,
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"errors": [{"code": str(e.code), "detail": raw[:400]}]}
            return e.code, payload
        except Exception as e:
            return 599, {"errors": [{"code": "NET", "detail": str(e)}]}

    def step(self, label, method, path, body=None, manual_hint=None, ok_codes=(200, 201, 204)):
        """Kør et trin; fortsæt ved fejl med en klar besked."""
        code, payload = self.call(method, path, body)
        if code in ok_codes:
            self.wins.append(label)
            return True, payload
        detail = "; ".join(
            f"{err.get('code', '?')}: {err.get('detail') or err.get('title') or '?'}"
            for err in payload.get("errors", [])[:3]) or f"HTTP {code}"
        print(f"  ✗ {label}: {detail[:220]}")
        self.failures.append((label, detail))
        if manual_hint:
            self.manual.append(manual_hint)
        return False, payload

    def summary(self):
        print("\n" + "=" * 62)
        print(f"OK ({len(self.wins)}):")
        for w in self.wins:
            print(f"  ✓ {w}")
        if self.failures:
            print(f"Fejl ({len(self.failures)}):")
            for label, d in self.failures:
                print(f"  ✗ {label}")
        if self.manual:
            print("\nGør selv i webbet (appstoreconnect.apple.com):")
            for m in dict.fromkeys(self.manual):
                print(f"  → {m}")
        print("=" * 62)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def get_one(api, path):
    code, payload = api.call("GET", path)
    if code != 200:
        return None
    return payload.get("data") or []


def find_app(api):
    code, payload = api.call("GET", "/apps?filter[bundleId]=" + urllib.parse.quote(api.cfg["bundleId"]))
    if code != 200:
        api.failures.append(("find-app", f"HTTP {code}: {json.dumps(payload.get('errors', []))[:200]}"))
        api.manual.append("Tjek at app-optagelsen findes i webbet (Apps → " + api.cfg["bundleId"] + ") og at API-nøglen har tilstrækkelig rolle (App Manager eller Admin).")
        return None
    items = payload.get("data") or []
    if not items:
        api.failures.append(("find-app", "ingen app med bundle ID " + api.cfg["bundleId"]))
        api.manual.append("Opret app-optagelsen i webbet: Apps → + → Ny app (platform: iPad, bundle ID: " + api.cfg["bundleId"] + ", sprog: dansk, SKU: kontraktkontoret-1).")
        return None
    app = items[0]
    print(f"App: {app['id']} ({api.cfg['bundleId']})")
    return app


def get_version(api, app_id):
    want = api.cfg.get("version", "1.0")
    data = get_one(api, f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS")
    if not data:
        return None
    for v in data:
        if v.get("attributes", {}).get("versionString") == want:
            return v
    return data[0] if len(data) == 1 else None


# ---------------------------------------------------------------------------
# Trin: setup
# ---------------------------------------------------------------------------
def setup(api):
    print("Søger efter app …")
    app = find_app(api)
    if not app:
        api.summary()
        return
    app_id = app["id"]

    version = get_version(api, app_id)
    if not version:
        api.failures.append(("version", "ingen App Store-version fundet"))
        api.summary()
        return
    vid = version["id"]
    print(f"Version: {version['attributes'].get('versionString')} ({vid}), "
          f"status: {version['attributes'].get('appStoreState')}")

    # --- Version-lokalisering (beskrivelse, nøgleord, markedsføringstekst) ---
    locs = get_one(api, f"/appStoreVersions/{vid}/appStoreVersionLocalizations") or []
    loc = next((l for l in locs if l.get("attributes", {}).get("locale") in (LOCALE, "da-DK")), None)
    if loc is None:
        ok, payload = api.step(
            "opret dansk lokalisation på versionen",
            "POST", f"/appStoreVersions/{vid}/relationships/appStoreVersionLocalizations",
            {"data": {"type": "appStoreVersionLocalizations",
                       "attributes": {"locale": LOCALE},
                       "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": vid}}}}},
            "Opret en dansk lokalisation i webbet (App-info → tilføj sprog: dansk).")
        if ok:
            loc = payload.get("data")
    if loc:
        lid = loc["id"]
        api.step(
            "tekster på versionen (beskrivelse, nøgleord, markedsføring)",
            "PATCH", f"/appStoreVersionLocalizations/{lid}",
            {"data": {"type": "appStoreVersionLocalizations", "id": lid,
                       "attributes": {"description": DESCRIPTION,
                                      "keywords": KEYWORDS,
                                      "promotionalText": PROMO}}},
            "Fyld beskrivelse/nøgleord ud i webbet (App-info).")
    else:
        api.manual.append("Fyld beskrivelse/nøgleord ud i webbet (App-info) — API'et fandt ikke lokalisationen.")

    # --- App-info (navn + undertitel) ---
    infos = get_one(api, f"/apps/{app_id}/appInfos") or []
    if infos:
        aid = infos[0]["id"]
        ilocs = get_one(api, f"/appInfos/{aid}/appInfoLocalizations") or []
        iloc = next((l for l in ilocs if l.get("attributes", {}).get("locale") in (LOCALE, "da-DK")), None)
        if iloc:
            # PATCH med kun attributter (API'et afviser relations-feltet her)
            patch_body = {"data": {"type": "appInfoLocalizations", "id": iloc["id"],
                                    "attributes": {"name": NAME, "subtitle": SUBTITLE}}}
            api.step("app-navn + undertitel", "PATCH", f"/appInfoLocalizations/{iloc['id']}", patch_body,
                     "Sæt app-navn/undertitel i webbet (App-info).")
        else:
            api.step("opret app-navn + undertitel",
                     "POST", f"/appInfos/{aid}/relationships/appInfoLocalizations",
                     {"data": {"type": "appInfoLocalizations",
                                "attributes": {"locale": LOCALE, "name": NAME, "subtitle": SUBTITLE}}},
                     "Sæt app-navn/undertitel i webbet (App-info).")

        # --- Aldersvurdering (alt "Ingen" → 4+) ---
        decls = get_one(api, f"/appInfos/{aid}/ageRatingDeclaration")
        if decls:
            api.step("aldersvurdering (4+, alt 'Ingen')",
                     "PATCH", f"/ageRatingDeclarations/{decls[0]['id'] if isinstance(decls, list) else decls['id']}",
                     {"data": {"type": "ageRatingDeclarations",
                               "id": decls[0]["id"] if isinstance(decls, list) else decls["id"],
                               "attributes": AGE_RATING_ALL_NONE}},
                     "Svar 'Ingen' på alle spørgsmål i webbet (Aldersvurdering) → 4+.")
        else:
            api.step("opret aldersvurdering (4+, alt 'Ingen')",
                     "POST", f"/appInfos/{aid}/relationships/ageRatingDeclaration",
                     {"data": {"type": "ageRatingDeclarations", "attributes": AGE_RATING_ALL_NONE}},
                     "Udfyld aldersvurdering i webbet: svar 'Ingen' på alt → 4+.")

        # --- Kategorier (kun hvis der er IDs i config) ---
        for key, rel in (("primaryCategoryId", "primaryCategory"),
                         ("secondaryCategoryId", "secondaryCategory")):
            cid = api.cfg.get(key)
            if cid is not None:
                api.step(f"kategori ({rel} = {cid})",
                         "POST", f"/appInfos/{aid}/relationships/{rel}",
                         {"data": {"type": "appCategories", "id": str(cid)}},
                         f"Vælg kategorien i webbet (App-info) — den korrekte ID for {rel} er ikke kendt.")

    # --- Privatliv (Ingen data indsamles) ---
    # Ressourcen findes ikke i den offentlige API (verificeret: 404 på alle veje) —
    # det er et fast manuelt trin i webbet.
    api.manual.append("App-privatliv i webbet: vælg 'Ingen data indsamles' (kryds af) og gem.")

    # --- Tilgængelighed: Danmark (kun hvis config siger ja) ---
    den = api.cfg.get("territoryDenmarkId")
    if den is None and api.cfg.get("denmarkOnly"):
        data = get_one(api, "/territories?filter[countryCode]=DK")
        den = data[0]["id"] if data else None
        if den:
            api.cfg["territoryDenmarkId"] = int(den)
    if den is not None:
        existing = get_one(api, f"/apps/{app_id}/appAvailabilityV2")
        if existing:
            api.wins.append("tilgængelighed findes allerede")
        else:
            api.step(
                "tilgængelighed: kun Danmark",
                "POST", "/appAvailabilities",
                {"data": {"type": "appAvailabilities",
                           "attributes": {"availableInNewTerritories": False},
                           "relationships": {
                               "app": {"type": "apps", "id": app_id},
                               "territoryAvailabilities": [
                                   {"type": "territoryAvailabilities", "id": str(den)}]}}},
                "Vælg 'Kun Danmark' under Tilgængelighed i webbet.")

    # --- Skærmbilleder ---
    do_screenshots(api, loc_id=next(
        (l["id"] for l in locs if l.get("attributes", {}).get("locale") in (LOCALE, "da-DK")), None))

    # --- Review-info (kontakt + bemærkninger) ---
    # Oprettes først uden relation, linkes bagefter via versions-relations.
    if "FILL" in str(api.cfg.get("contactEmail", "")):
        api.manual.append("Giv os en kontakt-e-mail (asc/config.json), eller udfyld 'Info til review' i webbet.")
    else:
        ok, payload = api.step(
            "review-info (kontakt + bemærkninger)",
            "POST", "/appStoreReviewDetails",
            {"data": {"type": "appStoreReviewDetails",
                       "attributes": {"contactFirstName": "Magnus",
                                      "contactLastName": "Skou Andersen",
                                      "contactEmail": api.cfg["contactEmail"],
                                      "contactPhone": api.cfg.get("contactPhone", "+45 53373006"),
                                      "demoAccountRequired": False,
                                      "notes": REVIEW_NOTES},
                       "relationships": {"appStoreVersion":
                                          {"data": {"type": "appStoreVersions", "id": vid}}}}},
            "Udfyld 'Info til review' i webbet (navn, e-mail, telefon + bemærkninger).")
        if ok:
            new = payload.get("data") or {}
            if new.get("id"):
                api.step("link review-info til versionen",
                         "POST", f"/appStoreVersions/{vid}/relationships/appStoreReviewDetail",
                         {"data": {"type": "appStoreReviewDetails", "id": new["id"]}},
                         "Udfyld 'Info til review' i webbet (e-mail + bemærkninger).")
            else:
                api.manual.append("Udfyld 'Info til review' i webbet (e-mail + bemærkninger).")

    # --- Faste manuelle trin (kan ikke laves via API) ---
    api.manual.append("Kategorier: vælg Uddannelse (primær) + Underholdning (sekundær) i App-info, hvis det ikke er sat.")
    api.manual.append("App-ikon (1024 px): upload Assets.xcassets/AppIcon.appiconset/AppIcon.png i webbet.")
    api.manual.append("Pris: vælg 'Gratis' (Pris og tilgængelighed) — det er ofte forudvalgt.")

    api.summary()


def do_screenshots(api, loc_id):
    if not loc_id:
        api.manual.append("Skærmbilleder mangler — upload dem i webbet (App-info), eller kør setup igen.")
        return
    shot_dir = os.path.join(ROOT, "Screenshots")
    files = [f for f, *_ in SCREENSHOTS if os.path.exists(os.path.join(shot_dir, f))]
    if not files:
        api.manual.append(f"Skærmbilleder mangler i {shot_dir} — kør Tools/make-screenshots.sh først.")
        return

    # Gruppér per display-type
    groups = {}
    for f, dt_main, dt_alt in SCREENSHOTS:
        if os.path.exists(os.path.join(shot_dir, f)):
            groups.setdefault(dt_main, (dt_alt, []))[1].append(f)

    for dt_main, (dt_alt, fs) in groups.items():
        # Find/ophavn sæt for display-typen
        sets = get_one(api, f"/appStoreVersionLocalizations/{loc_id}/appScreenshotSets") or []
        sset = None
        for s in sets:
            if s.get("attributes", {}).get("screenshotDisplayType") in (dt_main, dt_alt):
                sset = s
        if sset is None:
            for dt in (dt_main, dt_alt):
                ok, payload = api.step(
                    f"skærmbillede-sæt {dt}",
                    "POST", "/appScreenshotSets",
                    {"data": {"type": "appScreenshotSets",
                               "attributes": {"screenshotDisplayType": dt},
                               "relationships": {"appStoreVersionLocalization":
                                                  {"data": {"type": "appStoreVersionLocalizations", "id": loc_id}}}}},
                    "Upload skærmbillederne i webbet (App-info) for denne skærmstørrelse.")
                if ok:
                    sset = (payload.get("data") or [None])[0] if isinstance(payload.get("data"), list) else payload.get("data")
                    if sset:
                        break
        if sset is None:
            continue
        sid = sset["id"]

        for f in fs:
            path = os.path.join(shot_dir, f)
            size = os.path.getsize(path)
            ok, payload = api.step(
                f"skærmbillede {f} ({size // 1024} kB)",
                "POST", "/appScreenshots",
                {"data": {"type": "appScreenshots",
                           "attributes": {"fileName": f, "fileSize": size},
                           "relationships": {"appScreenshotSet":
                                              {"data": {"type": "appScreenshotSets", "id": sid}}}}},
                None)
            if not ok:
                # Ældre API-format: base64-feltet 'file'
                ok, payload = api.step(
                    f"skærmbillede {f} (base64-fallback)",
                    "POST", "/appScreenshots",
                    {"data": {"type": "appScreenshots",
                               "attributes": {"fileName": f, "fileSize": size,
                                              "file": base64.b64encode(open(path, "rb").read()).decode()},
                               "relationships": {"appScreenshotSet":
                                                  {"data": {"type": "appScreenshotSets", "id": sid}}}}},
                    None)
            if ok:
                shot = payload.get("data")
                if isinstance(shot, list):
                    shot = shot[0] if shot else None
                if shot:
                    upload_bytes(api, shot, open(path, "rb").read())


def upload_bytes(api, shot, raw):
    """Upload billedets bytes via signed URL'er (uploadOperations), hvis der er nogle.

    VIGTIGT: efter PUT'en skal uploaden bekræftes med PATCH {uploaded: true} —
    ellers ligger billedet i Apples storage, men skærmbilledet står i
    AWAITING_UPLOAD for evigt (API'et flipper ikke status af sig selv).
    """
    ops = shot.get("attributes", {}).get("uploadOperations") or []
    for op in ops:
        url = op.get("url")
        if not url:
            continue
        headers = {h["name"]: h.get("value", "") for h in (op.get("requestHeaders") or [])}
        req = urllib.request.Request(url, data=raw, method=op.get("method", "PUT"), headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                print(f"    upload {r.status}")
        except Exception as e:
            api.failures.append((f"upload {shot.get('id')}", str(e)))
    sid = shot.get("id")
    if sid:
        code, payload = api.call("PATCH", f"/appScreenshots/{sid}",
                                 {"data": {"type": "appScreenshots", "id": sid,
                                           "attributes": {"uploaded": True}}})
        if code == 200:
            print("    upload bekræftet (uploaded=true)")
        else:
            err = (payload.get("errors") or [{}])[0]
            print(f"    WARNING: bekræftelse fejlede: {err.get('detail', '')[:120]}")
            api.failures.append((f"upload-bekræftelse {sid}", err.get("detail", "")))


# ---------------------------------------------------------------------------
# Trin: submit (tilknyt build + review-submission)
# ---------------------------------------------------------------------------
def submit(api, send=False):
    print("Søger efter app …")
    app = find_app(api)
    if not app:
        api.summary()
        return
    app_id = app["id"]
    version = get_version(api, app_id)
    if not version:
        api.failures.append(("version", "ingen version fundet"))
        api.summary()
        return
    vid = version["id"]

    # Find build (seneste upload)
    code, payload = api.call("GET", f"/apps/{app_id}/builds")
    builds = payload.get("data") or []
    if not builds:
        api.failures.append(("build", "ingen build i App Store Connect"))
        api.manual.append("Archive + Distribute i Xcode (README.md, krav 3) — så opdateres dette trin automatisk.")
        api.summary()
        return
    build = max(builds, key=lambda b: b.get("attributes", {}).get("uploadedDate") or "")
    state = build.get("attributes", {}).get("processingState")
    print(f"Seneste build: {build['attributes'].get('version')} "
          f"({build['attributes'].get('buildNumber')}) — {state}")
    if state != "VALID":
        api.failures.append(("build", f"bygge-{state} — vent indtil den er VALID og kør igen"))
        api.summary()
        return

    # Build linkes via PATCH på selve versionen (relationships/build tillader kun GET)
    api.step("tilknyt build til versionen",
             "PATCH", f"/appStoreVersions/{vid}",
             {"data": {"type": "appStoreVersions", "id": vid,
                        "relationships": {"build": {"data": {"type": "builds", "id": build["id"]}}}}},
             "Vælg bygget under 'Byg' i webbet.")

    # Review-submission
    data = get_one(api, f"/apps/{app_id}/reviewSubmissions?filter[state]=READY_FOR_REVIEW&filter[platform]=IOS")
    sub = None
    if data:
        sub = data[0]
        print(f"Genbruger eksisterende submission ({sub['id']})")
    else:
        ok, payload = api.step("opret review-submission",
                               "POST", "/reviewSubmissions",
                               {"data": {"type": "reviewSubmissions",
                                         "attributes": {"platform": "IOS"},
                                         "relationships": {"app": {"data": {"type": "apps", "id": app_id}}}}},
                               "Klik 'Tilføj til review' i webbet.")
        if ok:
            sub = payload.get("data")
    if not sub:
        api.summary()
        return
    sid = sub["id"]

    # Tilknyt versionen
    items = get_one(api, f"/reviewSubmissions/{sid}/items") or []

    def has_version(i):
        rel = (i.get("relationships") or {}).get("appStoreVersion") or {}
        d = rel.get("data") or rel
        return d.get("id") == vid or (i.get("attributes") or {}).get("version") == vid

    if not any(has_version(i) for i in items):
        api.step("tilknyt versionen til submissionen",
                 "POST", "/reviewSubmissionItems",
                 {"data": {"type": "reviewSubmissionItems",
                            "relationships": {
                                "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sid}},
                                "appStoreVersion": {"data": {"type": "appStoreVersions", "id": vid}}}}},
                 "Vælg versionen i 'Indsendelser' i webbet.")

    if send:
        print("\n⚠️  Nu sendes appen til review hos Apple — dette kan ikke fortrydes.")
        api.step("INSENDELSE TIL REVIEW",
                 "PATCH", f"/reviewSubmissions/{sid}",
                 {"data": {"type": "reviewSubmissions", "id": sid,
                           "attributes": {"submitted": True}}},
                 "Klik 'Send til review' i webbet (Indsendelser).")
    else:
        print("\nAlt er klar (status: Ready for Review).")
        print("Kør med --send, når du vil sende den til Apple, eller klik 'Send til review' i webbet.")

    api.summary()


# ---------------------------------------------------------------------------
def check(api):
    print("Søger efter app …")
    app = find_app(api)
    if not app:
        api.summary()
        return
    app_id = app["id"]
    print(f"  navn: {app.get('attributes', {}).get('name')}  bundleId: {api.cfg['bundleId']}")
    for path, label in (
        (f"/apps/{app_id}/appStoreVersions?filter[platform]=IOS", "versioner"),
        (f"/apps/{app_id}/builds", "builds"),
        (f"/apps/{app_id}/appAvailabilityV2", "tilgængelighed"),
        (f"/apps/{app_id}/reviewSubmissions?filter[platform]=IOS", "indsendelser"),
    ):
        code, payload = api.call("GET", path)
        if code == 200:
            items = payload.get("data") or []
            print(f"  {label}: {len(items)}" + (
                f"  (første: {json.dumps(items[0].get('attributes', {}), ensure_ascii=False)[:120]})" if items else ""))
        else:
            print(f"  {label}: HTTP {code}")
    api.summary()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    mode = sys.argv[1]
    cfg = load_config()
    api = Api(cfg)
    if mode == "check":
        check(api)
    elif mode == "setup":
        setup(api)
    elif mode == "submit":
        submit(api, send="--send" in sys.argv)
    else:
        print(f"Ukendt mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
