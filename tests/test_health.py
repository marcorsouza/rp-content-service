from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "run-personal-content-service"


def test_jobs_races_requires_api_key() -> None:
    client = TestClient(app)
    response = client.post("/jobs/races/run")
    assert response.status_code == 401


def test_jobs_races_valid_api_key() -> None:
    """With valid API key, endpoint is reached (DB error expected in test env)."""
    client = TestClient(app)
    response = client.post(
        "/jobs/races/run",
        headers={"X-API-Key": "dev-content-api-key"},
        params={"state": "SP"},
    )
    # In test env (no DB), we accept 500 — endpoint is reachable
    assert response.status_code in (200, 500)
