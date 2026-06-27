import pytest

from backend.app.central_agent import graph as agent_graph
from backend.app.central_agent.rest_stop_service import (
    RestStopCandidate,
    rank_rest_stop_candidates,
)
from backend.app.central_agent.schemas import (
    FatigueRecommendationRequest,
    FatigueSnapshot,
    RestStopAcceptRequest,
    RestStopPlace,
)
from backend.app.central_agent.state import (
    clear_active_road_trips,
    store_active_road_trip,
)
from backend.app.schemas.routes import RouteResponse, RouteSummary


def _route() -> RouteResponse:
    return RouteResponse(
        duration="3600s",
        distanceMeters=100000,
        encodedPolyline="_p~iF~ps|U_ulLnnqC_mqNvxq`@",
        summary=RouteSummary(durationText="1 hr", distanceText="100 km"),
    )


def _fatigue(score: int) -> FatigueSnapshot:
    return FatigueSnapshot(
        faceDetected=True,
        fatigueLevel="Warning" if score >= 50 else "Normal",
        fatigueScore=score,
        symptoms=["Yawning"] if score >= 50 else [],
        alert=score >= 75,
    )


@pytest.fixture(autouse=True)
def clear_routes():
    clear_active_road_trips()
    yield
    clear_active_road_trips()


@pytest.mark.asyncio
async def test_recommendation_without_active_route_is_non_blocking():
    response = await agent_graph.recommend_rest_stop(
        FatigueRecommendationRequest(
            activeRouteId="missing",
            fatigue=_fatigue(75),
        ),
        api_key="google-key",
    )

    assert response.notification is None


@pytest.mark.asyncio
async def test_recommendation_below_warning_threshold_returns_none():
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )

    response = await agent_graph.recommend_rest_stop(
        FatigueRecommendationRequest(
            activeRouteId=active.route_id,
            fatigue=_fatigue(49),
        ),
        api_key="google-key",
    )

    assert response.notification is None


@pytest.mark.asyncio
async def test_warning_fatigue_returns_rest_stop_notification(monkeypatch):
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )
    candidate = RestStopCandidate(
        place=RestStopPlace(
            name="Rawang R&R",
            address="North-South Expressway, Rawang",
            placeId="rawang-rnr",
            latitude=3.32,
            longitude=101.57,
            rating=4.2,
            userRatingCount=500,
        ),
        category="R&R",
        distance_meters=9000,
        route_distance_meters=150,
        estimated_drive_seconds=420,
    )

    async def fake_find_rest_stop_candidates(**kwargs):
        return [candidate]

    monkeypatch.setattr(
        agent_graph,
        "find_rest_stop_candidates",
        fake_find_rest_stop_candidates,
    )

    response = await agent_graph.recommend_rest_stop(
        FatigueRecommendationRequest(
            activeRouteId=active.route_id,
            fatigue=_fatigue(50),
        ),
        api_key="google-key",
    )

    assert response.notification is not None
    assert response.notification.source == "fatigue_rest_stop"
    assert response.notification.severity == "warning"
    assert response.notification.place.name == "Rawang R&R"
    assert response.notification.primaryAction.type == "add_rest_stop"


@pytest.mark.asyncio
async def test_accepting_rest_stop_returns_route_response(monkeypatch):
    active = store_active_road_trip(
        origin="Kuala Lumpur",
        destination="Penang",
        route=_route(),
    )
    place = RestStopPlace(
        name="Tapah R&R",
        address="North-South Expressway, Tapah",
        placeId="tapah-rnr",
        rating=4.3,
        userRatingCount=800,
    )

    async def fake_compute_multi_stop_route(**kwargs):
        assert kwargs["origin"] == "Kuala Lumpur"
        assert kwargs["stops"] == ["North-South Expressway, Tapah"]
        assert kwargs["destination"] == "Penang"
        assert kwargs["stop_place_ids"] == ["tapah-rnr"]
        return RouteResponse(
            duration="3900s",
            distanceMeters=104000,
            encodedPolyline="encoded",
            summary=RouteSummary(durationText="1 hr 5 min", distanceText="104 km"),
        )

    monkeypatch.setattr(
        agent_graph,
        "compute_multi_stop_route",
        fake_compute_multi_stop_route,
    )
    monkeypatch.setattr(
        agent_graph,
        "record_stop_preference_feedback",
        lambda feedback: feedback,
    )

    route = await agent_graph.accept_rest_stop(
        RestStopAcceptRequest(
            activeRouteId=active.route_id,
            notificationId="notification",
            place=place,
        ),
        api_key="google-key",
    )

    assert route.duration == "3900s"
    assert [waypoint.role for waypoint in route.waypoints] == [
        "origin",
        "stop",
        "destination",
    ]
    assert route.waypoints[1].label == "Tapah R&R"


def test_candidate_ranking_prefers_closer_route_stop():
    far = RestStopCandidate(
        place=RestStopPlace(name="Far Cafe", address="Far address", rating=4.9),
        category="Cafe",
        distance_meters=30000,
        route_distance_meters=100,
        estimated_drive_seconds=1800,
    )
    close = RestStopCandidate(
        place=RestStopPlace(name="Close R&R", address="Close address", rating=3.8),
        category="R&R",
        distance_meters=8000,
        route_distance_meters=250,
        estimated_drive_seconds=360,
    )

    ranked = rank_rest_stop_candidates([far, close], "warning")

    assert ranked[0].place.name == "Close R&R"


def test_candidate_ranking_uses_preferred_stop_type_as_soft_signal():
    cafe = RestStopCandidate(
        place=RestStopPlace(name="Loved Cafe", address="Cafe address", rating=4.2),
        category="Cafe",
        distance_meters=9500,
        route_distance_meters=120,
        estimated_drive_seconds=430,
    )
    rnr = RestStopCandidate(
        place=RestStopPlace(name="Neutral R&R", address="R&R address", rating=4.7),
        category="R&R",
        distance_meters=9000,
        route_distance_meters=120,
        estimated_drive_seconds=420,
    )

    ranked = rank_rest_stop_candidates(
        [rnr, cafe],
        "warning",
        {"preferredStopTypes": {"Cafe": 2}, "dislikedStopTypes": {}},
    )

    assert ranked[0].place.name == "Loved Cafe"
