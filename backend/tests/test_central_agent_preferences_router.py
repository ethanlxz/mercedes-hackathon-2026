from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import memory_service


def test_central_agent_preference_feedback_and_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_service, "MEMORY_FILE", tmp_path / "user_memory.json")
    client = TestClient(app)

    response = client.post(
        "/api/central-agent/preferences/feedback",
        json={
            "action": "close",
            "id": "route-123",
            "placeId": "place-123",
            "name": "Scenic View",
            "address": "Jalan View",
            "category": "Scenic stop",
            "section": "route",
        },
    )

    assert response.status_code == 200
    assert response.json()["dislikedStopTypes"][0]["category"] == "Scenic stop"

    reset = client.delete("/api/central-agent/preferences")

    assert reset.status_code == 200
    assert reset.json() == {"preferredStopTypes": [], "dislikedStopTypes": []}


def test_central_agent_preference_can_unlove(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_service, "MEMORY_FILE", tmp_path / "user_memory.json")
    client = TestClient(app)
    payload = {
        "id": "food-123",
        "placeId": "place-123",
        "name": "Coffee House",
        "address": "Jalan Coffee",
        "category": "Cafe",
        "section": "food",
    }

    loved = client.post(
        "/api/central-agent/preferences/feedback",
        json={**payload, "action": "love"},
    )
    unliked = client.post(
        "/api/central-agent/preferences/feedback",
        json={**payload, "action": "unlove"},
    )

    assert loved.status_code == 200
    assert loved.json()["preferredStopTypes"][0]["category"] == "Cafe"
    assert unliked.status_code == 200
    assert unliked.json()["preferredStopTypes"] == []
