from app.ai import heuristic_news_suggestion


def test_heuristic_news_suggestion_categorizes_race_news() -> None:
    result = heuristic_news_suggestion(
        {
            "originalTitle": "Maratona abre inscricoes para nova etapa",
            "description": "Prova tera percursos de 5k e 10k.",
        }
    )

    assert result.category == "RACE"
    assert result.suggested_title.startswith("Maratona")
    assert 0 <= result.confidence <= 1
