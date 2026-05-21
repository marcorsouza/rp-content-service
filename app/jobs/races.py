"""Job: descoberta de corridas por estado."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import classify_race_tier
from app.models import ContentDiscoveryRun, ContentSourceType, DiscoveredContentStatus, DiscoveredRace, DiscoveryRunStatus
from app.parsers import minhas_inscricoes, ticket_sports

logger = logging.getLogger(__name__)

SUPPORTED_STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "GO", "DF", "PE", "CE"]


def _dedup_key(race: dict) -> str:
    """Canonical key for deduplication: title + date + city + state."""
    title = (race.get("title") or "").lower().strip()
    date = race.get("eventDate")
    date_str = date.strftime("%Y-%m-%d") if isinstance(date, datetime) else ""
    city = (race.get("city") or "").lower().strip()
    state = (race.get("state") or "").upper()
    return f"{title}|{date_str}|{city}|{state}"


async def _is_duplicate(session: AsyncSession, race: dict) -> bool:
    """Check DB for existing DiscoveredRace with same dedup key."""
    title = (race.get("title") or "").strip()
    state = (race.get("state") or "").upper() or None
    city = (race.get("city") or "").strip() or None
    event_date = race.get("eventDate")

    stmt = select(DiscoveredRace).where(
        DiscoveredRace.title == title,
        DiscoveredRace.state == state,
    )
    if event_date:
        stmt = stmt.where(DiscoveredRace.eventDate == event_date)
    if city:
        stmt = stmt.where(DiscoveredRace.city == city)

    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def run_races_job(session: AsyncSession, state: str | None = None) -> dict:
    """
    Discover races from all configured parsers for the given state (or all states).
    Returns a summary dict.
    """
    states = [state.upper()] if state else SUPPORTED_STATES
    now = datetime.now(tz=timezone.utc)

    run = ContentDiscoveryRun(
        id=str(uuid.uuid4()),
        type=ContentSourceType.RACE,
        state=state.upper() if state else None,
        status=DiscoveryRunStatus.RUNNING,
        startedAt=now,
    )
    session.add(run)
    await session.commit()

    items_found = 0
    items_new = 0
    items_duplicate = 0
    errors: list[str] = []
    seen_keys: set[str] = set()  # within-run dedup

    async with httpx.AsyncClient(
        headers={"User-Agent": "RunPersonal-ContentRadar/1.0 (+https://runnerpersonal.zenslab.com.br)"},
        timeout=20,
    ) as client:
        for uf in states:
            for parser in (ticket_sports, minhas_inscricoes):
                try:
                    raw = await parser.fetch_races(uf, client)
                except Exception as exc:
                    errors.append(f"{parser.SOURCE_NAME} {uf}: {exc}")
                    logger.exception("Parser error: %s %s", parser.SOURCE_NAME, uf)
                    continue

                items_found += len(raw)

                for race_data in raw:
                    key = _dedup_key(race_data)
                    if key in seen_keys:
                        items_duplicate += 1
                        continue
                    seen_keys.add(key)

                    if await _is_duplicate(session, race_data):
                        items_duplicate += 1
                        continue

                    classification = await classify_race_tier(race_data)
                    race = DiscoveredRace(
                        id=str(uuid.uuid4()),
                        title=race_data["title"],
                        state=race_data.get("state"),
                        city=race_data.get("city"),
                        eventDate=race_data.get("eventDate"),
                        location=race_data.get("location"),
                        sourceUrl=race_data["sourceUrl"],
                        sourceName=race_data["sourceName"],
                        tier=classification.tier,
                        confidence=classification.confidence,
                        status=DiscoveredContentStatus.NEW,
                        aiSummary=classification.summary,
                        rawPayload=race_data.get("rawPayload"),
                        discoveryRunId=run.id,
                    )
                    session.add(race)
                    items_new += 1

    run.status = DiscoveryRunStatus.DONE if not errors else DiscoveryRunStatus.FAILED
    run.finishedAt = datetime.now(tz=timezone.utc)
    run.itemsFound = items_found
    run.itemsNew = items_new
    run.itemsDuplicate = items_duplicate
    run.errors = {"errors": errors} if errors else None

    await session.commit()

    return {
        "runId": run.id,
        "states": states,
        "itemsFound": items_found,
        "itemsNew": items_new,
        "itemsDuplicate": items_duplicate,
        "errors": errors,
    }
