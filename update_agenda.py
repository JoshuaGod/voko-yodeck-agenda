#!/usr/bin/env python3
"""
VOKO Digital Signage - Agenda Scraper & Parser
Haalt de eerstvolgende clubactiviteiten op van www.voko-oosterhout.nl/activiteiten/
en genereert een geformatteerde agenda.json voor de narrowcasting web-slide.
"""

import json
import logging
import re
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# De live Club-Assistent site gebruikt een trailing slash (zonder slash levert 404 op)
URLS_TO_TRY = [
    "https://www.voko-oosterhout.nl/activiteiten/",
    "https://www.voko-oosterhout.nl/activiteiten"
]
OUTPUT_FILE = "agenda.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DUTCH_MONTHS = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december"
}

DUTCH_MONTH_ABBR_MAP = {
    "jan": 1, "feb": 2, "mrt": 3, "maa": 3, "mar": 3,
    "apr": 4, "mei": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dec": 12
}


def parse_date_string(date_str: str) -> date | None:
    """Probeert een datumstring in diverse formaten te parsen."""
    if not date_str:
        return None
    date_str = date_str.strip()

    # Formaat 1: ISO YYYY-MM-DD
    iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass

    # Formaat 2: DD-MM-YYYY of DD/MM/YYYY
    dmy_match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", date_str)
    if dmy_match:
        try:
            return date(int(dmy_match.group(3)), int(dmy_match.group(2)), int(dmy_match.group(1)))
        except ValueError:
            pass

    # Formaat 3: "2 dec 2026" of "2 december 2026"
    text_match = re.search(r"(\d{1,2})\s+([a-zA-Z]+)(?:\s+(\d{4}))?", date_str)
    if text_match:
        day = int(text_match.group(1))
        month_name = text_match.group(2).lower()[:3]
        year = int(text_match.group(3)) if text_match.group(3) else datetime.now().year
        month = DUTCH_MONTH_ABBR_MAP.get(month_name)
        if month:
            try:
                parsed = date(year, month, day)
                # Als geen jaar gegeven was en datum ligt in het verleden, neem volgend jaar
                if not text_match.group(3) and parsed < datetime.now().date():
                    parsed = date(year + 1, month, day)
                return parsed
            except ValueError:
                pass

    return None


def format_dutch_date(d: date) -> str:
    """Formatteert een datum als '2 december'."""
    month_name = DUTCH_MONTHS.get(d.month, "")
    return f"{d.day} {month_name}"


def clean_title(title: str, desc: str = "") -> str:
    """Normaliseert en verschoont de activiteitstitel voor de narrowcasting slide."""
    title = re.sub(r"\s+", " ", title).strip()

    # Specifieke optimalisaties voor VOKO huiseigen slide titels
    t_lower = title.lower()
    d_lower = desc.lower()

    if "pietentraining" in t_lower:
        if "volleystars" in d_lower or "mini" in d_lower:
            return "Pietentraining - Volleystars"
        return "Pietentraining"

    if "oliebollentoernooi" in t_lower or "oliebollen" in t_lower:
        return "Oliebollen Toernooi"

    if t_lower == "pubquiz":
        return "Pubquiz"

    if "winter bbq" in t_lower or "winterbbq" in t_lower:
        return "WinterBBQ"

    if ("ouder-kind" in t_lower or "kind-ouder" in t_lower) and "familie" in t_lower:
        return "Ouder-Kind Toernooi - Familie"

    return title


def smart_merge_day_events(events_on_day: list[dict]) -> dict:
    """
    Combineert meerdere activiteiten op dezelfde dag netjes tot 1 slide-rij,
    zoals bij het Ouder-Kind Toernooi & Familietoernooi of Oliebollentoernooi.
    """
    if len(events_on_day) == 1:
        return events_on_day[0]

    first = events_on_day[0]
    titles = [e["raw_title"] for e in events_on_day]
    titles_lower = [t.lower() for t in titles]

    # Geval A: Kind-Ouder + Familietoernooi op dezelfde dag
    has_kind_ouder = any("kind-ouder" in t or "ouder-kind" in t for t in titles_lower)
    has_familie = any("familie" in t for t in titles_lower)
    if has_kind_ouder and has_familie:
        return {
            "datum": first["datum"],
            "iso_datum": first["iso_datum"],
            "sort_date": first["sort_date"],
            "titel": "Ouder-Kind Toernooi - Familie"
        }

    # Geval B: Oliebollentoernooi (voor jeugd en/of senioren)
    if all("oliebollen" in t for t in titles_lower):
        return {
            "datum": first["datum"],
            "iso_datum": first["iso_datum"],
            "sort_date": first["sort_date"],
            "titel": "Oliebollen Toernooi"
        }

    # Geval C: Algemene samenvoeging
    cleaned = [clean_title(t) for t in titles]
    # Dedupliceer
    unique_cleaned = list(dict.fromkeys(cleaned))
    combined_title = " & ".join(unique_cleaned)

    return {
        "datum": first["datum"],
        "iso_datum": first["iso_datum"],
        "sort_date": first["sort_date"],
        "titel": combined_title
    }


def parse_activities():
    response = None
    used_url = None
    for url in URLS_TO_TRY:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                response = r
                used_url = url
                break
            else:
                logging.warning(f"URL {url} gaf statuscode {r.status_code}")
        except Exception as e:
            logging.warning(f"Fout bij ophalen {url}: {e}")

    if not response:
        logging.error("Kon geen enkele URL succesvol ophalen.")
        return

    logging.info(f"Pagina succesvol opgehaald van {used_url} ({len(response.text)} bytes)")
    soup = BeautifulSoup(response.text, "html.parser")
    today = datetime.now().date()

    raw_activities = []

    # Strategie 1: Club-Assistent specifieke DOM-structuur (toekomstige activiteiten)
    # De div.activiteit-overzicht.toekomst bevat specifiek de toekomstige evenementen
    future_section = soup.select(".activiteit-overzicht.toekomst")
    event_elements = (
        future_section[0].select("div.activiteit[itemprop='event']")
        if future_section
        else soup.select("div.activiteit[itemprop='event']")
    )

    for item in event_elements:
        date_el = item.select_one(".datum[itemprop='startDate']")
        title_el = item.select_one(".activiteittitel, [itemprop='name'], h2, h3")
        desc_el = item.select_one(".activiteit-omschrijving")

        if not title_el:
            continue

        raw_title = title_el.get_text(strip=True)
        desc = desc_el.get_text(strip=True) if desc_el else ""

        # Datum ophalen via itemprop/content of via de sub-spans
        parsed_date = None
        if date_el:
            content_date = date_el.get("content")
            if content_date:
                parsed_date = parse_date_string(content_date)
            if not parsed_date:
                parsed_date = parse_date_string(date_el.get_text(separator=" ", strip=True))

        if parsed_date and raw_title:
            raw_activities.append({
                "sort_date": parsed_date,
                "iso_datum": parsed_date.isoformat(),
                "datum": format_dutch_date(parsed_date),
                "raw_title": raw_title,
                "titel": clean_title(raw_title, desc),
                "desc": desc
            })

    # Strategie 2: Generieke selectors fallback
    if not raw_activities:
        generic_items = soup.select(".act-item, .event-item, article, tr")
        for item in generic_items:
            date_el = item.select_one(".date, .datum, time, td:first-child")
            title_el = item.select_one(".title, .titel, h2, h3, a, td:nth-child(2)")

            if date_el and title_el:
                d_text = date_el.get_text(strip=True)
                t_text = title_el.get_text(strip=True)
                p_date = parse_date_string(d_text)
                if p_date and t_text:
                    raw_activities.append({
                        "sort_date": p_date,
                        "iso_datum": p_date.isoformat(),
                        "datum": format_dutch_date(p_date),
                        "raw_title": t_text,
                        "titel": clean_title(t_text),
                        "desc": ""
                    })

    # Strategie 3: HTML tabellen fallback
    if not raw_activities:
        for row in soup.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                d_text = cols[0].get_text(strip=True)
                t_text = cols[1].get_text(strip=True)
                p_date = parse_date_string(d_text)
                if p_date and t_text:
                    raw_activities.append({
                        "sort_date": p_date,
                        "iso_datum": p_date.isoformat(),
                        "datum": format_dutch_date(p_date),
                        "raw_title": t_text,
                        "titel": clean_title(t_text),
                        "desc": ""
                    })

    # 1. Filter activiteiten uit het verleden weg
    future_activities = [a for a in raw_activities if a["sort_date"] >= today]

    # 2. Sorteer chronologisch
    future_activities.sort(key=lambda x: x["sort_date"])

    # 3. Groepeer op datum (als er meerdere activiteiten op 1 dag vallen, combineer)
    grouped_by_date = {}
    for act in future_activities:
        d_key = act["sort_date"]
        grouped_by_date.setdefault(d_key, []).append(act)

    merged_activities = [smart_merge_day_events(events) for events in grouped_by_date.values()]

    # 4. Pak de eerstvolgende 6 items
    final_list = []
    for item in merged_activities[:6]:
        final_list.append({
            "datum": item["datum"],
            "titel": item["titel"],
            "iso_datum": item.get("iso_datum", "")
        })

    # 5. Schrijf weg naar agenda.json
    output_data = {
        "updated_at": datetime.now().isoformat(),
        "total_upcoming": len(future_activities),
        "items": final_list
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logging.info(f"{len(final_list)} activiteiten weggeschreven naar {OUTPUT_FILE}:")
    for item in final_list:
        logging.info(f" - {item['datum']}: {item['titel']}")

    return final_list


if __name__ == "__main__":
    parse_activities()
