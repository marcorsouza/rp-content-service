"""Descoberta de corridas via Google News RSS.

Consulta o Google News por estado para encontrar anúncios de corridas de rua.
Mais confiável que web scraping de SPAs, pois o Google News RSS é sempre disponível.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from datetime import datetime

import feedparser
import httpx

logger = logging.getLogger(__name__)

SOURCE_NAME = "Google News"

_STATE_NAMES: dict[str, str] = {
    "SP": "São Paulo",
    "RJ": "Rio de Janeiro",
    "MG": "Minas Gerais",
    "RS": "Rio Grande do Sul",
    "PR": "Paraná",
    "SC": "Santa Catarina",
    "BA": "Bahia",
    "GO": "Goiás",
    "DF": "Distrito Federal",
    "PE": "Pernambuco",
    "CE": "Ceará",
}

_MONTH_MAP: dict[str, int] = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

_DATE_RE = re.compile(
    r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b"
    r"|(\d{1,2})\s+de\s+(" + "|".join(_MONTH_MAP.keys()) + r")\s+(?:de\s+)?(\d{4})\b",
    re.IGNORECASE,
)

_RACE_KEYWORDS = frozenset([
    "corrida", "maratona", "meia maratona", "trail", "km", "inscrição",
    "inscrições", "atletismo", "largada", "percurso", "prova",
])

_NOISE_KEYWORDS = frozenset([
    "futebol", "bbb", "crime", "acidente", "loteria", "político", "política",
])


def _google_rss_url(query: str) -> str:
    return (
        "https://news.google.com/rss/search"
        f"?q={urllib.parse.quote(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )


def _extract_date(text: str) -> datetime | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    g = m.groups()
    try:
        if g[0] is not None:  # dd/mm/yyyy
            day, month, year = int(g[0]), int(g[1]), int(g[2])
            if year < 100:
                year += 2000
        else:  # dd de mês de yyyy
            day = int(g[3])
            month = _MONTH_MAP[g[4].lower()]
            year = int(g[5])
        return datetime(year, month, day)
    except (ValueError, KeyError):
        return None


def _is_race_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    if any(kw in text for kw in _NOISE_KEYWORDS):
        return False
    return any(kw in text for kw in _RACE_KEYWORDS)


async def fetch_races(state: str, client: httpx.AsyncClient) -> list[dict]:
    state_name = _STATE_NAMES.get(state.upper())
    if not state_name:
        logger.warning("Estado %s não mapeado no parser Google News Races", state)
        return []

    queries = [
        f'corrida de rua "{state_name}" inscrições 2026',
        f'(maratona OR "meia maratona") "{state_name}" 2026',
        f'corrida "{state_name}" km largada 2026',
    ]

    seen_urls: set[str] = set()
    races: list[dict] = []

    for query in queries:
        url = _google_rss_url(query)
        try:
            resp = await client.get(url, follow_redirects=True, timeout=20)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Erro ao buscar Google News Races [%s]: %s", query, exc)
            continue

        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:15]:
            title = str(getattr(entry, "title", "")).strip()
            link = str(getattr(entry, "link", "")).strip()
            summary = str(getattr(entry, "summary", "")).strip()

            if not title or not link:
                continue

            # Deduplicate by URL
            # Google News wraps links — use the link as-is for dedup
            if link in seen_urls:
                continue
            seen_urls.add(link)

            if not _is_race_relevant(title, summary):
                continue

            event_date = _extract_date(f"{title} {summary}")

            races.append({
                "title": title,
                "state": state.upper(),
                "city": None,
                "eventDate": event_date,
                "sourceUrl": link,
                "sourceName": SOURCE_NAME,
                "rawPayload": {
                    "title": title,
                    "summary": summary[:500],
                    "query": query,
                },
            })

    logger.info("Google News Races %s: %d corridas encontradas", state, len(races))
    return races
