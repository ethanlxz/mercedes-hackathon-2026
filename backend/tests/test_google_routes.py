import pytest

from backend.app.schemas.routes import RouteResponse, RouteSummary
from backend.app.trip_planner.schemas import TripPreferences
from backend.app.services import google_routes


class _Response:
    status_code = 200
    content = b"{}"

    def json(self):
        return {
            "routes": [
                {
                    "duration": "900s",
                    "distanceMeters": 10000,
                }
            ]
        }


class _Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, *args, **kwargs):
        return _Response()


@pytest.mark.asyncio
async def test_direct_trip_retries_when_preference_route_has_no_polyline(monkeypatch):
    fallback = RouteResponse(
        duration="840s",
        distanceMeters=9500,
        encodedPolyline="fallback-polyline",
        summary=RouteSummary(durationText="14 min", distanceText="9.5 km"),
    )

    async def fake_compute_route(origin, destination, api_key, **kwargs):
        assert origin == "Bandar Sunway"
        assert destination == "Mid Valley Megamall"
        assert kwargs["destination_place_id"] == "mid-valley-place-id"
        return fallback

    monkeypatch.setattr(google_routes.httpx, "AsyncClient", lambda **kwargs: _Client())
    monkeypatch.setattr(google_routes, "compute_route", fake_compute_route)

    route = await google_routes.compute_multi_stop_route(
        origin="Bandar Sunway",
        stops=[],
        destination="Mid Valley Megamall",
        preferences=TripPreferences(avoidHighways=True, avoidTolls=True),
        api_key="test-key",
        destination_place_id="mid-valley-place-id",
    )

    assert route.encodedPolyline == "fallback-polyline"
    assert route.legDurations == ["840s"]
