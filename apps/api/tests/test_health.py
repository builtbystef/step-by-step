from fastapi.testclient import TestClient
from step_by_step_api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_greeting() -> None:
    response = client.get("/api/hello/Step%20by%20Step")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Step by Step!"}
