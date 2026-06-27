from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import maps as maps_router
from backend.app.schemas.preferences import PreferenceMemoryResponse, PreferenceMemoryItem


def test_settings_returns_ev_battery_level(monkeypatch):
    monkeypatch.setattr(
        maps_router,
        "get_user_settings",
        lambda: {"currentLocation": "Kuala Lumpur", "evBatteryLevel": 64},
    )
    monkeypatch.setattr(
        maps_router,
        "get_preference_memory_summary",
        lambda: PreferenceMemoryResponse(
            preferredStopTypes=[PreferenceMemoryItem(category="Cafe", count=2)]
        ),
    )

    client = TestClient(app)
    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["evBatteryLevel"] == 64
    assert response.json()["preferenceMemory"]["preferredStopTypes"][0]["category"] == "Cafe"


def test_save_ev_battery_level(monkeypatch):
    saved_levels = []

    def fake_set_ev_battery_level(level):
        saved_levels.append(level)
        return {"currentLocation": "Kuala Lumpur", "evBatteryLevel": level}

    monkeypatch.setattr(maps_router, "set_ev_battery_level", fake_set_ev_battery_level)

    client = TestClient(app)
    response = client.post("/api/settings/ev-battery-level", json={"level": 71})

    assert response.status_code == 200
    assert response.json()["evBatteryLevel"] == 71
    assert saved_levels == [71]


def test_save_ev_battery_level_rejects_out_of_range():
    client = TestClient(app)
    response = client.post("/api/settings/ev-battery-level", json={"level": 101})

    assert response.status_code == 422
