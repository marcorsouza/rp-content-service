"""Job: descoberta de noticias por RSS."""
from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import suggest_news_draft
from app.config import get_settings
from app.models import (
    ContentDiscoveryRun,
    ContentSourceType,
    DiscoveredContentStatus,
    DiscoveredNews,
    DiscoveredNewsCategory,
    DiscoveryRunStatus,
)
from app.news_ranking import rank_news_items
from app.parsers.news_rss import fetch_news
from app.time import utc_now

logger = logging.getLogger(__name__)


async def _is_duplicate(session: AsyncSession, source_url: str) -> bool:
    result = await session.execute(
        select(DiscoveredNews.id).where(DiscoveredNews.sourceUrl == source_url)
    )
    return result.scalar_one_or_none() is not None


async def run_news_job(session: AsyncSession) -> dict:
    settings = get_settings()
    now = utc_now()
    run = ContentDiscoveryRun(
        id=str(uuid.uuid4()),
        type=ContentSourceType.NEWS,
        status=DiscoveryRunStatus.RUNNING,
        startedAt=now,
    )
    session.add(run)
    await session.commit()

    items_found = 0
    items_new = 0
    items_duplicate = 0
    errors: list[str] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": "RunPersonal-ContentRadar/1.0 (+https://runnerpersonal.zenslab.com.br)"},
        timeout=20,
    ) as client:
        try:
            raw_items = await fetch_news(client)
        except Exception as exc:
            raw_items = []
            errors.append(f"RSS: {exc}")
            logger.exception("News parser error")

    items_found = len(raw_items)
    ranked_items = rank_news_items(raw_items, settings, now=now)
    items_filtered = items_found - len(ranked_items)

    for ranked_item in ranked_items:
        item = ranked_item.item
        source_url = item["sourceUrl"]
        if source_url in seen_urls:
            items_duplicate += 1
            continue
        seen_urls.add(source_url)

        if await _is_duplicate(session, source_url):
            items_duplicate += 1
            continue

        suggestion = await suggest_news_draft(item)
        category = DiscoveredNewsCategory(suggestion.category)
        created_at = utc_now()
        news = DiscoveredNews(
            id=str(uuid.uuid4()),
            originalTitle=item["originalTitle"],
            suggestedTitle=suggestion.suggested_title,
            description=item.get("description") or None,
            summary=suggestion.summary,
            sourceUrl=source_url,
            sourceName=item["sourceName"],
            category=category,
            confidence=suggestion.confidence,
            status=DiscoveredContentStatus.NEW,
            rawPayload=item.get("rawPayload"),
            discoveryRunId=run.id,
            createdAt=created_at,
            updatedAt=created_at,
        )
        session.add(news)
        items_new += 1

    run.status = DiscoveryRunStatus.DONE if not errors else DiscoveryRunStatus.FAILED
    run.finishedAt = utc_now()
    run.itemsFound = items_found
    run.itemsNew = items_new
    run.itemsDuplicate = items_duplicate
    run.errors = {"errors": errors} if errors else None

    await session.commit()

    return {
        "runId": run.id,
        "itemsFound": items_found,
        "itemsRanked": len(ranked_items),
        "itemsFiltered": items_filtered,
        "itemsNew": items_new,
        "itemsDuplicate": items_duplicate,
        "errors": errors,
    }
