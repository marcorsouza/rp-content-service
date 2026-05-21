"""Ranking and filtering for discovered news."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from unicodedata import normalize

from app.config import Settings

SOURCE_WEIGHTS = {
    "Google News Corrida de Rua": 8,
    "Google News Maratona": 8,
    "Webrun": 12,
}

TERM_WEIGHTS = {
    "corrida de rua": 12,
    "maratona": 16,
    "meia maratona": 14,
    "trail run": 12,
    "trail": 10,
    "running": 8,
    "calendario": 8,
    "inscricoes": 8,
    "inscricoes abertas": 12,
    "circuito": 8,
    "recorde": 10,
    "brasil": 6,
    "brasileiro": 6,
    "atletas": 6,
}

ENGAGEMENT_PATTERNS = (
    (re.compile(r"\b\d+\s?mil\b"), 12, "volume de participantes"),
    (re.compile(r"\b\d{3,}\s+(participantes|atletas|inscritos)\b"), 10, "volume de participantes"),
    (
        re.compile(r"\b(guia|calendario|ranking|recorde|resultado|inscricoes abertas)\b"),
        8,
        "gancho editorial",
    ),
)


@dataclass(frozen=True)
class RankedNews:
    item: dict
    score: int
    reasons: list[str]


def _fold(value: str) -> str:
    return normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()


def _text(item: dict) -> str:
    return _fold(f"{item.get('originalTitle', '')} {item.get('description', '')}")


def _published_at_naive(item: dict) -> datetime | None:
    published_at = item.get("publishedAt")
    if not isinstance(published_at, datetime):
        return None
    if published_at.tzinfo:
        return published_at.astimezone(timezone.utc).replace(tzinfo=None)
    return published_at


def _canonical_title(item: dict) -> str:
    title = _fold(str(item.get("originalTitle", "")))
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return " ".join(title.split())


def rank_news_items(
    items: list[dict],
    settings: Settings,
    now: datetime | None = None,
) -> list[RankedNews]:
    """Filter stale/weak news and return the highest-ranked editorial candidates."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    required_terms = [_fold(term) for term in settings.news_required_term_list]
    blocked_terms = [_fold(term) for term in settings.news_blocked_term_list]

    ranked: list[RankedNews] = []
    seen_titles: set[str] = set()

    for item in items:
        text = _text(item)
        title_key = _canonical_title(item)
        if title_key and title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        if required_terms and not any(term in text for term in required_terms):
            continue
        if any(term in text for term in blocked_terms):
            continue

        published_at = _published_at_naive(item)
        if settings.news_require_published_at and published_at is None:
            continue

        age_hours: float | None = None
        if published_at:
            age_hours = max((now - published_at).total_seconds() / 3600, 0)
            if age_hours > settings.news_max_age_hours:
                continue

        score = SOURCE_WEIGHTS.get(str(item.get("sourceName", "")), 5)
        reasons = [f"fonte +{score}"]

        if age_hours is not None:
            if age_hours <= 12:
                score += 20
                reasons.append("recente +20")
            elif age_hours <= 24:
                score += 16
                reasons.append("recente +16")
            elif age_hours <= 48:
                score += 10
                reasons.append("recente +10")
            else:
                score += 5
                reasons.append("recente +5")

        for term, weight in TERM_WEIGHTS.items():
            if term in text:
                score += weight
                reasons.append(f"{term} +{weight}")

        for pattern, weight, reason in ENGAGEMENT_PATTERNS:
            if pattern.search(text):
                score += weight
                reasons.append(f"{reason} +{weight}")

        if score < settings.news_min_score:
            continue

        raw_payload = dict(item.get("rawPayload") or {})
        raw_payload["contentScore"] = score
        raw_payload["rankingReasons"] = reasons
        if published_at:
            raw_payload["publishedAt"] = published_at.isoformat()
        item = {**item, "rawPayload": raw_payload, "contentScore": score}
        ranked.append(RankedNews(item=item, score=score, reasons=reasons))

    ranked.sort(key=lambda news: news.score, reverse=True)
    return ranked[: settings.news_max_items_per_run]
