import pytest

from backend.app.schemas.routes import RouteResponse, RouteSummary
from backend.app.services.google_places import ResolvedPlace
from backend.app.services import road_trip_planner_service as planner


ENCODED_POLYLINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


@pytest.mark.asyncio
async def test_road_trip_recommendations_keep_google_formatted_address(monkeypatch):
    async def fake_route(origin, destination, api_key):
        return RouteResponse(
            duration="3600s",
            distanceMeters=120000,
            encodedPolyline=ENCODED_POLYLINE,
            summary=RouteSummary(durationText="1 hr", distanceText="120 km"),
        )

    async def fake_search_places(**kwargs):
        query = kwargs["text_query"].split(" in ", 1)[0]
        if query == "attractions":
            return [
                ResolvedPlace(
                    label="Ipoh Heritage Walk",
                    address="Jalan Panglima, 30000 Ipoh, Perak, Malaysia",
                    place_id="ipoh-heritage",
                    latitude=4.5975,
                    longitude=101.0901,
                    rating=4.5,
                    user_rating_count=1200,
                    google_maps_uri="https://maps.google.com/?cid=ipoh",
                )
            ]
        if query == "restaurants":
            return [
                ResolvedPlace(
                    label="Penang Local Kitchen",
                    address="Lebuh Chulia, George Town, 10200 George Town, Pulau Pinang, Malaysia",
                    place_id="penang-kitchen",
                    latitude=5.4164,
                    longitude=100.3327,
                    rating=4.4,
                    user_rating_count=980,
                    google_maps_uri="https://maps.google.com/?cid=penang",
                )
            ]
        return []

    async def fake_explain(*args, **kwargs):
        return {
            "ipoh-heritage": "A light cultural stop that breaks up the drive without straying far.",
            "penang-kitchen": "A useful first food stop near the destination with strong Google interest.",
        }

    monkeypatch.setattr(planner, "compute_route", fake_route)
    monkeypatch.setattr(planner, "search_places", fake_search_places)
    monkeypatch.setattr(planner, "_explain_with_deepseek", fake_explain)
    monkeypatch.setattr(planner, "_decode_polyline", lambda value: [(4.6, 101.1), (5.4164, 100.3327)])

    response = await planner.plan_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        google_maps_server_key="google-key",
        deepseek_api_key="deepseek-key",
        deepseek_model="model",
        deepseek_base_url="url",
    )

    addresses = {
        recommendation.address
        for recommendation in [
            *response.routeRecommendations,
            *response.destinationRecommendations,
            *response.foodRecommendations,
        ]
    }
    assert "Jalan Panglima, 30000 Ipoh, Perak, Malaysia" in addresses
    assert "Lebuh Chulia, George Town, 10200 George Town, Pulau Pinang, Malaysia" in addresses
    assert response.foodRecommendations[0].explanation.startswith("A useful first food stop")


@pytest.mark.asyncio
async def test_road_trip_uses_fallback_explanation_when_deepseek_unavailable(monkeypatch):
    async def fake_route(origin, destination, api_key):
        return RouteResponse(
            duration="1800s",
            distanceMeters=40000,
            encodedPolyline=ENCODED_POLYLINE,
            summary=RouteSummary(durationText="30 min", distanceText="40 km"),
        )

    async def fake_search_places(**kwargs):
        if kwargs["text_query"] != "kopitiam":
            return []
        return [
            ResolvedPlace(
                label="Route Kopitiam",
                address="Google Formatted Kopitiam Address",
                place_id="kopitiam",
                latitude=4.6,
                longitude=101.1,
                rating=4.2,
            )
        ]

    monkeypatch.setattr(planner, "compute_route", fake_route)
    monkeypatch.setattr(planner, "search_places", fake_search_places)

    response = await planner.plan_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        google_maps_server_key="google-key",
        deepseek_api_key="",
        deepseek_model="model",
        deepseek_base_url="url",
    )

    assert response.routeRecommendations
    assert response.routeRecommendations[0].address == "Google Formatted Kopitiam Address"
    assert "practical local food stop" in response.routeRecommendations[0].explanation.lower()


@pytest.mark.asyncio
async def test_road_trip_returns_more_destination_places(monkeypatch):
    async def fake_route(origin, destination, api_key):
        return RouteResponse(
            duration="3600s",
            distanceMeters=120000,
            encodedPolyline=ENCODED_POLYLINE,
            summary=RouteSummary(durationText="1 hr", distanceText="120 km"),
        )

    async def fake_search_places(**kwargs):
        query = kwargs["text_query"].split(" in ", 1)[0]
        destination_queries = {"attractions", "sightseeing", "landmarks", "mall"}
        if query not in destination_queries:
            return []
        return [
            ResolvedPlace(
                label=f"{query.title()} Place {index}",
                address=f"{query.title()} Address {index}",
                place_id=f"{query}-{index}",
                latitude=5.4 + index / 1000,
                longitude=100.3 + index / 1000,
                rating=4.5,
            )
            for index in range(1, 5)
        ]

    monkeypatch.setattr(planner, "compute_route", fake_route)
    monkeypatch.setattr(planner, "search_places", fake_search_places)
    monkeypatch.setattr(planner, "_decode_polyline", lambda value: [(5.0, 100.0), (5.4, 100.3)])

    response = await planner.plan_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        google_maps_server_key="google-key",
        deepseek_api_key="",
        deepseek_model="model",
        deepseek_base_url="url",
    )

    assert len(response.destinationRecommendations) == planner.DESTINATION_RECOMMENDATION_LIMIT


@pytest.mark.asyncio
async def test_road_trip_filters_destination_places_far_from_destination(monkeypatch):
    async def fake_route(origin, destination, api_key):
        return RouteResponse(
            duration="7200s",
            distanceMeters=145000,
            encodedPolyline=ENCODED_POLYLINE,
            summary=RouteSummary(durationText="2 hr", distanceText="145 km"),
        )

    async def fake_search_places(**kwargs):
        query = kwargs["text_query"].split(" in ", 1)[0]
        if query != "attractions":
            return []
        return [
            ResolvedPlace(
                label="A Famosa",
                address="Bandar Hilir, Melaka",
                place_id="a-famosa",
                latitude=2.1914,
                longitude=102.2497,
                rating=4.4,
            ),
            ResolvedPlace(
                label="IOI City Mall",
                address="IOI Resort City, Putrajaya",
                place_id="ioi-city-mall",
                latitude=2.9696,
                longitude=101.7139,
                rating=4.6,
            ),
        ]

    monkeypatch.setattr(planner, "compute_route", fake_route)
    monkeypatch.setattr(planner, "search_places", fake_search_places)
    monkeypatch.setattr(planner, "_decode_polyline", lambda value: [(3.139, 101.6869), (2.1896, 102.2501)])

    response = await planner.plan_road_trip(
        origin="Kuala Lumpur",
        destination="Melaka",
        google_maps_server_key="google-key",
        deepseek_api_key="",
        deepseek_model="model",
        deepseek_base_url="url",
    )

    destination_names = {
        recommendation.name for recommendation in response.destinationRecommendations
    }
    assert "A Famosa" in destination_names
    assert "IOI City Mall" not in destination_names
