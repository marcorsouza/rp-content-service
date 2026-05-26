"""Parser para Ticket Sports — busca corridas por estado."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCE_NAME = "Ticket Sports"
BASE_URL = "https://www.ticketsports.com.br"

STATE_SLUGS: dict[str, str] = {
    "SP": "sao-paulo",
    "RJ": "rio-de-janeiro",
    "MG": "minas-gerais",
    "RS": "rio-grande-do-sul",
    "PR": "parana",
    "SC": "santa-catarina",
    "BA": "bahia",
    "GO": "goias",
    "DF": "distrito-federal",
    "PE": "pernambuco",
    "CE": "ceara",
}


def _parse_date(text: str) -> datetime | None:
    """Try to parse common date formats found on the page."""
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d de %B de %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    # Try to extract digits pattern dd/mm/yyyy
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", text)
    if m:
        day, month, year = m.groups()
        if len(year) == 2:
            year = "20" + year
        try:
            return datetime(int(year), int(month), int(day))
        except ValueError:
            pass
    return None


async def fetch_races(state: str, client: httpx.AsyncClient) -> list[dict]:
    """Fetch and parse race listings from Ticket Sports for a given state UF."""
    slug = STATE_SLUGS.get(state.upper())
    if not slug:
        logger.warning("Estado %s nao suportado no Ticket Sports parser", state)
        return []

    url = f"{BASE_URL}/corrida-de-rua/{slug}"
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Erro ao buscar Ticket Sports (%s): %s", state, exc)
        return []

    await asyncio.sleep(1)  # rate limit

    # Diagnóstico: logar se a resposta parece SPA (sem conteúdo renderizado)
    body_preview = resp.text[:300].replace("\n", " ")
    logger.debug("Ticket Sports %s response preview: %s", state, body_preview)
    if len(resp.text) < 2000 or 'id="root"' in resp.text or 'id="app"' in resp.text:
        logger.warning(
            "Ticket Sports %s: resposta parece SPA (JavaScript rendering). "
            "HTML length=%d. Seletores CSS provavelmente não funcionarão.",
            state, len(resp.text),
        )

    soup = BeautifulSoup(resp.text, "html.parser")
    races: list[dict] = []

    # Ticket Sports event cards — selectors may need updating if site changes
    cards = soup.select(
        "div.event-card, article.event-item, div.card-event, "
        "div[class*='event'], div[class*='card'], article[class*='event']"
    )
    if not cards:
        # Fallback: look for any links with event-like text
        cards = soup.select("a[href*='/evento/'], a[href*='/corrida/'], a[href*='/event/']")
    logger.info("Ticket Sports %s: %d cards encontrados com seletores CSS", state, len(cards))

    for card in cards:
        title = (
            card.select_one("h2, h3, .event-title, .card-title, .title") or
            card
        )
        title_text = title.get_text(strip=True) if title else ""
        if not title_text or len(title_text) < 5:
            continue

        link_el = card if card.name == "a" else card.select_one("a")
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            href = BASE_URL + href

        date_el = card.select_one(".event-date, .date, time, [class*='date']")
        date_text = date_el.get_text(strip=True) if date_el else ""
        event_date = _parse_date(date_text)

        city_el = card.select_one(".event-city, .city, .location, [class*='city']")
        city_text = city_el.get_text(strip=True) if city_el else ""

        races.append({
            "title": title_text,
            "state": state.upper(),
            "city": city_text or None,
            "eventDate": event_date,
            "sourceUrl": href or url,
            "sourceName": SOURCE_NAME,
            "rawPayload": {"html_snippet": str(card)[:500]},
        })

    logger.info("Ticket Sports %s: %d corridas encontradas", state, len(races))
    return races
