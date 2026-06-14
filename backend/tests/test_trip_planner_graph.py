from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from backend.app.schemas.routes import RouteResponse, RouteSummary
from backend.app.schemas.trip_planner import PlaceResult
from backend.app.services.google_places import ResolvedPlace
from backend.app.services import trip_planner_service as planner


def _route(leg_seconds: list[int]) -> RouteResponse:
    total = sum(leg_seconds)
    return RouteResponse(
        duration=f"{total}s",
        distanceMeters=25000,
        encodedPolyline="encoded",
        summary=RouteSummary(durationText=f"{total // 60} min", distanceText="25 km"),
        legDurations=[f"{seconds}s" for seconds in leg_seconds],
    )


def _initial(instruction: str) -> dict:
    return {
        "instruction": instruction,
        "original_instruction": instruction,
        "location_tags": {
            "home": "Impian Meridian, Subang Jaya",
            "work": "Menara UOA Bangsar, Kuala Lumpur",
        },
        "user_settings": {"currentLocation": "KL Sentral, Kuala Lumpur"},
        "stored_preferences": {
            "avoidHighways": False,
            "avoidTolls": True,
            "fastestRoute": False,
        },
        "requested_departure_time": "2026-06-10T10:30:00+08:00",
        "revision": 0,
        "resolved_waypoints": [],
    }


def _graph():
    dependencies = planner.PlannerDependencies("google", "deepseek", "model", "url")
    return planner.build_trip_graph(dependencies, InMemorySaver())


@pytest.mark.asyncio
async def test_food_choice_resumes_same_trip(monkeypatch):
    async def fake_parse(state, dependencies):
        return planner.ParsedTrip(
            origin="work",
            waypoints=[
                planner.WaypointIntent(query="Aquaria KLCC", resolution="specific"),
                planner.WaypointIntent(
                    query="lunch",
                    purpose="lunch",
                    resolution="food_choice",
                    selectionMode="choice",
                    nearbyReference="Aquaria KLCC",
                    dwellMinutes=45,
                ),
                planner.WaypointIntent(query="home", resolution="specific"),
            ],
            preferences=planner.ParsedPreferences(avoidTolls=True),
        )

    async def fake_search(**kwargs):
        return [
            ResolvedPlace(
                label="Aquaria KLCC",
                address="Kuala Lumpur Convention Centre, KLCC",
                place_id="aquaria",
                rating=4.4,
            )
        ]

    async def fake_matrix(origin, destinations, preferences, api_key):
        return [(600 + index * 60, 5000) for index, _ in enumerate(destinations)]

    async def fake_route(**kwargs):
        return _route([900, 600, 1200])

    monkeypatch.setattr(planner, "_parse_with_deepseek", fake_parse)
    monkeypatch.setattr(planner, "search_places", fake_search)
    monkeypatch.setattr(planner, "compute_route_matrix", fake_matrix)
    monkeypatch.setattr(planner, "compute_multi_stop_route", fake_route)
    monkeypatch.setattr(planner, "update_preferences", lambda value: value)

    graph = _graph()
    config = {"configurable": {"thread_id": str(uuid4())}}
    paused = await graph.ainvoke(_initial("KLCC then lunch then home"), config=config)

    payload = planner._interrupt_payload(paused)
    assert payload["kind"] == "choice"
    assert payload["choiceType"] == "food"
    assert payload["referenceOrigin"] == "Aquaria KLCC"

    resumed = await graph.ainvoke(
        Command(
            resume={
                "selectedPlace": PlaceResult(
                    name="Sushi Oribe",
                    address="Jalan Kia Peng, Kuala Lumpur",
                    placeId="sushi-oribe",
                    rating=4.6,
                ).model_dump()
            }
        ),
        config=config,
    )

    assert resumed["normalized_plan"].stops == [
        "Kuala Lumpur Convention Centre, KLCC",
        "Jalan Kia Peng, Kuala Lumpur",
    ]
    assert resumed["normalized_plan"].destination == "Impian Meridian, Subang Jaya"
    assert [waypoint.label for waypoint in resumed["waypoints"]] == [
        "Start",
        "Aquaria KLCC",
        "Sushi Oribe",
        "Home",
    ]


@pytest.mark.asyncio
async def test_named_destination_uses_google_top_result(monkeypatch):
    async def fake_parse(state, dependencies):
        return planner.ParsedTrip(
            origin="current location",
            waypoints=[planner.WaypointIntent(query="Pavilion KL")],
        )

    async def fake_search(**kwargs):
        return [
            ResolvedPlace(
                label="Pavilion Kuala Lumpur",
                address="168 Jalan Bukit Bintang, Kuala Lumpur",
                place_id="pavilion-kl",
            ),
            ResolvedPlace(label="Pavilion Hotel", address="Bukit Bintang", place_id="hotel"),
        ]

    async def fake_matrix(origin, destinations, preferences, api_key):
        return [(900, 10000)]

    async def fake_route(**kwargs):
        assert kwargs["destination_place_id"] == "pavilion-kl"
        return _route([900])

    monkeypatch.setattr(planner, "_parse_with_deepseek", fake_parse)
    monkeypatch.setattr(planner, "search_places", fake_search)
    monkeypatch.setattr(planner, "compute_route_matrix", fake_matrix)
    monkeypatch.setattr(planner, "compute_multi_stop_route", fake_route)
    monkeypatch.setattr(planner, "update_preferences", lambda value: value)

    completed = await _graph().ainvoke(
        _initial("Go to Pavilion KL"),
        config={"configurable": {"thread_id": str(uuid4())}},
    )
    assert "__interrupt__" not in completed
    assert completed["normalized_plan"].destination == "168 Jalan Bukit Bintang, Kuala Lumpur"


@pytest.mark.asyncio
async def test_single_choice_result_is_selected_without_prompt(monkeypatch):
    async def fake_parse(state, dependencies):
        return planner.ParsedTrip(
            origin="current location",
            waypoints=[
                planner.WaypointIntent(
                    query="midvalley",
                    resolution="category",
                    selectionMode="choice",
                )
            ],
        )

    async def fake_search(**kwargs):
        assert kwargs["text_query"] == "midvalley"
        assert kwargs["included_type"] is None
        return [
            ResolvedPlace(
                label="Mid Valley Megamall",
                address="Lingkaran Syed Putra, Kuala Lumpur",
                place_id="mid-valley-megamall",
            ),
            ResolvedPlace(label="Mid Valley City", address="Mid Valley City", place_id="mid-valley-city"),
        ]

    async def fake_matrix(origin, destinations, preferences, api_key):
        return [(900, 10000)]

    async def fake_route(**kwargs):
        assert kwargs["destination_place_id"] == "mid-valley-megamall"
        return _route([900])

    monkeypatch.setattr(planner, "_parse_with_deepseek", fake_parse)
    monkeypatch.setattr(planner, "search_places", fake_search)
    monkeypatch.setattr(planner, "compute_route_matrix", fake_matrix)
    monkeypatch.setattr(planner, "compute_multi_stop_route", fake_route)
    monkeypatch.setattr(planner, "update_preferences", lambda value: value)

    completed = await _graph().ainvoke(
        _initial("Go to Mid Valley"),
        config={"configurable": {"thread_id": str(uuid4())}},
    )

    assert "__interrupt__" not in completed
    assert completed["normalized_plan"].destination == "Lingkaran Syed Putra, Kuala Lumpur"
    assert [item.label for item in completed["waypoints"]] == [
        "Start",
        "Mid Valley Megamall",
    ]
    assert completed["route_response"].encodedPolyline == "encoded"


@pytest.mark.asyncio
async def test_infeasible_arrival_interrupts(monkeypatch):
    async def fake_parse(state, dependencies):
        return planner.ParsedTrip(
            origin="current location",
            waypoints=[
                planner.WaypointIntent(
                    query="Setia City Mall",
                    arriveBy="10:40",
                )
            ],
        )

    async def fake_search(**kwargs):
        return [
            ResolvedPlace(
                label="Setia City Mall",
                address="Setia Alam, Shah Alam",
                place_id="setia-city-mall",
            )
        ]

    async def fake_matrix(origin, destinations, preferences, api_key):
        return [(3600, 40000)]

    async def fake_route(**kwargs):
        return _route([3600])

    monkeypatch.setattr(planner, "_parse_with_deepseek", fake_parse)
    monkeypatch.setattr(planner, "search_places", fake_search)
    monkeypatch.setattr(planner, "compute_route_matrix", fake_matrix)
    monkeypatch.setattr(planner, "compute_multi_stop_route", fake_route)

    initial = _initial("Reach Setia City Mall by 10:40")
    initial["requested_departure_time"] = "2026-06-10T10:30:00+08:00"
    graph = _graph()
    paused = await graph.ainvoke(
        initial,
        config={"configurable": {"thread_id": str(uuid4())}},
    )
    payload = planner._interrupt_payload(paused)
    assert payload["kind"] == "clarification"
    assert "earliest estimated arrival" in payload["prompt"]


def test_explicit_false_overrides_stored_true():
    preferences = planner._merge_preferences(
        planner.ParsedPreferences(avoidTolls=False),
        {"avoidTolls": True, "avoidHighways": False, "fastestRoute": False},
    )
    assert preferences.avoidTolls is False


@pytest.mark.asyncio
async def test_flexible_stops_follow_google_optimized_order(monkeypatch):
    async def fake_parse(state, dependencies):
        return planner.ParsedTrip(
            origin="current location",
            waypoints=[
                planner.WaypointIntent(query="Stop A", flexible=True),
                planner.WaypointIntent(query="Stop B", flexible=True),
                planner.WaypointIntent(query="Home", flexible=False),
            ],
            optimizeFlexible=True,
        )

    async def fake_search(**kwargs):
        query = kwargs["text_query"]
        label = "Stop A" if "Stop A" in query else "Stop B"
        return [ResolvedPlace(label=label, address=f"{label} address", place_id=label)]

    async def fake_matrix(origin, destinations, preferences, api_key):
        return [(600, 5000) for _ in destinations]

    async def fake_route(**kwargs):
        response = _route([600, 600, 600])
        response.optimizedWaypointOrder = [1, 0]
        return response

    monkeypatch.setattr(planner, "_parse_with_deepseek", fake_parse)
    monkeypatch.setattr(planner, "search_places", fake_search)
    monkeypatch.setattr(planner, "compute_route_matrix", fake_matrix)
    monkeypatch.setattr(planner, "compute_multi_stop_route", fake_route)
    monkeypatch.setattr(planner, "update_preferences", lambda value: value)

    completed = await _graph().ainvoke(
        _initial("Visit A and B in the fastest order, then home"),
        config={"configurable": {"thread_id": str(uuid4())}},
    )
    assert completed["normalized_plan"].stops == ["Stop B address", "Stop A address"]
    assert [item.label for item in completed["waypoints"][1:]] == ["Stop B", "Stop A", "Home"]
