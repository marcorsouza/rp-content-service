"""AI helpers for content classification and editorial suggestions."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from openai import AsyncOpenAI

from app.config import get_settings
from app.text_cleanup import clean_external_text, clean_news_description, split_title_source

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RaceClassification:
    tier: int
    confidence: float
    summary: str


@dataclass(frozen=True)
class NewsSuggestion:
    suggested_title: str
    summary: str
    category: str
    confidence: float


TIER_1_KEYWORDS = (
    "maratona",
    "marathon",
    "meia maratona",
    "half marathon",
    "track&field",
    "track & field",
    "sp city",
    "rio marathon",
    "w21k",
    "circuito das estacoes",
    "circuito das estações",
)

TIER_2_KEYWORDS = (
    "circuito",
    "etapa",
    "10k",
    "21k",
    "night run",
    "run series",
    "trail",
    "ultra",
)


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, round(value, 2)))


def heuristic_race_classification(race: dict) -> RaceClassification:
    """Deterministic fallback for environments without OpenAI credentials."""
    title = (race.get("title") or "").lower()
    location = " ".join(
        part
        for part in (
            race.get("city") or "",
            race.get("state") or "",
            race.get("location") or "",
        )
        if part
    )

    if any(keyword in title for keyword in TIER_1_KEYWORDS):
        tier = 1
        confidence = 0.82
    elif any(keyword in title for keyword in TIER_2_KEYWORDS):
        tier = 2
        confidence = 0.72
    else:
        tier = 3
        confidence = 0.62

    summary = (
        f"Corrida classificada como tier {tier} com base no nome do evento"
        f"{' e localidade' if location else ''}. Revisar data, cidade e link antes de publicar."
    )
    return RaceClassification(tier=tier, confidence=confidence, summary=summary)


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("AI response does not contain a JSON object")
    return json.loads(match.group(0))


async def classify_race_tier(race: dict) -> RaceClassification:
    """Classify a discovered race into tier 1/2/3 with a confidence score."""
    settings = get_settings()
    if not settings.openai_api_key:
        return heuristic_race_classification(race)

    event_date = race.get("eventDate")
    if isinstance(event_date, datetime):
        event_date = event_date.date().isoformat()

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = {
        "title": race.get("title"),
        "state": race.get("state"),
        "city": race.get("city"),
        "location": race.get("location"),
        "eventDate": event_date,
        "sourceName": race.get("sourceName"),
    }

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classifique corridas de rua brasileiras para curadoria editorial. "
                        "Retorne somente JSON: tier inteiro 1, 2 ou 3; confidence entre 0 e 1; "
                        "summary curto em portugues. Tier 1 sao provas nacionais/famosas; "
                        "tier 2 regionais relevantes; tier 3 locais/municipais."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or ""
        data = _parse_json_object(content)
        tier = int(data.get("tier", 3))
        if tier not in (1, 2, 3):
            tier = 3
        confidence = _clamp_confidence(float(data.get("confidence", 0.5)))
        summary = str(data.get("summary") or "").strip()
        if not summary:
            summary = heuristic_race_classification(race).summary
        return RaceClassification(tier=tier, confidence=confidence, summary=summary[:500])
    except Exception as exc:
        logger.warning("AI race classification failed, using heuristic fallback: %s", exc)
        return heuristic_race_classification(race)


def heuristic_news_suggestion(item: dict) -> NewsSuggestion:
    title, _source = split_title_source(str(item.get("originalTitle") or item.get("title") or ""))
    description = clean_news_description(
        str(item.get("description") or ""),
        title,
        str(item.get("sourceName") or ""),
    )
    text = f"{title} {description}".lower()

    if any(keyword in text for keyword in ("maratona", "corrida", "prova", "inscricao", "calendario")):
        category = "RACE"
    elif any(keyword in text for keyword in ("saude", "lesao", "nutricao", "cardio", "sono")):
        category = "HEALTH"
    elif any(keyword in text for keyword in ("treino", "pace", "performance", "recorde", "elite")):
        category = "PERFORMANCE"
    elif any(keyword in text for keyword in ("mercado", "marca", "evento", "patrocinio")):
        category = "MARKET"
    else:
        category = "GENERAL"

    suggested_title = title[:120] if title else "Noticia de corrida para revisar"
    summary = description[:500] if description else (
        f"Noticia para curadoria sobre: {title}. Confirmar detalhes na fonte antes de publicar."
    )
    return NewsSuggestion(
        suggested_title=suggested_title,
        summary=summary,
        category=category,
        confidence=0.62,
    )


async def suggest_news_draft(item: dict) -> NewsSuggestion:
    settings = get_settings()
    if not settings.openai_api_key:
        return heuristic_news_suggestion(item)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = {
        "originalTitle": item.get("originalTitle") or item.get("title"),
        "description": item.get("description"),
        "sourceName": item.get("sourceName"),
        "sourceUrl": item.get("sourceUrl"),
        "publishedAt": item.get("publishedAt"),
    }

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Voce prepara rascunhos editoriais originais sobre corrida. "
                        "Nao copie a materia. Retorne somente JSON com suggestedTitle, summary, "
                        "category em RACE, HEALTH, PERFORMANCE, MARKET ou GENERAL, e confidence 0-1."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or ""
        data = _parse_json_object(content)
        category = str(data.get("category") or "GENERAL").upper()
        if category not in {"RACE", "HEALTH", "PERFORMANCE", "MARKET", "GENERAL"}:
            category = "GENERAL"
        return NewsSuggestion(
            suggested_title=split_title_source(
                str(data.get("suggestedTitle") or data.get("suggested_title") or "")
            )[0][:140],
            summary=clean_external_text(str(data.get("summary") or ""))[:900],
            category=category,
            confidence=_clamp_confidence(float(data.get("confidence", 0.5))),
        )
    except Exception as exc:
        logger.warning("AI news suggestion failed, using heuristic fallback: %s", exc)
        return heuristic_news_suggestion(item)
