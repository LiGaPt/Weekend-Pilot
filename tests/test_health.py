from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_check_returns_service_metadata() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "weekend-pilot"
    assert "environment" in body
    assert "version" in body
