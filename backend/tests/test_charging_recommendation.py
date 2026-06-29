import pytest

from backend.app.central_agent import charging_service
from backend.app.central_agent.schemas import (
    ChargingRecommendationRequest,
    ChargingStopAcceptRequest,
    RestStopPlace,
)
from backend.app.central_agent.state import (
    clear_active_road_trips,
    store_active_road_trip,
)
from backend.app.schemas.routes import RouteResponse, RouteSummary
from backend.app.services.google_places import ResolvedPlace


ENCODED_POLYLINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


class FakeBatteryService:
    def __init__(self, required_battery_percent: float) -> None:
        self.required_battery_percent = required_battery_percent
        self.distances: list[float] = []

    def predict_trip(self, distance_km: float):
        self.distances.append(distance_km)
        return {
            "required_battery_percent": self.required_battery_percent,
            "distance_km": distance_km,
        }


def _route(distance_meters: int = 352000) -> RouteResponse:
    return RouteResponse(
        duration="14400s",
        distanceMeters=distance_meters,
        encodedPolyline=ENCODED_POLYLINE,
        summary=RouteSummary(durationText="4 hr", distanceText="352 km"),
    )


def _charger(
    name: str = "Green DC Charger",
    latitude: float = 4.6,
    longitude: float = 101.1,
) -> ResolvedPlace:
    return ResolvedPlace(
        label=name,
        address="North-South Expressway, Tapah, Perak",
        place_id=name.lower().replace(" ", "-"),
        latitude=latitude,
        longitude=longitude,
        rating=4.4,
        user_rating_count=120,
        google_maps_uri="https://maps.google.com/?cid=charger",
    )


@pytest.fixture(autouse=True)
def clear_routes():
    clear_active_road_trips()
    yield
    clear_active_road_trips()


@pytest.mark.asyncio
async def test_charging_recommendation_uses_battery_optimizer_and_skips_search(monkeypatch):
    battery = FakeBatteryService(required_battery_percent=40)
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )

    async def fail_search(**kwargs):
        raise AssertionError("search should not run when no charging is needed")

    monkeypatch.setattr(charging_service, "battery_model_service", battery)
    monkeypatch.setattr(charging_service, "get_user_settings", lambda: {"evBatteryLevel": 82})
    monkeypatch.setattr(charging_service, "search_places", fail_search)

    response = await charging_service.recommend_charging(
        ChargingRecommendationRequest(activeRouteId=active.route_id),
        api_key="google-key",
    )

    recommendation = response.recommendation
    assert recommendation is not None
    assert battery.distances == [352.0]
    assert recommendation.decision == "no_charging_required"
    assert recommendation.chargingRequired is False
    assert recommendation.remainingBatteryPercent == 42
    assert recommendation.place is None
    assert recommendation.stations == []


@pytest.mark.asyncio
async def test_charging_recommendation_charge_before_departure(monkeypatch):
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )
    search_points = []

    async def fake_search_places(**kwargs):
        assert kwargs["included_type"] == "electric_vehicle_charging_station"
        assert kwargs["location_bias"] is not None
        search_points.append(kwargs["location_bias"])
        return [
            _charger("Start DC Charger A", latitude=38.51, longitude=-120.2),
            _charger("Start DC Charger B", latitude=39.01, longitude=-120.8),
            _charger("Start DC Charger C", latitude=40.0, longitude=-120.9),
        ]

    monkeypatch.setattr(charging_service, "battery_model_service", FakeBatteryService(10))
    monkeypatch.setattr(charging_service, "get_user_settings", lambda: {"evBatteryLevel": 15})
    monkeypatch.setattr(charging_service, "search_places", fake_search_places)

    response = await charging_service.recommend_charging(
        ChargingRecommendationRequest(activeRouteId=active.route_id),
        api_key="google-key",
    )

    recommendation = response.recommendation
    assert recommendation is not None
    assert recommendation.decision == "charge_before_departure"
    assert len(search_points) == 1
    assert recommendation.place.name == "Start DC Charger A"
    assert len(recommendation.stations) == 3
    assert recommendation.stations[0].place.name == "Start DC Charger A"
    assert recommendation.stations[0].distanceLabel == "Near starting point"
    assert "Charge before starting" in recommendation.message


@pytest.mark.asyncio
async def test_charging_recommendation_charge_during_trip(monkeypatch):
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )
    search_points = []

    async def fake_search_places(**kwargs):
        search_points.append(kwargs["location_bias"])
        if len(search_points) == 1:
            return [_charger("Origin DC Charger", latitude=38.51, longitude=-120.2)]
        return [
            _charger("Midway DC Charger A", latitude=39.01, longitude=-120.8),
            _charger("Midway DC Charger B", latitude=40.0, longitude=-120.9),
        ]

    monkeypatch.setattr(charging_service, "battery_model_service", FakeBatteryService(72))
    monkeypatch.setattr(charging_service, "get_user_settings", lambda: {"evBatteryLevel": 48})
    monkeypatch.setattr(charging_service, "search_places", fake_search_places)

    response = await charging_service.recommend_charging(
        ChargingRecommendationRequest(activeRouteId=active.route_id),
        api_key="google-key",
    )

    recommendation = response.recommendation
    assert recommendation is not None
    assert recommendation.decision == "charge_during_trip"
    assert recommendation.triggerDistanceKm == pytest.approx(136.9)
    assert recommendation.distanceLabel == "Around 136.9 km from start"
    assert len(search_points) == 2
    assert recommendation.place.name.startswith("Midway DC Charger")
    assert len(recommendation.stations) == 3
    assert recommendation.stations[0].place.name == recommendation.place.name
    assert recommendation.stations[0].distanceLabel == "Around 136.9 km from start"
    assert recommendation.stations[-1].distanceLabel == "Near starting point"


@pytest.mark.asyncio
async def test_charging_recommendation_charge_near_destination(monkeypatch):
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )
    search_points = []

    async def fake_search_places(**kwargs):
        search_points.append(kwargs["location_bias"])
        duplicate = _charger("Shared DC Charger", latitude=43.252, longitude=-126.453)
        if len(search_points) == 1:
            return [
                duplicate,
                _charger("Origin DC Charger", latitude=38.51, longitude=-120.2),
            ]
        return [
            duplicate,
            _charger("Destination DC Charger A", latitude=43.3, longitude=-126.5),
            _charger("Destination DC Charger B", latitude=43.4, longitude=-126.6),
            _charger("Destination DC Charger C", latitude=43.5, longitude=-126.7),
        ]

    monkeypatch.setattr(charging_service, "battery_model_service", FakeBatteryService(35))
    monkeypatch.setattr(charging_service, "get_user_settings", lambda: {"evBatteryLevel": 48})
    monkeypatch.setattr(charging_service, "search_places", fake_search_places)

    response = await charging_service.recommend_charging(
        ChargingRecommendationRequest(activeRouteId=active.route_id),
        api_key="google-key",
    )

    recommendation = response.recommendation
    assert recommendation is not None
    assert recommendation.decision == "charge_near_destination"
    assert recommendation.remainingBatteryPercent == 13
    assert recommendation.triggerDistanceKm == 352
    assert len(search_points) == 2
    assert recommendation.place.name in {
        "Shared DC Charger",
        "Destination DC Charger A",
        "Destination DC Charger B",
        "Destination DC Charger C",
    }
    assert len(recommendation.stations) == 3
    assert len({station.place.placeId for station in recommendation.stations}) == 3
    assert "shared-dc-charger" in {station.place.placeId for station in recommendation.stations}
    assert recommendation.stations[0].distanceLabel == "Near destination"


@pytest.mark.asyncio
async def test_accepting_charger_stop_recomputes_route(monkeypatch):
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )
    place = RestStopPlace(
        name="Tapah DC Charger",
        address="North-South Expressway, Tapah",
        placeId="tapah-dc",
        rating=4.3,
        userRatingCount=80,
    )

    async def fake_compute_multi_stop_route(**kwargs):
        assert kwargs["origin"] == "Kuala Lumpur"
        assert kwargs["stops"] == ["North-South Expressway, Tapah"]
        assert kwargs["destination"] == "Penang"
        assert kwargs["stop_place_ids"] == ["tapah-dc"]
        return RouteResponse(
            duration="15000s",
            distanceMeters=356000,
            encodedPolyline="encoded",
            summary=RouteSummary(durationText="4 hr 10 min", distanceText="356 km"),
        )

    monkeypatch.setattr(
        charging_service,
        "compute_multi_stop_route",
        fake_compute_multi_stop_route,
    )

    route = await charging_service.accept_charging_stop(
        ChargingStopAcceptRequest(
            activeRouteId=active.route_id,
            notificationId="charge-1",
            place=place,
        ),
        api_key="google-key",
    )

    assert route.distanceMeters == 356000
    assert [waypoint.role for waypoint in route.waypoints] == [
        "origin",
        "stop",
        "destination",
    ]
    assert route.waypoints[1].label == "Charge: Tapah DC Charger"
