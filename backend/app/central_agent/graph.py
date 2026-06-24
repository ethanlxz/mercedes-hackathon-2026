from typing import Any, TypedDict
from uuid import uuid4

from fastapi import HTTPException, status

from backend.app.central_agent.rest_stop_service import (
    RestStopCandidate,
    find_rest_stop_candidates,
)
from backend.app.central_agent.schemas import (
    AgentNotification,
    FatigueRecommendationRequest,
    FatigueRecommendationResponse,
    NotificationAction,
    RestStopAcceptRequest,
    RestStopPlace,
    Severity,
)
from backend.app.central_agent.state import (
    ActiveRoadTrip,
    get_active_road_trip,
    update_active_road_trip,
)
from backend.app.schemas.routes import RouteResponse, RouteSummary, RouteWaypoint
from backend.app.services.google_routes import compute_multi_stop_route
from backend.app.trip_planner.schemas import TripPreferences


class CentralAgentState(TypedDict, total=False):
    request: FatigueRecommendationRequest
    api_key: str
    active_route: ActiveRoadTrip | None
    severity: Severity | None
    candidates: list[RestStopCandidate]
    selected_candidate: RestStopCandidate | None
    notification: AgentNotification | None


def _severity_from_score(score: int) -> Severity | None:
    if score >= 85:
        return "critical"
    if score >= 75:
        return "high"
    if score >= 50:
        return "warning"
    return None


def _format_eta(seconds: int | None) -> str:
    if not seconds:
        return "soon"
    minutes = max(1, round(seconds / 60))
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def _title_for_severity(severity: Severity) -> str:
    if severity == "critical":
        return "Critical fatigue risk"
    if severity == "high":
        return "High fatigue risk"
    return "Fatigue risk rising"


def _message_for_candidate(
    *,
    severity: Severity,
    candidate: RestStopCandidate,
) -> str:
    eta = _format_eta(candidate.estimated_drive_seconds)
    if severity == "critical":
        return (
            f"Please stop as soon as it is safe. {candidate.place.name} is about "
            f"{eta} away and is the best rest option on this route."
        )
    if severity == "high":
        return (
            f"Your fatigue risk is high. {candidate.place.name} is about {eta} away; "
            "I recommend taking a break there."
        )
    return (
        f"Your fatigue risk is rising. {candidate.place.name} is about {eta} away; "
        "would you like to rest there?"
    )


def build_central_agent_graph():
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LangGraph is not installed.",
        ) from exc

    async def load_active_route(state: CentralAgentState) -> dict[str, Any]:
        request = state["request"]
        return {"active_route": get_active_road_trip(request.activeRouteId)}

    async def evaluate_risk(state: CentralAgentState) -> dict[str, Any]:
        return {"severity": _severity_from_score(state["request"].fatigue.fatigueScore)}

    def after_risk(state: CentralAgentState) -> str:
        if not state.get("active_route") or not state.get("severity"):
            return "end"
        return "find_rest_stops"

    async def find_rest_stops(state: CentralAgentState) -> dict[str, Any]:
        active_route = state.get("active_route")
        severity = state.get("severity")
        if not active_route or not severity:
            return {"candidates": []}
        candidates = await find_rest_stop_candidates(
            active_route=active_route,
            location=state["request"].location,
            severity=severity,
            api_key=state["api_key"],
        )
        return {
            "candidates": candidates,
            "selected_candidate": candidates[0] if candidates else None,
        }

    def after_rest_stops(state: CentralAgentState) -> str:
        return "build_notification" if state.get("selected_candidate") else "end"

    async def build_notification(state: CentralAgentState) -> dict[str, Any]:
        severity = state["severity"]
        candidate = state["selected_candidate"]
        notification = AgentNotification(
            id=str(uuid4()),
            severity=severity,
            title=_title_for_severity(severity),
            message=_message_for_candidate(severity=severity, candidate=candidate),
            place=candidate.place,
            estimatedDriveSeconds=candidate.estimated_drive_seconds,
            distanceMeters=candidate.distance_meters,
            primaryAction=NotificationAction(label="Rest there", type="add_rest_stop"),
            secondaryAction=NotificationAction(label="Not now", type="dismiss"),
        )
        return {"notification": notification}

    graph = StateGraph(CentralAgentState)
    graph.add_node("load_active_route", load_active_route)
    graph.add_node("evaluate_risk", evaluate_risk)
    graph.add_node("find_rest_stops", find_rest_stops)
    graph.add_node("build_notification", build_notification)
    graph.add_edge(START, "load_active_route")
    graph.add_edge("load_active_route", "evaluate_risk")
    graph.add_conditional_edges(
        "evaluate_risk",
        after_risk,
        {
            "find_rest_stops": "find_rest_stops",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "find_rest_stops",
        after_rest_stops,
        {
            "build_notification": "build_notification",
            "end": END,
        },
    )
    graph.add_edge("build_notification", END)
    return graph.compile()


async def recommend_rest_stop(
    request: FatigueRecommendationRequest,
    api_key: str,
) -> FatigueRecommendationResponse:
    graph = build_central_agent_graph()
    final_state = await graph.ainvoke(
        {
            "request": request,
            "api_key": api_key,
            "notification": None,
        }
    )
    return FatigueRecommendationResponse(notification=final_state.get("notification"))


async def accept_rest_stop(
    request: RestStopAcceptRequest,
    api_key: str,
) -> RouteResponse:
    active_route = get_active_road_trip(request.activeRouteId)
    if not active_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This road-trip route is no longer active. Plan the road trip again.",
        )

    route = await compute_multi_stop_route(
        origin=active_route.origin,
        stops=[request.place.address],
        destination=active_route.destination,
        preferences=TripPreferences(),
        api_key=api_key,
        optimize_waypoints=False,
        stop_place_ids=[request.place.placeId],
    )
    route.waypoints = [
        RouteWaypoint(role="origin", label="Start", address=active_route.origin),
        RouteWaypoint(
            role="stop",
            label=request.place.name,
            address=request.place.address,
            rating=request.place.rating,
            userRatingCount=request.place.userRatingCount,
            googleMapsUri=request.place.googleMapsUri,
        ),
        RouteWaypoint(
            role="destination",
            label="Destination",
            address=active_route.destination,
        ),
    ]
    if not route.summary:
        route.summary = RouteSummary(durationText="--", distanceText="--")
    update_active_road_trip(active_route.route_id, route)
    return route

