from app.time import utc_now


def test_utc_now_returns_naive_datetime():
    assert utc_now().tzinfo is None
