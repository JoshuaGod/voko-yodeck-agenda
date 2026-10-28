#!/usr/bin/env python3
"""
VOKO Digital Signage - Nieuws Scraper & Parser
Haalt de meest recente nieuwsberichten op van de VOKO website
(via de officiële RSS feed en HTML fallback) en genereert nieuws.json
voor de narrowcasting web-slide.
"""

import html
import json
import logging
import re
from datetime import datetime
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

RSS_URL = "https://www.voko-oosterhout.nl/rss/nieuws/"
HTML_URL = "https://www.voko-oosterhout.nl/nieuws/"
OUTPUT_FILE = "nieuws.json"

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
    "jan": 1, "feb": 2, "mar": 3, "mrt": 3, "apr": 4, "may": 5, "mei": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12
}


def strip_html_tags(raw_html: str) -> str:
    """Verwijdert HTML tags en decodeert entiteiten."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_pub_date(date_str: str) -> str:
    """Zet een RFC 822 / ISO datum om naar een Nederlands geformatteerde datum."""
    if not date_str:
        return ""
    # RFC 822 voorbeeld: "Sat, 03 Oct 2026 12:00:00 GMT"
    m = re.search(r"(\d{1,2})\s+([a-zA-Z]{3})\s+(\d{4})", date_str)
    if m:
        day = int(m.group(1))
        month_abbr = m.group(2).lower()
        year = int(m.group(3))
        month_num = DUTCH_MONTH_ABBR_MAP.get(month_abbr, 1)
        month_name = DUTCH_MONTHS.get(month_num, "")
        return f"{day} {month_name} {year}"

    # ISO datum YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if m_iso:
        year = int(m_iso.group(1))
        month_num = int(m_iso.group(2))
        day = int(m_iso.group(3))
        month_name = DUTCH_MONTHS.get(month_num, "")
        return f"{day} {month_name} {year}"

    return date_str.strip()


def fetch_from_rss() -> list[dict]:
    """Haalt nieuws op via de officiële RSS feed van Club-Assistent."""
    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        logging.warning(f"Kon RSS feed niet parsen: {e}")
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    seen_links = set()
    items = []

    for item_el in channel.findall("item"):
        link = (item_el.findtext("link") or "").strip()
        title = (item_el.findtext("title") or "").strip()

        # Dedupliceer items (Club-assistent feed herhaalt soms entries)
        dedup_key = (title, link)
        if dedup_key in seen_links:
            continue
        seen_links.add(dedup_key)

        desc_raw = (item_el.findtext("description") or "").strip()
        description = strip_html_tags(desc_raw)

        pub_date_raw = (item_el.findtext("pubDate") or "").strip()
        formatted_date = parse_pub_date(pub_date_raw)

        # Zoek eventuele foto in <enclosure>
        image_url = None
        enclosure = item_el.find("enclosure")
        if enclosure is not None:
            url = enclosure.get("url")
            if url:
                image_url = url

        if title:
            items.append({
                "titel": title,
                "datum": formatted_date,
                "omschrijving": description,
                "link": link,
                "afbeelding": image_url
            })

    return items


def fetch_from_html() -> list[dict]:
    """Fallback scraping van de HTML nieuwspagina."""
    try:
        resp = requests.get(HTML_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logging.warning(f"Kon HTML nieuwspagina niet ophalen: {e}")
        return []

    items = []
    cards = soup.select(".nieuws-overzicht .overzicht-bericht-item, .bericht-item, article")
    for card in cards:
        title_el = card.select_one(".berichttitel, h2, h3, .titel")
        date_el = card.select_one(".datum, time, .date")
        desc_el = card.select_one(".intro, .bericht-intro, p")
        img_el = card.select_one("img")

        if title_el:
            title = title_el.get_text(strip=True)
            date_str = date_el.get_text(strip=True) if date_el else ""
            desc = desc_el.get_text(strip=True) if desc_el else ""
            img_src = img_el.get("src") if img_el else None

            if img_src and not img_src.startswith("http"):
                img_src = f"https://www.voko-oosterhout.nl{img_src}"

            items.append({
                "titel": title,
                "datum": parse_pub_date(date_str),
                "omschrijving": desc,
                "link": HTML_URL,
                "afbeelding": img_src
            })

    return items


def update_nieuws():
    logging.info("Starten met ophalen van nieuwsberichten...")
    items = fetch_from_rss()

    if not items:
        logging.info("Geen RSS items gevonden, fallback naar HTML scraping...")
        items = fetch_from_html()

    if not items:
        logging.warning("Geen nieuwsberichten kunnen ophalen.")
        return

    # Pak maximaal de 5 meest recente unieke nieuwsberichten
    final_items = items[:5]

    output = {
        "updated_at": datetime.now().isoformat(),
        "total": len(final_items),
        "items": final_items
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logging.info(f"{len(final_items)} nieuwsberichten opgeslagen in {OUTPUT_FILE}:")
    for it in final_items:
        logging.info(f" - [{it['datum']}] {it['titel']}")

    return final_items


if __name__ == "__main__":
    update_nieuws()
