"""AI helpers for content classification and editorial suggestions."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RaceClassification:
    tier: int
    confidence: float
    summary: str


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
