import asyncio
from pathlib import Path
from typing import Any, Literal, TypedDict
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
from backend.app.schemas.preferences import (
    PreferenceMemoryResponse,
    StopPreferenceFeedbackRequest,
)
from backend.app.services.memory_service import (
    get_central_agent_memory,
    get_preference_memory_summary,
    record_stop_preference_feedback,
    reset_stop_preference_memory,
)
from backend.app.services.google_routes import compute_multi_stop_route
from backend.app.trip_planner.schemas import TripPreferences


CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / "data" / "central_agent.sqlite"
CentralAgentTask = Literal[
    "recommend_fatigue_stop",
    "record_preference_feedback",
    "reset_preference_memory",
]


class CentralAgentState(TypedDict, total=False):
    task: CentralAgentTask
    request: FatigueRecommendationRequest
    feedback: StopPreferenceFeedbackRequest
    api_key: str
    preference_memory: dict[str, Any]
    preference_summary: dict[str, Any]
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


def _active_stop_waypoints(active_route: ActiveRoadTrip) -> list[RouteWaypoint]:
    return [
        waypoint
        for waypoint in active_route.route.waypoints
        if waypoint.role == "stop" and waypoint.address
    ]


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


def build_central_agent_graph(checkpointer: Any = None):
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LangGraph is not installed.",
        ) from exc

    async def load_preference_memory(state: CentralAgentState) -> dict[str, Any]:
        return {
            "preference_memory": get_central_agent_memory(),
            "preference_summary": get_preference_memory_summary().model_dump(),
        }

    def after_preference_memory(state: CentralAgentState) -> str:
        task = state.get("task") or "recommend_fatigue_stop"
        if task == "record_preference_feedback":
            return "record_preference_feedback"
        if task == "reset_preference_memory":
            return "reset_preference_memory"
        return "load_active_route"

    async def record_preference_feedback_node(state: CentralAgentState) -> dict[str, Any]:
        summary = record_stop_preference_feedback(state["feedback"])
        return {
            "preference_memory": get_central_agent_memory(),
            "preference_summary": summary.model_dump(),
        }

    async def reset_preference_memory_node(_: CentralAgentState) -> dict[str, Any]:
        summary = reset_stop_preference_memory()
        return {
            "preference_memory": get_central_agent_memory(),
            "preference_summary": summary.model_dump(),
        }

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
            preference_memory=state.get("preference_memory", {}),
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
    graph.add_node("load_preference_memory", load_preference_memory)
    graph.add_node("record_preference_feedback", record_preference_feedback_node)
    graph.add_node("reset_preference_memory", reset_preference_memory_node)
    graph.add_node("load_active_route", load_active_route)
    graph.add_node("evaluate_risk", evaluate_risk)
    graph.add_node("find_rest_stops", find_rest_stops)
    graph.add_node("build_notification", build_notification)
    graph.add_edge(START, "load_preference_memory")
    graph.add_conditional_edges(
        "load_preference_memory",
        after_preference_memory,
        {
            "record_preference_feedback": "record_preference_feedback",
            "reset_preference_memory": "reset_preference_memory",
            "load_active_route": "load_active_route",
        },
    )
    graph.add_edge("record_preference_feedback", END)
    graph.add_edge("reset_preference_memory", END)
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
    return graph.compile(checkpointer=checkpointer)


class _CentralGraphRuntime:
    def __init__(self) -> None:
        self._graphs: dict[int, Any] = {}
        self._checkpoint_connections: dict[int, Any] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    async def get(self):
        loop_id = id(asyncio.get_running_loop())
        if loop_id in self._graphs:
            return self._graphs[loop_id]
        lock = self._locks.setdefault(loop_id, asyncio.Lock())
        async with lock:
            if loop_id in self._graphs:
                return self._graphs[loop_id]
            CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
            try:
                import aiosqlite
                from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

                self._checkpoint_connections[loop_id] = await aiosqlite.connect(str(CHECKPOINT_PATH))
                serializer = JsonPlusSerializer(
                    allowed_msgpack_modules=[
                        ("backend.app.central_agent.schemas", "AgentNotification"),
                        ("backend.app.central_agent.schemas", "FatigueRecommendationRequest"),
                        ("backend.app.central_agent.schemas", "FatigueRecommendationResponse"),
                        ("backend.app.central_agent.schemas", "FatigueSnapshot"),
                        ("backend.app.central_agent.schemas", "GeoLocation"),
                        ("backend.app.central_agent.schemas", "NotificationAction"),
                        ("backend.app.central_agent.schemas", "RestStopPlace"),
                        ("backend.app.central_agent.rest_stop_service", "RestStopCandidate"),
                        ("backend.app.schemas.preferences", "PreferenceMemoryItem"),
                        ("backend.app.schemas.preferences", "PreferenceMemoryResponse"),
                        ("backend.app.schemas.preferences", "StopPreferenceFeedbackRequest"),
                    ]
                )
                checkpointer = AsyncSqliteSaver(
                    self._checkpoint_connections[loop_id],
                    serde=serializer,
                )
            except ImportError:
                from langgraph.checkpoint.memory import InMemorySaver

                checkpointer = InMemorySaver()
            self._graphs[loop_id] = build_central_agent_graph(checkpointer)
            return self._graphs[loop_id]


_RUNTIME = _CentralGraphRuntime()


def _preference_response_from_state(state: dict[str, Any]) -> PreferenceMemoryResponse:
    return PreferenceMemoryResponse.model_validate(
        state.get("preference_summary") or get_preference_memory_summary().model_dump()
    )


async def _invoke_central_agent_graph(
    state: dict[str, Any],
    thread_id: str,
) -> dict[str, Any]:
    checkpoint_connection: Any = None
    try:
        try:
            import aiosqlite
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

            CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_connection = await aiosqlite.connect(str(CHECKPOINT_PATH))
            serializer = JsonPlusSerializer(
                allowed_msgpack_modules=[
                    ("backend.app.central_agent.schemas", "AgentNotification"),
                    ("backend.app.central_agent.schemas", "FatigueRecommendationRequest"),
                    ("backend.app.central_agent.schemas", "FatigueRecommendationResponse"),
                    ("backend.app.central_agent.schemas", "FatigueSnapshot"),
                    ("backend.app.central_agent.schemas", "GeoLocation"),
                    ("backend.app.central_agent.schemas", "NotificationAction"),
                    ("backend.app.central_agent.schemas", "RestStopPlace"),
                    ("backend.app.central_agent.rest_stop_service", "RestStopCandidate"),
                    ("backend.app.schemas.preferences", "PreferenceMemoryItem"),
                    ("backend.app.schemas.preferences", "PreferenceMemoryResponse"),
                    ("backend.app.schemas.preferences", "StopPreferenceFeedbackRequest"),
                ]
            )
            checkpointer = AsyncSqliteSaver(checkpoint_connection, serde=serializer)
        except ImportError:
            from langgraph.checkpoint.memory import InMemorySaver

            checkpointer = InMemorySaver()

        graph = build_central_agent_graph(checkpointer)
        return await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": thread_id}},
        )
    finally:
        if checkpoint_connection is not None:
            await checkpoint_connection.close()


async def recommend_rest_stop(
    request: FatigueRecommendationRequest,
    api_key: str,
) -> FatigueRecommendationResponse:
    final_state = await _invoke_central_agent_graph(
        {
            "task": "recommend_fatigue_stop",
            "request": request,
            "api_key": api_key,
            "notification": None,
        },
        request.activeRouteId or "central-agent",
    )
    return FatigueRecommendationResponse(notification=final_state.get("notification"))


async def record_preference_feedback(
    request: StopPreferenceFeedbackRequest,
) -> PreferenceMemoryResponse:
    final_state = await _invoke_central_agent_graph(
        {
            "task": "record_preference_feedback",
            "feedback": request,
            "notification": None,
        },
        "central-agent-preferences",
    )
    return _preference_response_from_state(final_state)


async def reset_preference_memory() -> PreferenceMemoryResponse:
    final_state = await _invoke_central_agent_graph(
        {
            "task": "reset_preference_memory",
            "notification": None,
        },
        "central-agent-preferences",
    )
    return _preference_response_from_state(final_state)


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

    existing_stops = _active_stop_waypoints(active_route)
    stops = [waypoint.address for waypoint in existing_stops]
    is_new_stop = request.place.address not in stops
    if is_new_stop:
        stops.append(request.place.address)
    stop_place_ids = ["" for _ in existing_stops]
    if is_new_stop:
        stop_place_ids.append(request.place.placeId)

    route = await compute_multi_stop_route(
        origin=active_route.origin,
        stops=stops,
        destination=active_route.destination,
        preferences=TripPreferences(),
        api_key=api_key,
        optimize_waypoints=False,
        stop_place_ids=stop_place_ids,
    )
    stop_waypoints = [*existing_stops]
    if is_new_stop:
        stop_waypoints.append(
            RouteWaypoint(
                role="stop",
                label=request.place.name,
                address=request.place.address,
                rating=request.place.rating,
                userRatingCount=request.place.userRatingCount,
                googleMapsUri=request.place.googleMapsUri,
            )
        )
    route.waypoints = [
        RouteWaypoint(role="origin", label="Start", address=active_route.origin),
        *stop_waypoints,
        RouteWaypoint(
            role="destination",
            label="Destination",
            address=active_route.destination,
        ),
    ]
    if not route.summary:
        route.summary = RouteSummary(durationText="--", distanceText="--")
    update_active_road_trip(active_route.route_id, route)
    record_stop_preference_feedback(
        StopPreferenceFeedbackRequest(
            action="love",
            id=request.notificationId,
            placeId=request.place.placeId,
            name=request.place.name,
            address=request.place.address,
            category="Rest stop",
            section="rest",
        )
    )
    return route
