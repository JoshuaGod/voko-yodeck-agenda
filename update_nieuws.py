#!/usr/bin/env python3
"""
VOKO Digital Signage - Nieuws Scraper & Parser
Haalt de meest recente nieuwsberichten op van de VOKO website.
Filtert uitsluitend op nieuws van de afgelopen 3 maanden (90 dagen).
Opent elk nieuwsbericht om de volledige strekking/tekst (incl. opsommingen,
functies en tussenkopjes) en hoge resolutie afbeeldingen op te halen.
"""

import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

RSS_URL = "https://www.voko-oosterhout.nl/rss/nieuws/"
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
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_date_to_datetime(date_str: str) -> tuple[datetime | None, str]:
    """Parseert een datumstring naar een datetime object en een Nederlandse datumtekst."""
    if not date_str:
        return None, ""
    date_str = date_str.strip()

    # Formaat: "Sat, 03 Oct 2026 12:00:00 GMT"
    m_rfc = re.search(r"(\d{1,2})\s+([a-zA-Z]{3})\s+(\d{4})", date_str)
    if m_rfc:
        day = int(m_rfc.group(1))
        month_abbr = m_rfc.group(2).lower()
        year = int(m_rfc.group(3))
        month = DUTCH_MONTH_ABBR_MAP.get(month_abbr, 1)
        try:
            dt = datetime(year, month, day)
            month_name = DUTCH_MONTHS.get(month, "")
            return dt, f"{day} {month_name} {year}"
        except ValueError:
            pass

    # Formaat: ISO YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if m_iso:
        year = int(m_iso.group(1))
        month = int(m_iso.group(2))
        day = int(m_iso.group(3))
        try:
            dt = datetime(year, month, day)
            month_name = DUTCH_MONTHS.get(month, "")
            return dt, f"{day} {month_name} {year}"
        except ValueError:
            pass

    return None, date_str


def extract_article_details(detail_soup: BeautifulSoup) -> tuple[list[str], str | None]:
    """
    Haalt alle inhoudelijke alinea's, opsommingen en afbeeldingen
    uit een geopend nieuwsbericht op de VOKO website.
    """
    intro_el = detail_soup.find(class_="intro")
    intro_text = strip_html_tags(intro_el.get_text(separator=" ", strip=True)) if intro_el else ""

    vervolg_el = detail_soup.find(class_="vervolg")

    raw_paragraphs = []
    if intro_text:
        raw_paragraphs.append(intro_text)

    if vervolg_el:
        for child in vervolg_el.children:
            if not child:
                continue

            # 1. HTML Opsommingen (ul / ol)
            if child.name in ["ul", "ol"]:
                bullets = []
                for li in child.find_all("li"):
                    txt = li.get_text(separator=" ", strip=True)
                    if txt:
                        bullets.append(f"• {txt}")
                if bullets:
                    raw_paragraphs.append("\n".join(bullets))

            # 2. Paragrafen (<p>)
            elif child.name == "p":
                txt = child.get_text(separator=" ", strip=True)
                # Sla over als het een exacte of nagenoeg identieke herhaling is van de intro
                if txt and txt != intro_text and not (intro_text and intro_text.startswith(txt[:40])):
                    raw_paragraphs.append(txt)

            # 3. Tussenkopjes (h2, h3, h4)
            elif child.name in ["h2", "h3", "h4"]:
                t = child.get_text(separator=" ", strip=True)
                if t:
                    raw_paragraphs.append(t)

            # 4. Losse tekstregels (zoals bij de vacatures met * bullet points)
            elif child.name is None:
                lines = [l.strip() for l in str(child).split("\n") if l.strip()]
                for l in lines:
                    l_clean = html.unescape(re.sub(r"<[^>]+>", "", l)).strip()
                    if l_clean.startswith("*") or l_clean.startswith("-"):
                        bullet = "• " + l_clean.lstrip("*- ").strip()
                        raw_paragraphs.append(bullet)
                    elif len(l_clean) > 5 and l_clean != intro_text:
                        raw_paragraphs.append(l_clean)

    # Voeg opeenvolgende losse bullet points samen tot 1 lijst-alinea
    cleaned_paragraphs = []
    bullet_group = []
    for p in raw_paragraphs:
        if p.startswith("•"):
            bullet_group.append(p)
        else:
            if bullet_group:
                cleaned_paragraphs.append("\n".join(bullet_group))
                bullet_group = []
            cleaned_paragraphs.append(p)
    if bullet_group:
        cleaned_paragraphs.append("\n".join(bullet_group))

    # Zoek afbeelding
    image_url = None
    img_meta = detail_soup.select_one('meta[itemprop="image"]')
    if img_meta and img_meta.get("content"):
        image_url = img_meta.get("content")
    if not image_url:
        img_tag = detail_soup.select_one(".afbeelding img, img.thumbnail, img")
        if img_tag and img_tag.get("src"):
            src = img_tag.get("src")
            if not src.startswith("http"):
                src = f"https://www.voko-oosterhout.nl{src}"
            image_url = src

    return cleaned_paragraphs, image_url


def fetch_full_article(link: str, fallback_desc: str) -> tuple[str, list[str], str | None]:
    """Opent de webpagina van het nieuwsbericht om de volledige inhoud op te halen."""
    if link:
        try:
            resp = requests.get(link, headers=HEADERS, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                detail = soup.select_one(".nieuwsbericht-actief, .bericht.nieuws, .nieuws-detail")
                if detail:
                    paragraphs, img = extract_article_details(detail)
                    if paragraphs:
                        full_body = "\n\n".join(paragraphs)
                        return full_body, paragraphs, img
            logging.warning(f"Artikel {link} bevat geen actief berichtelement.")
        except Exception as e:
            logging.warning(f"Kon artikelpagina {link} niet openen: {e}")

    # Fallback op de RSS beschrijving
    clean_desc = strip_html_tags(fallback_desc)
    paragraphs = [clean_desc] if clean_desc else []
    return clean_desc, paragraphs, None


def update_nieuws():
    logging.info("Starten met ophalen van nieuwsberichten...")

    # Filter: uitsluitend nieuws van de afgelopen 3 maanden (90 dagen)
    today = datetime.now()
    cutoff_date = today - timedelta(days=90)
    logging.info(f"Peildatum: {today.strftime('%Y-%m-%d')} | Cutoff (3 maanden): {cutoff_date.strftime('%Y-%m-%d')}")

    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        logging.error(f"Fout bij ophalen RSS feed: {e}")
        return []

    channel = root.find("channel")
    if channel is None:
        logging.error("RSS feed bevat geen channel")
        return []

    seen = set()
    articles = []

    for item_el in channel.findall("item"):
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        pub_date_raw = (item_el.findtext("pubDate") or "").strip()
        desc_raw = (item_el.findtext("description") or "").strip()

        # 1. Filter op afgelopen 3 maanden
        dt, formatted_date = parse_date_to_datetime(pub_date_raw)
        if dt and dt < cutoff_date:
            continue

        # 2. Dedupliceer
        dedup_key = (title, link)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        # 3. Zoek afbeelding in <enclosure>
        rss_image_url = None
        enclosure = item_el.find("enclosure")
        if enclosure is not None:
            url = enclosure.get("url")
            if url:
                rss_image_url = url

        # 4. Open het nieuwsbericht op de website voor de volledige inhoud
        full_text, paragraphs, article_image_url = fetch_full_article(link, desc_raw)
        final_image = article_image_url or rss_image_url

        is_flyer = False
        if final_image and ("afbeelding_" in final_image or "poster" in final_image.lower()):
            is_flyer = True

        if title:
            articles.append({
                "titel": title,
                "datum": formatted_date,
                "iso_datum": dt.isoformat() if dt else "",
                "tekst": full_text,
                "paragrafen": paragraphs,
                "link": link,
                "afbeelding": final_image,
                "is_flyer": is_flyer
            })

    # Sorteer op datum aflopend (nieuwste eerst)
    articles.sort(key=lambda x: x["iso_datum"], reverse=True)

    output = {
        "updated_at": datetime.now().isoformat(),
        "filter": "afgelopen 3 maanden",
        "total": len(articles),
        "items": articles
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logging.info(f"{len(articles)} actuele nieuwsberichten van de afgelopen 3 maanden opgeslagen in {OUTPUT_FILE}:")
    for a in articles:
        logging.info(f" - [{a['datum']}] {a['titel']} ({len(a['paragrafen'])} alinea's/secties)")

    return articles


if __name__ == "__main__":
    update_nieuws()
