#!/usr/bin/env python3
"""
VOKO Narrowcasting - Competitie Scraper & Parser
Haalt programma, uitslagen en standen op voor VOKO Oosterhout (CKM1R98):
1. Nevobo (volleybal.nl / api.nevobo.nl) voor alle Nevobo teams
2. ORV Breda (orvbreda.nl ajaxLeesWedstrijden) voor VOKO Dames 3 (2e klasse dames)
3. VOKO website (voko-oosterhout.nl/teamoverzicht) voor actuele teamfoto's
Genereert:
- uitslagen.json (uitslagen van de afgelopen 7 dagen + zaterdag live)
- programma.json (wedstrijden komende 7 dagen met zaal, veld en ranking)
- standen.json (4 categorieën: Heren, Dames, Jeugd, Volley Stars)
"""

import io
import json
import logging
import os
import re
import urllib.parse
import zipfile
from datetime import datetime, timedelta, date
from pathlib import Path
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

SCRIPT_DIR = Path(__file__).parent.resolve()
CACHE_DIR = SCRIPT_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Bestemmingen
UPLOADS_FILE = SCRIPT_DIR / "uitslagen.json"
PROGRAMMA_FILE = SCRIPT_DIR / "programma.json"
STANDEN_FILE = SCRIPT_DIR / "standen.json"
TEAM_PHOTOS_CACHE = CACHE_DIR / "team_photos.json"
STAND_XLSX_CACHE = CACHE_DIR / "stand.xlsx"
STAND_XLSX_URL = "https://api.nevobo.nl/export/vereniging/CKM1R98/stand.xlsx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DUTCH_DAYS = {
    0: "Maandag", 1: "Dinsdag", 2: "Woensdag", 3: "Donderdag",
    4: "Vrijdag", 5: "Zaterdag", 6: "Zondag"
}

DUTCH_MONTHS = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december"
}

DEFAULT_PLACEHOLDER_IMG = "https://www.voko-oosterhout.nl/back-site/upload/voko-oosterhout/teams/_800x600/placeholder_20241213222914264_20250817204009442.jpg"

NEVOBO_API_BASE = "https://api.nevobo.nl"
VERENIGING_IRI = "/relatiebeheer/verenigingen/ckm1r98"
ORV_BASE = "https://www.orvbreda.nl"


def format_dutch_date(dt: datetime | date) -> str:
    """Formatteert een datum naar 'Zaterdag 24 oktober 2026'."""
    day_name = DUTCH_DAYS.get(dt.weekday(), "")
    month_name = DUTCH_MONTHS.get(dt.month, "")
    return f"{day_name} {dt.day} {month_name}"


def normalize_team_name(name: str) -> str:
    """Standaardiseert teamnamen voor consistente vergelijking."""
    if not name:
        return ""
    n = name.strip()
    # Standaardiseer 'Voko' -> 'VOKO'
    n = re.sub(r"^voko\b", "VOKO", n, flags=re.IGNORECASE)
    # Standaardiseer 'D3' -> 'DS 3'
    n = re.sub(r"\bD3\b", "DS 3", n)
    n = re.sub(r"\bD2\b", "DS 2", n)
    n = re.sub(r"\bD1\b", "DS 1", n)
    n = re.sub(r"\bH1\b", "HS 1", n)
    n = re.sub(r"\bH2\b", "HS 2", n)
    n = re.sub(r"\bH3\b", "HS 3", n)
    n = re.sub(r"\bH4\b", "HS 4", n)
    n = re.sub(r"\bH5\b", "HS 5", n)
    return n


# -----------------------------------------------------------------------------
# 1. Teamfoto's van VOKO clubsite
# -----------------------------------------------------------------------------
def fetch_team_photos() -> dict[str, dict]:
    """
    Haalt de actuele teamfoto's op van https://www.voko-oosterhout.nl/teamoverzicht.
    Slaat op in team_photos.json met timestamp.
    """
    # Check cache als minder dan 24 uur oud
    if TEAM_PHOTOS_CACHE.exists():
        try:
            with open(TEAM_PHOTOS_CACHE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                cached_time = datetime.fromisoformat(cached.get("updated_at", "2000-01-01"))
                if datetime.now() - cached_time < timedelta(hours=24):
                    logging.info(f"Teamfoto's ingeladen uit cache ({len(cached.get('photos', {}))} teams).")
                    return cached.get("photos", {})
        except Exception as e:
            logging.warning(f"Kon teamfoto-cache niet lezen: {e}")

    logging.info("Ophalen van teamfoto's van www.voko-oosterhout.nl/teamoverzicht...")
    photos = {}
    try:
        resp = requests.get("https://www.voko-oosterhout.nl/teamoverzicht", headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            team_links = {}
            for a in soup.select(".team-overzicht a.team"):
                name = normalize_team_name(a.get_text(strip=True))
                href = a.get("href")
                if name and href:
                    team_links[name] = href

            for name, href in team_links.items():
                try:
                    t_resp = requests.get(href, headers=HEADERS, timeout=8)
                    if t_resp.status_code == 200:
                        t_soup = BeautifulSoup(t_resp.text, "html.parser")
                        img = t_soup.select_one("img.team_foto")
                        if img and img.get("src"):
                            src = img.get("src")
                            is_placeholder = "placeholder" in src.lower()
                            photos[name] = {
                                "url": src,
                                "is_placeholder": is_placeholder
                            }
                except Exception as err:
                    logging.warning(f"Fout bij ophalen foto voor {name}: {err}")
    except Exception as e:
        logging.warning(f"Fout bij openen teamoverzicht: {e}")

    # Zorg dat alle standaard VOKO teams aanwezig zijn
    standard_teams = [
        "VOKO HS 1", "VOKO HS 2", "VOKO HS 3", "VOKO HS 4", "VOKO HS 5",
        "VOKO DS 1", "VOKO DS 2", "VOKO DS 3",
        "VOKO MA 1", "VOKO MA 2", "VOKO MB 1", "VOKO MB 2", "VOKO MC 1", "VOKO MC 2",
        "Volley Stars"
    ]
    for st in standard_teams:
        if st not in photos:
            photos[st] = {
                "url": DEFAULT_PLACEHOLDER_IMG,
                "is_placeholder": True
            }

    with open(TEAM_PHOTOS_CACHE, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().isoformat(), "photos": photos}, f, ensure_ascii=False, indent=2)

    logging.info(f"{len(photos)} teamfoto's succesvol opgeslagen.")
    return photos


def get_team_photo(team_name: str, photos_map: dict) -> tuple[str, bool]:
    """Geeft de afbeeldings-URL en een boolean is_placeholder terug."""
    norm = normalize_team_name(team_name)
    for k, v in photos_map.items():
        if k.lower() == norm.lower() or k.lower() in norm.lower() or norm.lower() in k.lower():
            return v.get("url", DEFAULT_PLACEHOLDER_IMG), v.get("is_placeholder", True)
    return DEFAULT_PLACEHOLDER_IMG, True


# -----------------------------------------------------------------------------
# 2. Nevobo API & Poule-indelingen
# -----------------------------------------------------------------------------
def fetch_and_parse_stand_xlsx() -> dict[str, dict]:
    """
    Haalt de officiële stand.xlsx op van Nevobo en parseert deze.
    Bevat 100% actuele standen voor alle Nevobo teams (inclusief toernooien Volley Stars).
    """
    xlsx_bytes = None
    try:
        resp = requests.get(STAND_XLSX_URL, headers=HEADERS, timeout=12)
        if resp.status_code == 200 and len(resp.content) > 1000:
            xlsx_bytes = resp.content
            with open(STAND_XLSX_CACHE, "wb") as f:
                f.write(xlsx_bytes)
            logging.info("Nieuwe stand.xlsx succesvol opgehaald bij Nevobo en gecachet.")
    except Exception as e:
        logging.warning(f"Kon stand.xlsx niet live ophalen ({e}); gebruik cache indien aanwezig.")

    if not xlsx_bytes and STAND_XLSX_CACHE.exists():
        try:
            with open(STAND_XLSX_CACHE, "rb") as f:
                xlsx_bytes = f.read()
            logging.info("stand.xlsx ingeladen uit lokale cache.")
        except Exception as e:
            logging.warning(f"Kon stand.xlsx cache niet lezen: {e}")

    if not xlsx_bytes:
        return {}

    standings = {}
    try:
        with zipfile.ZipFile(io.BytesIO(xlsx_bytes), "r") as z:
            shared_strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in tree.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    t = si.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    shared_strings.append(t.text if t is not None else "")

            sheet_tree = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            rows = sheet_tree.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")

            current_team_header = ""
            current_poule_desc = ""

            for r in rows:
                cells = r.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
                row_vals = []
                for c in cells:
                    t = c.get("t")
                    v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    val = v.text if v is not None else ""
                    if t == "s" and val and val.isdigit() and int(val) < len(shared_strings):
                        val = shared_strings[int(val)]
                    row_vals.append(val)

                # Header van poule: [Teamnaam, Poule-omschrijving]
                if len(row_vals) == 2 and any(k in row_vals[1].lower() for k in ["competitie", "toernooi", "beker"]):
                    current_team_header = row_vals[0].strip()
                    current_poule_desc = row_vals[1].strip()
                    continue

                # Data rij: Ranking | Teamnaam | Wedstrijden | Punten | Sets voor | Sets tegen | ...
                if len(row_vals) >= 4 and row_vals[0].isdigit():
                    rank = int(row_vals[0])
                    team_naam = normalize_team_name(row_vals[1].strip())

                    # Check of het een VOKO team is
                    if "voko" in team_naam.lower():
                        clean_klasse = re.sub(r"^[A-Za-z0-9\-\s]+,\s*", "", current_poule_desc).strip()
                        is_beker = "beker" in current_poule_desc.lower()

                        if team_naam not in standings or not is_beker:
                            standings[team_naam] = {
                                "team": team_naam,
                                "positie": rank,
                                "positie_tekst": f"{rank}e",
                                "klasse": clean_klasse or current_poule_desc,
                                "stand_omschrijving": f"{rank}e in {clean_klasse}",
                                "gespeeld": int(row_vals[2]) if len(row_vals) > 2 and row_vals[2].isdigit() else 0,
                                "punten": int(row_vals[3]) if len(row_vals) > 3 and row_vals[3].isdigit() else 0,
                            }
        logging.info(f"{len(standings)} actuele standen geparsed uit stand.xlsx.")
    except Exception as e:
        logging.warning(f"Fout bij parsen stand.xlsx: {e}")

    return standings


def load_poule_cache() -> dict:
    """Laadt de lokale poule-indeling cache (voor teamnamen op basis van IRIs)."""
    sibling_cache = SCRIPT_DIR.parent / "voko-uitslagen" / "cache" / "pouleindelingen.json"
    if sibling_cache.exists():
        try:
            with open(sibling_cache, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def fetch_nevobo_teams(poule_cache: dict) -> dict[str, dict]:
    """
    Haalt de lijst van VOKO teams op bij Nevobo inclusief standpositietekst.
    Geeft een mapping terug: team_naam -> { stand: str, id: str, poule: str, ... }
    """
    url = f"{NEVOBO_API_BASE}/competitie/teams?vereniging={urllib.parse.quote(VERENIGING_IRI)}"
    nevobo_teams = {}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for member in data.get("hydra:member", []):
                name = normalize_team_name(member.get("naam", ""))
                stand = member.get("standpositietekst", "")
                team_id = member.get("@id", "")
                if name:
                    nevobo_teams[name] = {
                        "naam": name,
                        "stand": stand,
                        "id": team_id,
                        "uuid": member.get("uuid"),
                        "links": member.get("_links", {})
                    }
            logging.info(f"{len(nevobo_teams)} teams opgehaald bij Nevobo.")
            return nevobo_teams
    except Exception as e:
        logging.warning(f"Nevobo teams API waarschuwing: {e}. Fallback op lokaal referentiebestand.")

    # Fallback op lokaal 01.json snapshot indien live netwerk offline of afgeschermd is
    fallback_file = SCRIPT_DIR.parent / "voko-wedstrijden-check" / "recon-output" / "volleybalnl-json" / "01.json"
    if fallback_file.exists():
        try:
            with open(fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for member in data.get("hydra:member", []):
                    name = normalize_team_name(member.get("naam", ""))
                    stand = member.get("standpositietekst", "")
                    if name:
                        nevobo_teams[name] = {
                            "naam": name,
                            "stand": stand,
                            "id": member.get("@id", ""),
                            "uuid": member.get("uuid"),
                            "links": member.get("_links", {})
                        }
            logging.info(f"{len(nevobo_teams)} teams geladen uit lokaal referentiebestand.")
        except Exception as ex:
            logging.warning(f"Kon lokaal referentiebestand niet laden: {ex}")

    return nevobo_teams


def fetch_nevobo_matches(today: date, poule_cache: dict, nevobo_teams: dict) -> tuple[list[dict], list[dict]]:
    """
    Haalt uitslagen (afgelopen week + vandaag) en programma (komende 7 dagen) op via de officiële Nevobo RSS-feeds:
    - https://api.nevobo.nl/export/vereniging/CKM1R98/resultaten.rss
    - https://api.nevobo.nl/export/vereniging/CKM1R98/programma.rss
    """
    cutoff_uitslagen = today - timedelta(days=7)
    cutoff_programma = today + timedelta(days=7)

    uitslagen = []
    programma = []

    # -------------------------------------------------------------------------
    # A. Resultaten ophalen via resultaten.rss
    # -------------------------------------------------------------------------
    rss_uitslagen_url = "https://api.nevobo.nl/export/vereniging/CKM1R98/resultaten.rss"
    try:
        resp = requests.get(rss_uitslagen_url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            logging.info(f"{len(items)} items gevonden in resultaten.rss")

            def parse_resultaten_items(cutoff_date):
                parsed = []
                for it in items:
                    status_el = it.find("{https://www.api.nevobo.nl/rss/}status")
                    status = status_el.text.strip().lower() if status_el is not None and status_el.text else ""
                    if status != "gespeeld":
                        continue

                    pub_date_raw = it.findtext("pubDate") or ""
                    clean_date = re.sub(r"\s+[+-]\d{4}$", "", pub_date_raw).strip()
                    try:
                        dt = datetime.strptime(clean_date, "%a, %d %b %Y %H:%M:%S")
                        m_date = dt.date()
                        tijd = dt.strftime("%H:%M")
                    except Exception:
                        continue

                    # Alleen uitslagen binnen het datumvenster
                    if not (cutoff_date <= m_date <= today):
                        continue

                    title = it.findtext("title") or ""
                    desc = it.findtext("description") or ""

                    # Formaat: "Dunamis MB 1 - VOKO MB 2, Uitslag: 3-2"
                    m = re.search(r"(.+?)\s*-\s*(.+?),\s*Uitslag:\s*(\d+)-(\d+)", title)
                    if not m:
                        continue

                    t_thuis_raw = m.group(1).strip()
                    t_uit_raw = m.group(2).strip()
                    sets_thuis = int(m.group(3))
                    sets_uit = int(m.group(4))

                    t_thuis = normalize_team_name(t_thuis_raw)
                    t_uit = normalize_team_name(t_uit_raw)

                    is_voko_thuis = "voko" in t_thuis.lower()
                    is_voko_uit = "voko" in t_uit.lower()
                    if not (is_voko_thuis or is_voko_uit):
                        continue

                    our_team = t_thuis if is_voko_thuis else t_uit
                    opp_team = t_uit if is_voko_thuis else t_thuis
                    is_home = is_voko_thuis
                    our_sets = sets_thuis if is_home else sets_uit
                    opp_sets = sets_uit if is_home else sets_thuis
                    winst = our_sets > opp_sets

                    # Parse setstanden uit description: "Setstanden: 25-8, 25-23, 22-25, 20-25, 15-5"
                    m_sets = re.search(r"Setstanden:\s*([0-9\s,\-]+)", desc)
                    setstanden_str = m_sets.group(1).strip() if m_sets else ""

                    guid = it.findtext("guid") or it.findtext("link") or f"{our_team}_{m_date.isoformat()}"
                    match_id = guid.split("/")[-1] if "/" in guid else guid

                    team_info = nevobo_teams.get(our_team, {})
                    stand_tekst = team_info.get("stand", "")
                    competitie = stand_tekst.replace(" in ", " • ").split(" • ")[-1] if " in " in stand_tekst else "Nevobo Competitie"

                    parsed.append({
                        "id": match_id,
                        "team": our_team,
                        "tegenstander": opp_team,
                        "thuis": is_home,
                        "team_thuis": t_thuis,
                        "team_uit": t_uit,
                        "datum": format_dutch_date(m_date),
                        "iso_datum": m_date.isoformat(),
                        "tijd": tijd,
                        "locatie": "Sporthal VOKO-Home" if is_home else "Uitwedstrijd",
                        "competitie": competitie,
                        "stand_team": stand_tekst,
                        "sets_thuis": sets_thuis,
                        "sets_uit": sets_uit,
                        "uitslag": f"{sets_thuis} - {sets_uit}",
                        "winst": winst,
                        "setstanden": setstanden_str,
                        "bron": "Nevobo RSS"
                    })
                return parsed

            uitslagen = parse_resultaten_items(cutoff_uitslagen)
            # Als er in de afgelopen 7 dagen < 2 uitslagen zijn (bijv. rustige speelronde), kijk tot 14 dagen terug
            if len(uitslagen) < 2:
                uitslagen = parse_resultaten_items(today - timedelta(days=14))

            logging.info(f"{len(uitslagen)} uitslagen geladen uit Nevobo RSS.")
    except Exception as e:
        logging.warning(f"Nevobo resultaten RSS waarschuwing: {e}")

    # -------------------------------------------------------------------------
    # B. Programma ophalen via programma.rss
    # -------------------------------------------------------------------------
    rss_programma_url = "https://api.nevobo.nl/export/vereniging/CKM1R98/programma.rss"
    try:
        resp = requests.get(rss_programma_url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            logging.info(f"{len(items)} items gevonden in programma.rss")

            for it in items:
                status_el = it.find("{https://www.api.nevobo.nl/rss/}status")
                status = status_el.text.strip().lower() if status_el is not None and status_el.text else ""
                if status != "gepland":
                    continue

                pub_date_raw = it.findtext("pubDate") or ""
                clean_date = re.sub(r"\s+[+-]\d{4}$", "", pub_date_raw).strip()
                try:
                    dt = datetime.strptime(clean_date, "%a, %d %b %Y %H:%M:%S")
                    m_date = dt.date()
                    tijd = dt.strftime("%H:%M")
                except Exception:
                    continue

                if not (today <= m_date <= cutoff_programma):
                    continue

                title = it.findtext("title") or ""
                desc = it.findtext("description") or ""

                # Strip voorloop-datum/tijd indien aanwezig (bv. "30 okt 20:30: VOKO DS 2 - Volley Zuid DS 8")
                title_clean = re.sub(r"^\s*\d+\s+[a-zA-Z]+\s+\d{1,2}:\d{2}:\s*", "", title)
                m_teams = re.search(r"(.+?)\s*-\s*(.+)", title_clean)
                if not m_teams:
                    continue

                t_thuis_raw = m_teams.group(1).strip()
                t_uit_raw = m_teams.group(2).strip()
                t_thuis = normalize_team_name(t_thuis_raw)
                t_uit = normalize_team_name(t_uit_raw)

                is_voko_thuis = "voko" in t_thuis.lower()
                is_voko_uit = "voko" in t_uit.lower()
                if not (is_voko_thuis or is_voko_uit):
                    continue

                our_team = t_thuis if is_voko_thuis else t_uit
                opp_team = t_uit if is_voko_thuis else t_thuis
                is_home = is_voko_thuis

                # Parse Speellocatie uit description: "Speellocatie: VOKO-home, Paterserf 16, 4904AR  Oosterhout NB"
                loc_match = re.search(r"Speellocatie:\s*([^,]+)", desc)
                locatie = loc_match.group(1).strip() if loc_match else ("Sporthal VOKO-Home" if is_home else "Uitwedstrijd")

                guid = it.findtext("guid") or it.findtext("link") or f"{our_team}_{m_date.isoformat()}"
                match_id = guid.split("/")[-1] if "/" in guid else guid

                team_info = nevobo_teams.get(our_team, {})
                stand_tekst = team_info.get("stand", "")
                competitie = stand_tekst.replace(" in ", " • ").split(" • ")[-1] if " in " in stand_tekst else "Nevobo Competitie"

                programma.append({
                    "id": match_id,
                    "team": our_team,
                    "tegenstander": opp_team,
                    "thuis": is_home,
                    "team_thuis": t_thuis,
                    "team_uit": t_uit,
                    "datum": format_dutch_date(m_date),
                    "iso_datum": m_date.isoformat(),
                    "tijd": tijd,
                    "locatie": locatie,
                    "competitie": competitie,
                    "stand_team": stand_tekst,
                    "bron": "Nevobo RSS"
                })
            logging.info(f"{len(programma)} programma-items geladen uit Nevobo RSS.")
    except Exception as e:
        logging.warning(f"Nevobo programma RSS waarschuwing: {e}")

    # -------------------------------------------------------------------------
    # C. Lokale Fallbacks indien live RSS niet bereikbaar was
    # -------------------------------------------------------------------------
    if not uitslagen:
        gespeeld_fallback_file = SCRIPT_DIR.parent / "voko-uitslagen" / "recon-output" / "B01-gespeeld-voorbeeld.json"
        if gespeeld_fallback_file.exists():
            try:
                with open(gespeeld_fallback_file, "r", encoding="utf-8") as f:
                    fallback_gespeeld = json.load(f)
                    for m in fallback_gespeeld[:6]:
                        d_str = m.get("datum", "")[:10]
                        try:
                            m_date = datetime.strptime(d_str, "%Y-%m-%d").date()
                        except ValueError:
                            m_date = today

                        t_iris = m.get("teams", [])
                        if len(t_iris) >= 2:
                            t1 = poule_cache.get(t_iris[0], {}).get("om", t_iris[0].split("/")[-1])
                            t2 = poule_cache.get(t_iris[1], {}).get("om", t_iris[1].split("/")[-1])
                            t1_norm = normalize_team_name(t1)
                            t2_norm = normalize_team_name(t2)
                            is_home = "voko" in t1_norm.lower()
                            our_team = t1_norm if is_home else t2_norm
                            opp_team = t2_norm if is_home else t1_norm

                            eind = m.get("eindstand", [0, 0])
                            st_list = m.get("setstanden", [])
                            st_str = ", ".join(f"{s.get('puntenA')}-{s.get('puntenB')}" for s in st_list) if st_list else ""
                            winst = (eind[0] > eind[1]) if is_home else (eind[1] > eind[0])

                            uitslagen.append({
                                "id": m.get("code") or f"{our_team}_{d_str}",
                                "team": our_team,
                                "tegenstander": opp_team,
                                "thuis": is_home,
                                "team_thuis": t1_norm,
                                "team_uit": t2_norm,
                                "datum": format_dutch_date(m_date),
                                "iso_datum": d_str,
                                "tijd": m.get("tijdstip", "")[11:16],
                                "locatie": "Sporthal VOKO-Home" if is_home else "Uitwedstrijd",
                                "competitie": "Nevobo Competitie",
                                "stand_team": nevobo_teams.get(our_team, {}).get("stand", ""),
                                "sets_thuis": eind[0],
                                "sets_uit": eind[1],
                                "uitslag": f"{eind[0]} - {eind[1]}",
                                "winst": winst,
                                "setstanden": st_str,
                                "bron": "Lokaal referentiebestand"
                            })
                    logging.info(f"{len(uitslagen)} uitslagen geladen uit referentiebestand.")
            except Exception as ex:
                logging.warning(f"Kon fallback gespeeld niet laden: {ex}")

    return uitslagen, programma


# -----------------------------------------------------------------------------
# 3. ORV Breda (Dames 3 - 2e Klasse Dames)
# -----------------------------------------------------------------------------
def fetch_orv_dames3(today: date) -> tuple[list[dict], list[dict], dict | None]:
    """
    Haalt wedstrijden en stand op voor VOKO Dames 3 bij de ORV Breda (2e klasse dames).
    Endpoint: https://www.orvbreda.nl/util/ajaxLeesWedstrijden.php (pKlasse=7)
    """
    cutoff_uitslagen = today - timedelta(days=7)
    cutoff_programma = today + timedelta(days=7)

    uitslagen_orv = []
    programma_orv = []
    orv_data = None

    try:
        post_data = {
            "pKlasse": "7",
            "pTimestamp": str(int(datetime.now().timestamp() * 1000))
        }
        resp = requests.post(
            f"{ORV_BASE}/util/ajaxLeesWedstrijden.php",
            headers={"Content-Type": "application/x-www-form-urlencoded", **HEADERS},
            data=post_data,
            timeout=10
        )
        if resp.status_code == 200:
            orv_data = resp.json()
            logging.info("ORV Breda 2e klasse dames succesvol opgehaald.")
    except Exception as e:
        logging.warning(f"ORV Breda API waarschuwing: {e}. Fallback op lokaal referentiebestand.")

    if not orv_data:
        fallback_orv = SCRIPT_DIR.parent / "voko-uitslagen" / "recon-output" / "C01-orv-klasse-7.json"
        if fallback_orv.exists():
            try:
                with open(fallback_orv, "r", encoding="utf-8") as f:
                    orv_data = json.load(f)
                logging.info("ORV data geladen uit lokaal C01-orv-klasse-7.json.")
            except Exception as ex:
                logging.warning(f"Kon C01-orv-klasse-7.json niet laden: {ex}")

    if not orv_data:
        return uitslagen_orv, programma_orv, None

    teams_list = orv_data.get("Team", [])
    voko_idx = -1
    for idx, t in enumerate(teams_list):
        tname = t.get("TeamNaam", "")
        if "voko" in tname.lower():
            voko_idx = idx
            break

    if voko_idx == -1:
        logging.warning("VOKO DS 3 niet gevonden in ORV teams.")
        return uitslagen_orv, programma_orv, None

    # Bereken de stand voor 2e klasse dames volgens het ORV algoritme
    # Stand matrix: [ranking, TeamNaam, Gespeeld, Gewonnen, Gelijk, Verloren, Punten, Voor, Tegen, Saldo, idx]
    stand_matrix = []
    for idx, t in enumerate(teams_list):
        stand_matrix.append({
            "idx": idx,
            "team": t.get("TeamNaam", ""),
            "gespeeld": 0, "gewonnen": 0, "gelijk": 0, "verloren": 0,
            "punten": 0.0, "voor": 0, "tegen": 0, "saldo": 0
        })

    wedstrijden = orv_data.get("Wedstrijd", [])
    for w in wedstrijden:
        set_standen = w.get("SetStanden")
        t_thuis = int(w.get("TeamThuis", -1))
        t_uit = int(w.get("TeamUit", -1))

        if set_standen and t_thuis >= 0 and t_uit >= 0:
            stand_matrix[t_thuis]["gespeeld"] += 1
            stand_matrix[t_uit]["gespeeld"] += 1

            pthuis = float(w.get("PuntenThuis", 0))
            puit = float(w.get("PuntenUit", 0))

            stand_matrix[t_thuis]["punten"] += pthuis
            stand_matrix[t_uit]["punten"] += puit

            if pthuis > puit:
                stand_matrix[t_thuis]["gewonnen"] += 1
                stand_matrix[t_uit]["verloren"] += 1
            elif pthuis < puit:
                stand_matrix[t_thuis]["verloren"] += 1
                stand_matrix[t_uit]["gewonnen"] += 1
            else:
                stand_matrix[t_thuis]["gelijk"] += 1
                stand_matrix[t_uit]["gelijk"] += 1

            sthuis = int(w.get("SaldoThuis", 0))
            suit = int(w.get("SaldoUit", 0))
            stand_matrix[t_thuis]["voor"] += sthuis
            stand_matrix[t_thuis]["tegen"] += suit
            stand_matrix[t_uit]["voor"] += suit
            stand_matrix[t_uit]["tegen"] += sthuis

    # Sorteer op punten (aflopend), daarna op saldo
    for s in stand_matrix:
        s["saldo"] = s["voor"] - s["tegen"]
    stand_matrix.sort(key=lambda x: (x["punten"], x["saldo"]), reverse=True)

    voko_rank = 1
    voko_stand_item = None
    for r_idx, s in enumerate(stand_matrix, start=1):
        if s["idx"] == voko_idx:
            voko_rank = r_idx
            voko_stand_item = s
            break

    stand_ds3_tekst = f"{voko_rank}e in 2e Klasse Dames (ORV)"
    ds3_stand_dict = {
        "team": "VOKO DS 3",
        "klasse": "ORV 2e Klasse Dames",
        "positie": voko_rank,
        "positie_tekst": f"{voko_rank}e",
        "stand_omschrijving": stand_ds3_tekst,
        "gespeeld": voko_stand_item["gespeeld"] if voko_stand_item else 0,
        "punten": int(voko_stand_item["punten"]) if voko_stand_item else 0,
        "bron": "ORV Breda"
    }

    # Parse wedstrijden van VOKO DS 3
    for w in wedstrijden:
        t_thuis_idx = int(w.get("TeamThuis", -1))
        t_uit_idx = int(w.get("TeamUit", -1))

        if t_thuis_idx != voko_idx and t_uit_idx != voko_idx:
            continue

        raw_date = str(w.get("SpeelDatum", ""))
        if not (len(raw_date) == 8 and raw_date.isdigit()):
            continue

        try:
            m_date = datetime.strptime(raw_date, "%Y%m%d").date()
        except ValueError:
            continue

        is_home = (t_thuis_idx == voko_idx)
        opp_idx = t_uit_idx if is_home else t_thuis_idx
        opp_name = teams_list[opp_idx].get("TeamNaam", f"Team {opp_idx}") if opp_idx < len(teams_list) else "Tegenstander"

        status_code = str(w.get("SpeelStatus", ""))
        set_standen = w.get("SetStanden", "")

        tijd = teams_list[t_thuis_idx].get("TijdOpen", "20:30") if t_thuis_idx < len(teams_list) else "20:30"
        locatie = teams_list[t_thuis_idx].get("SpeelLocatie", "Sporthal") if t_thuis_idx < len(teams_list) else "Sporthal"

        # Uitslagen: SpeelStatus 3 = gespeeld
        if status_code == "3" and set_standen and cutoff_uitslagen <= m_date <= today:
            sets_thuis = int(float(w.get("PuntenThuis", 0)))
            sets_uit = int(float(w.get("PuntenUit", 0)))
            our_sets = sets_thuis if is_home else sets_uit
            opp_sets = sets_uit if is_home else sets_thuis

            # Format setstanden: "17,25,18,25..." -> "17-25, 18-25..."
            raw_nums = [n.strip() for n in set_standen.split(",") if n.strip().isdigit()]
            sets_formatted = []
            for i in range(0, len(raw_nums) - 1, 2):
                sets_formatted.append(f"{raw_nums[i]}-{raw_nums[i+1]}")
            setstanden_str = ", ".join(sets_formatted)

            uitslagen_orv.append({
                "id": f"ORV_7_{w.get('Ronde')}_{raw_date}",
                "team": "VOKO DS 3",
                "tegenstander": opp_name,
                "thuis": is_home,
                "team_thuis": "VOKO DS 3" if is_home else opp_name,
                "team_uit": opp_name if is_home else "VOKO DS 3",
                "datum": format_dutch_date(m_date),
                "iso_datum": m_date.isoformat(),
                "tijd": tijd,
                "locatie": locatie,
                "competitie": "ORV 2e Klasse Dames",
                "stand_team": stand_ds3_tekst,
                "sets_thuis": sets_thuis,
                "sets_uit": sets_uit,
                "uitslag": f"{sets_thuis} - {sets_uit}",
                "winst": our_sets > opp_sets,
                "setstanden": setstanden_str,
                "bron": "ORV Breda"
            })

        # Programma: SpeelStatus 1 = gepland
        elif status_code == "1" and today <= m_date <= cutoff_programma:
            programma_orv.append({
                "id": f"ORV_7_{w.get('Ronde')}_{raw_date}",
                "team": "VOKO DS 3",
                "tegenstander": opp_name,
                "thuis": is_home,
                "team_thuis": "VOKO DS 3" if is_home else opp_name,
                "team_uit": opp_name if is_home else "VOKO DS 3",
                "datum": format_dutch_date(m_date),
                "iso_datum": m_date.isoformat(),
                "tijd": tijd,
                "locatie": locatie,
                "competitie": "ORV 2e Klasse Dames",
                "stand_team": stand_ds3_tekst,
                "bron": "ORV Breda"
            })

    # Als er geen uitslagen waren in de afgelopen 7 dagen, voeg meest recente gespeelde ORV wedstrijd toe
    if not uitslagen_orv:
        for w in reversed(wedstrijden):
            t_thuis_idx = int(w.get("TeamThuis", -1))
            t_uit_idx = int(w.get("TeamUit", -1))
            if t_thuis_idx != voko_idx and t_uit_idx != voko_idx:
                continue
            if str(w.get("SpeelStatus")) == "3" and w.get("SetStanden"):
                raw_date = str(w.get("SpeelDatum", ""))
                try:
                    m_date = datetime.strptime(raw_date, "%Y%m%d").date()
                except ValueError:
                    m_date = today
                is_home = (t_thuis_idx == voko_idx)
                opp_idx = t_uit_idx if is_home else t_thuis_idx
                opp_name = teams_list[opp_idx].get("TeamNaam", f"Team {opp_idx}") if opp_idx < len(teams_list) else "Tegenstander"
                pthuis = int(float(w.get("PuntenThuis", 0)))
                puit = int(float(w.get("PuntenUit", 0)))
                raw_nums = [n.strip() for n in w.get("SetStanden", "").split(",") if n.strip().isdigit()]
                st_formatted = [f"{raw_nums[i]}-{raw_nums[i+1]}" for i in range(0, len(raw_nums)-1, 2)]
                uitslagen_orv.append({
                    "id": f"ORV_7_{w.get('Ronde')}_{raw_date}",
                    "team": "VOKO DS 3",
                    "tegenstander": opp_name,
                    "thuis": is_home,
                    "team_thuis": "VOKO DS 3" if is_home else opp_name,
                    "team_uit": opp_name if is_home else "VOKO DS 3",
                    "datum": format_dutch_date(m_date),
                    "iso_datum": m_date.isoformat(),
                    "tijd": "20:30",
                    "locatie": "Sporthal De Opperdam",
                    "competitie": "ORV 2e Klasse Dames",
                    "stand_team": stand_ds3_tekst,
                    "sets_thuis": pthuis,
                    "sets_uit": puit,
                    "uitslag": f"{pthuis} - {puit}",
                    "winst": (pthuis > puit) if is_home else (puit > pthuis),
                    "setstanden": ", ".join(st_formatted),
                    "bron": "ORV Breda"
                })
                break

    return uitslagen_orv, programma_orv, ds3_stand_dict


# -----------------------------------------------------------------------------
# 4. Standen structureren (4 categorieën)
# -----------------------------------------------------------------------------
def build_standen_data(nevobo_teams: dict, ds3_stand: dict | None, photos_map: dict, xlsx_standings: dict) -> dict:
    """
    Bouwt de 4 categorieën van standen.json op basis van de officiële Nevobo stand.xlsx:
    Slide 1: Heren (HS 1 t/m HS 5)
    Slide 2: Dames (DS 1, DS 2 & DS 3 ORV)
    Slide 3: Jeugd (MA 1, MA 2, MB 1, MB 2, MC 1, MC 2)
    Slide 4: Volley Stars (L5-2, L5-1, L4-2, L4-3, L4-1, Level 3 & 2)
    """
    def parse_rank_and_class(stand_txt: str) -> tuple[int, str, str]:
        m = re.search(r"(\d+)[e|ste]?\s+in\s+(.+)", stand_txt, flags=re.IGNORECASE)
        if m:
            rank = int(m.group(1))
            klasse = m.group(2).strip()
            return rank, f"{rank}e", klasse
        return 99, "-", stand_txt

    def get_team_stand_info(team_name: str, fallback_klasse: str) -> tuple[int, str, str, str, int, int]:
        t_xlsx = xlsx_standings.get(team_name)
        if t_xlsx:
            return (
                t_xlsx["positie"],
                t_xlsx["positie_tekst"],
                t_xlsx["klasse"],
                t_xlsx["stand_omschrijving"],
                t_xlsx.get("gespeeld", 0),
                t_xlsx.get("punten", 0)
            )
        # Fallback op nevobo_teams (API / referentie)
        t_data = nevobo_teams.get(team_name, {})
        stand_txt = t_data.get("stand", "")
        pos, pos_txt, klasse = parse_rank_and_class(stand_txt) if stand_txt else (99, "-", fallback_klasse)
        return pos, pos_txt, klasse or fallback_klasse, stand_txt or f"{pos_txt} in {fallback_klasse}", 0, 0

    # 1. Heren
    heren_order = [
        ("VOKO HS 1", "Heren Derde divisie B"),
        ("VOKO HS 2", "Heren 1e Klasse D"),
        ("VOKO HS 3", "Heren 2e Klasse D"),
        ("VOKO HS 4", "Heren 3e Klasse C"),
        ("VOKO HS 5", "Heren 3e Klasse D")
    ]
    heren_list = []
    for team_name, def_klasse in heren_order:
        pos, pos_txt, klasse, stand_txt, gespeeld, punten = get_team_stand_info(team_name, def_klasse)
        img_url, is_ph = get_team_photo(team_name, photos_map)
        heren_list.append({
            "team": team_name,
            "klasse": klasse,
            "positie": pos,
            "positie_tekst": pos_txt,
            "stand_omschrijving": stand_txt,
            "gespeeld": gespeeld,
            "punten": punten,
            "team_foto": img_url,
            "is_placeholder": is_ph
        })

    # 2. Dames
    dames_order = [
        ("VOKO DS 1", "Dames Derde divisie B"),
        ("VOKO DS 2", "Dames 3e Klasse G"),
        ("VOKO DS 3", "ORV 2e Klasse Dames")
    ]
    dames_list = []
    for team_name, def_klasse in dames_order:
        if team_name == "VOKO DS 3":
            if ds3_stand:
                img_url, is_ph = get_team_photo(team_name, photos_map)
                dames_list.append({
                    **ds3_stand,
                    "team_foto": img_url,
                    "is_placeholder": is_ph
                })
        else:
            pos, pos_txt, klasse, stand_txt, gespeeld, punten = get_team_stand_info(team_name, def_klasse)
            img_url, is_ph = get_team_photo(team_name, photos_map)
            dames_list.append({
                "team": team_name,
                "klasse": klasse,
                "positie": pos,
                "positie_tekst": pos_txt,
                "stand_omschrijving": stand_txt,
                "gespeeld": gespeeld,
                "punten": punten,
                "team_foto": img_url,
                "is_placeholder": is_ph,
                "bron": "Nevobo"
            })

    # 3. Jeugd
    jeugd_order = [
        ("VOKO MA 1", "Meiden A 1e Klasse C Eerste helft"),
        ("VOKO MA 2", "Meiden A 1e Klasse D Eerste helft"),
        ("VOKO MB 1", "Meiden B 1e Klasse D Eerste helft"),
        ("VOKO MB 2", "Meiden B 3e Klasse E Eerste helft"),
        ("VOKO MC 1", "C Jeugd 3e Klasse J Eerste helft"),
        ("VOKO MC 2", "C Jeugd 3e Klasse K Eerste helft")
    ]
    jeugd_list = []
    for team_name, def_klasse in jeugd_order:
        pos, pos_txt, klasse, stand_txt, gespeeld, punten = get_team_stand_info(team_name, def_klasse)
        img_url, is_ph = get_team_photo(team_name, photos_map)
        jeugd_list.append({
            "team": team_name,
            "klasse": klasse,
            "positie": pos,
            "positie_tekst": pos_txt,
            "stand_omschrijving": stand_txt,
            "gespeeld": gespeeld,
            "punten": punten,
            "team_foto": img_url,
            "is_placeholder": is_ph
        })

    # 4. Volley Stars (Mini's / CMV toernooien)
    img_stars, is_ph_stars = get_team_photo("Volley Stars", photos_map)
    stars_order = [
        ("VOKO L5 2", "Niveau 5 (CMV) • 1e toernooipoule"),
        ("VOKO L5 1", "Niveau 5 (CMV) • 5e toernooipoule"),
        ("VOKO L4 2", "Niveau 4 (CMV) • 1e toernooipoule"),
        ("VOKO L4 3", "Niveau 4 (CMV) • 3e toernooipoule"),
        ("VOKO L4 1", "Niveau 4 (CMV) • 5e toernooipoule"),
        ("VOKO Level 3 & 2", "Niveau 3 & 2 • Geen toernooideelname")
    ]

    stars_list = []
    for team_name, def_klasse in stars_order:
        if team_name == "VOKO Level 3 & 2":
            stars_list.append({
                "team": team_name,
                "klasse": def_klasse,
                "positie": 99,
                "positie_tekst": "-",
                "stand_omschrijving": def_klasse,
                "team_foto": img_stars,
                "is_placeholder": is_ph_stars
            })
        else:
            pos, pos_txt, klasse, stand_txt, gespeeld, punten = get_team_stand_info(team_name, def_klasse)
            img_url, is_ph = get_team_photo(team_name, photos_map)
            if is_ph:
                img_url, is_ph = img_stars, is_ph_stars
            stars_list.append({
                "team": team_name,
                "klasse": klasse or def_klasse,
                "positie": pos,
                "positie_tekst": pos_txt,
                "stand_omschrijving": stand_txt,
                "gespeeld": gespeeld,
                "punten": punten,
                "team_foto": img_url,
                "is_placeholder": is_ph
            })

    return {
        "updated_at": datetime.now().isoformat(),
        "categories": {
            "heren": {
                "titel": "Standen Heren",
                "slide_index": 1,
                "teams": heren_list
            },
            "dames": {
                "titel": "Standen Dames",
                "slide_index": 2,
                "teams": dames_list
            },
            "jeugd": {
                "titel": "Standen Jeugd",
                "slide_index": 3,
                "teams": jeugd_list
            },
            "volleystars": {
                "titel": "Volley Stars (Mini's)",
                "slide_index": 4,
                "ondertitel": "Meest recente speelronde CMV • Level 5 & 4 actief",
                "teams": stars_list
            }
        }
    }


# -----------------------------------------------------------------------------
# 5. Hoofdroutine update_competitie()
# -----------------------------------------------------------------------------
def update_competitie():
    logging.info("Starten met updaten van VOKO competitiegegevens...")
    today = datetime.now().date()
    logging.info(f"Peildatum: {today.isoformat()} ({format_dutch_date(today)})")

    # 1. Haal teamfoto's op van de clubsite
    photos_map = fetch_team_photos()

    # 2. Laad pouleindelingen cache & Nevobo teamlijst
    poule_cache = load_poule_cache()
    nevobo_teams = fetch_nevobo_teams(poule_cache)

    # 2b. Haal de officiële en actuele stand.xlsx op bij Nevobo
    xlsx_standings = fetch_and_parse_stand_xlsx()

    # 3. Haal wedstrijden op bij Nevobo (RSS feeds)
    nevobo_uitslagen, nevobo_programma = fetch_nevobo_matches(today, poule_cache, nevobo_teams)

    # 4. Haal ORV gegevens op voor Dames 3
    orv_uitslagen, orv_programma, ds3_stand = fetch_orv_dames3(today)

    # Voeg samen
    alle_uitslagen = nevobo_uitslagen + orv_uitslagen
    alle_programma = nevobo_programma + orv_programma

    # Voeg teamfoto toe aan elke wedstrijd
    for w in alle_uitslagen:
        img_url, is_ph = get_team_photo(w["team"], photos_map)
        w["team_foto"] = img_url
        w["is_placeholder"] = is_ph

    for w in alle_programma:
        img_url, is_ph = get_team_photo(w["team"], photos_map)
        w["team_foto"] = img_url
        w["is_placeholder"] = is_ph

    # Sorteer uitslagen: meest recent eerst
    alle_uitslagen.sort(key=lambda x: (x.get("iso_datum", ""), x.get("tijd", "")), reverse=True)

    # Sorteer programma: eerstvolgende eerst
    alle_programma.sort(key=lambda x: (x.get("iso_datum", ""), x.get("tijd", "")))

    # Bouw standen met de actuele stand.xlsx data
    standen_data = build_standen_data(nevobo_teams, ds3_stand, photos_map, xlsx_standings)

    # 5. Schrijf bestanden weg
    with open(UPLOADS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "type": "uitslagen",
            "periode": "afgelopen week + live vandaag",
            "total": len(alle_uitslagen),
            "items": alle_uitslagen
        }, f, ensure_ascii=False, indent=2)

    with open(PROGRAMMA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "type": "programma",
            "periode": "komende 7 dagen",
            "total": len(alle_programma),
            "items": alle_programma
        }, f, ensure_ascii=False, indent=2)

    with open(STANDEN_FILE, "w", encoding="utf-8") as f:
        json.dump(standen_data, f, ensure_ascii=False, indent=2)

    logging.info(f"Klaar: {len(alle_uitslagen)} uitslagen naar {UPLOADS_FILE.name}")
    logging.info(f"Klaar: {len(alle_programma)} programma-items naar {PROGRAMMA_FILE.name}")
    logging.info(f"Klaar: Standen weggeschreven naar {STANDEN_FILE.name}")


if __name__ == "__main__":
    update_competitie()
