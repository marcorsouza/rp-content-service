from datetime import datetime, timedelta

from app.config import Settings
from app.news_ranking import rank_news_items


def test_rank_news_items_keeps_recent_engaging_news() -> None:
    now = datetime(2026, 5, 21, 12, 0, 0)
    settings = Settings(news_min_score=35, news_max_items_per_run=5)

    ranked = rank_news_items(
        [
            {
                "originalTitle": "Maratona abre inscricoes com 20 mil participantes",
                "description": "Corrida de rua tera atletas do Brasil.",
                "sourceName": "Google News Maratona",
                "sourceUrl": "https://example.com/1",
                "publishedAt": now - timedelta(hours=3),
                "rawPayload": {},
            }
        ],
        settings,
        now=now,
    )

    assert len(ranked) == 1
    assert ranked[0].score >= 35
    assert ranked[0].item["rawPayload"]["contentScore"] == ranked[0].score


def test_rank_news_items_filters_old_and_blocked_news() -> None:
    now = datetime(2026, 5, 21, 12, 0, 0)
    settings = Settings(news_max_age_hours=24, news_min_score=10)

    ranked = rank_news_items(
        [
            {
                "originalTitle": "Maratona antiga",
                "description": "Corrida de rua.",
                "sourceName": "Google News Maratona",
                "sourceUrl": "https://example.com/old",
                "publishedAt": now - timedelta(days=3),
                "rawPayload": {},
            },
            {
                "originalTitle": "Corrida aparece em noticia de futebol",
                "description": "Futebol domina o texto.",
                "sourceName": "Google News Corrida de Rua",
                "sourceUrl": "https://example.com/blocked",
                "publishedAt": now - timedelta(hours=1),
                "rawPayload": {},
            },
        ],
        settings,
        now=now,
    )

    assert ranked == []


def test_rank_news_items_limits_to_best_candidates() -> None:
    now = datetime(2026, 5, 21, 12, 0, 0)
    settings = Settings(news_min_score=1, news_max_items_per_run=1)

    ranked = rank_news_items(
        [
            {
                "originalTitle": "Corrida de rua local",
                "description": "Inscricoes abertas.",
                "sourceName": "Google News Corrida de Rua",
                "sourceUrl": "https://example.com/local",
                "publishedAt": now - timedelta(hours=2),
                "rawPayload": {},
            },
            {
                "originalTitle": "Maratona do Brasil tem recorde e 30 mil atletas",
                "description": "Corrida de rua com grande publico.",
                "sourceName": "Webrun",
                "sourceUrl": "https://example.com/top",
                "publishedAt": now - timedelta(hours=2),
                "rawPayload": {},
            },
        ],
        settings,
        now=now,
    )

    assert len(ranked) == 1
    assert ranked[0].item["sourceUrl"] == "https://example.com/top"
