"""Parser para Minhas Inscrições — busca corridas por estado."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCE_NAME = "Minhas Inscrições"
BASE_URL = "https://www.minhasinscricoes.com.br"

STATE_PARAMS: dict[str, str] = {
    "SP": "SP", "RJ": "RJ", "MG": "MG", "RS": "RS",
    "PR": "PR", "SC": "SC", "BA": "BA", "GO": "GO",
    "DF": "DF", "PE": "PE", "CE": "CE",
}


def _parse_date(text: str) -> datetime | None:
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
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
    """Fetch and parse race listings from Minhas Inscrições for a given state UF."""
    uf = STATE_PARAMS.get(state.upper())
    if not uf:
        logger.warning("Estado %s nao suportado no Minhas Inscricoes parser", state)
        return []

    url = f"{BASE_URL}/eventos?esporte=corrida&estado={uf}"
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Erro ao buscar Minhas Inscricoes (%s): %s", state, exc)
        return []

    await asyncio.sleep(1)  # rate limit

    body_preview = resp.text[:300].replace("\n", " ")
    logger.debug("Minhas Inscrições %s response preview: %s", state, body_preview)
    if len(resp.text) < 2000 or 'id="root"' in resp.text or 'id="app"' in resp.text:
        logger.warning(
            "Minhas Inscrições %s: resposta parece SPA (JavaScript rendering). "
            "HTML length=%d. Seletores CSS provavelmente não funcionarão.",
            state, len(resp.text),
        )

    soup = BeautifulSoup(resp.text, "html.parser")
    races: list[dict] = []

    cards = soup.select(
        "div.event-card, div.evento-item, article.event, "
        "div[class*='event'], div[class*='evento'], li[class*='event']"
    )
    if not cards:
        cards = soup.select("a[href*='/evento/'], a[href*='/corrida/'], a[href*='/inscricao/']")
    logger.info("Minhas Inscrições %s: %d cards encontrados com seletores CSS", state, len(cards))

    for card in cards:
        title_el = card.select_one("h2, h3, .event-name, .title, .nome")
        title_text = title_el.get_text(strip=True) if title_el else card.get_text(strip=True)[:80]
        if not title_text or len(title_text) < 5:
            continue

        link_el = card if card.name == "a" else card.select_one("a")
        href = link_el.get("href", "") if link_el else ""
        if href and not href.startswith("http"):
            href = BASE_URL + href

        date_el = card.select_one(".event-date, .data, time, [class*='date']")
        date_text = date_el.get_text(strip=True) if date_el else ""
        event_date = _parse_date(date_text)

        city_el = card.select_one(".city, .cidade, .local, [class*='city']")
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

    logger.info("Minhas Inscricoes %s: %d corridas encontradas", state, len(races))
    return races
