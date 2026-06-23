from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import battery as battery_router


class FakeBatteryService:
    ready = True
    last_error = ""

    def safe_load_or_train(self) -> None:
        return None

    def summary(self):
        return {
            "row_count": 100,
            "battery_capacity_kwh": 90.0,
            "weekdays": battery_router.WEEKDAYS,
            "weekday_stats": [
                {
                    "day_of_week": "Monday",
                    "expected_distance_km": 60.0,
                    "expected_battery_used_percent": 12.0,
                    "average_efficiency_wh_km": 145.0,
                }
            ],
            "metrics": {"trip_required_battery_percent": {"mae": 1.1, "r2": 0.9}},
        }

    def predict_trip(self, distance_km):
        return {
            "required_battery_percent": 18.5,
            "distance_km": distance_km,
            "message": "Estimated battery required based on your historical driving data.",
        }

    def predict_daily(self, day_of_week):
        return {
            "day_of_week": day_of_week,
            "expected_distance_km": 81.2,
            "expected_battery_used_percent": 16.4,
        }


def test_battery_summary_returns_dataset_and_model_details(monkeypatch):
    monkeypatch.setattr(battery_router, "model_service", FakeBatteryService())
    client = TestClient(app)

    response = client.get("/api/battery/model/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == 100
    assert payload["battery_capacity_kwh"] == 90.0
    assert "Monday" in payload["weekdays"]
    assert "metrics" in payload


def test_battery_trip_prediction_accepts_valid_distance(monkeypatch):
    monkeypatch.setattr(battery_router, "model_service", FakeBatteryService())
    client = TestClient(app)

    response = client.post("/api/battery/predict/trip", json={"distance_km": 80})

    assert response.status_code == 200
    assert response.json()["required_battery_percent"] == 18.5


def test_battery_trip_prediction_rejects_invalid_distance(monkeypatch):
    monkeypatch.setattr(battery_router, "model_service", FakeBatteryService())
    client = TestClient(app)

    response = client.post("/api/battery/predict/trip", json={"distance_km": 0})

    assert response.status_code == 422


def test_battery_daily_prediction_accepts_valid_weekday(monkeypatch):
    monkeypatch.setattr(battery_router, "model_service", FakeBatteryService())
    client = TestClient(app)

    response = client.post("/api/battery/predict/daily", json={"day_of_week": "Tuesday"})

    assert response.status_code == 200
    assert response.json()["day_of_week"] == "Tuesday"


def test_battery_daily_prediction_rejects_invalid_weekday(monkeypatch):
    monkeypatch.setattr(battery_router, "model_service", FakeBatteryService())
    client = TestClient(app)

    response = client.post("/api/battery/predict/daily", json={"day_of_week": "Funday"})

    assert response.status_code == 422
    assert "day_of_week must be one of" in response.json()["detail"]


def test_battery_model_unready_returns_service_unavailable(monkeypatch):
    class UnreadyBatteryService(FakeBatteryService):
        ready = False

        def predict_trip(self, distance_km):
            raise RuntimeError("Battery optimizer models are not ready yet.")

    monkeypatch.setattr(battery_router, "model_service", UnreadyBatteryService())
    client = TestClient(app)

    response = client.post("/api/battery/predict/trip", json={"distance_km": 80})

    assert response.status_code == 503
    assert response.json()["detail"] == "Battery optimizer models are not ready yet."
