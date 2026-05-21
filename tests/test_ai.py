from app.ai import heuristic_race_classification


def test_heuristic_classifies_major_marathon_as_tier_1() -> None:
    result = heuristic_race_classification({"title": "Maratona do Rio", "city": "Rio de Janeiro", "state": "RJ"})

    assert result.tier == 1
    assert result.confidence >= 0.8
    assert "tier 1" in result.summary


def test_heuristic_classifies_local_race_as_tier_3() -> None:
    result = heuristic_race_classification({"title": "Corrida Beneficente do Bairro", "city": "Campinas", "state": "SP"})

    assert result.tier == 3
    assert 0 <= result.confidence <= 1
