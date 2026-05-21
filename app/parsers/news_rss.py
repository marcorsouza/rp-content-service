"""RSS parsers for running news discovery."""
from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx

logger = logging.getLogger(__name__)

DEFAULT_FEEDS: tuple[tuple[str, str], ...] = (
    ("Google News Corrida de Rua", "https://news.google.com/rss/search?q=corrida%20de%20rua%20Brasil&hl=pt-BR&gl=BR&ceid=BR:pt-419"),
    ("Google News Maratona", "https://news.google.com/rss/search?q=maratona%20Brasil&hl=pt-BR&gl=BR&ceid=BR:pt-419"),
    ("Webrun", "https://www.webrun.com.br/feed/"),
)


def _published_at(entry) -> datetime | None:
    value = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


async def fetch_news(client: httpx.AsyncClient, feeds: tuple[tuple[str, str], ...] = DEFAULT_FEEDS) -> list[dict]:
    items: list[dict] = []

    for source_name, url in feeds:
        try:
            response = await client.get(url, follow_redirects=True, timeout=20)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Erro ao buscar RSS %s: %s", source_name, exc)
            continue

        parsed = feedparser.parse(response.text)
        for entry in parsed.entries[:30]:
            title = str(getattr(entry, "title", "")).strip()
            link = str(getattr(entry, "link", "")).strip()
            if not title or not link:
                continue
            description = str(getattr(entry, "summary", "") or getattr(entry, "description", "")).strip()
            items.append(
                {
                    "originalTitle": title,
                    "description": description,
                    "sourceUrl": link,
                    "sourceName": source_name,
                    "publishedAt": _published_at(entry),
                    "rawPayload": {
                        "title": title,
                        "link": link,
                        "summary": description[:1000],
                    },
                }
            )

    logger.info("RSS news: %d noticias encontradas", len(items))
    return items
