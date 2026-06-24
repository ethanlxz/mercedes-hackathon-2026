import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from backend.app.services.google_places import search_places
from backend.app.services.google_routes import compute_route_matrix
from backend.app.services.memory_service import get_preferences, update_preferences
from backend.app.trip_planner.models import (
    CURRENT_LOCATION_ALIASES,
    Candidate,
    ParsedPreferences,
    ParsedTrip,
    PlannerDependencies,
    PlannerState,
    ResolvedWaypoint,
    WaypointIntent,
    _clean,
    _latest_resolved,
    _tag_name,
)
from backend.app.trip_planner.parser import _parse_with_deepseek
from backend.app.trip_planner.resolution import (
    _candidate_from_place,
    _candidate_is_confident,
    _candidate_text_score,
    _default_origin,
    _merge_preferences,
    _normalize_place_intent,
    _place_result,
    _resolve_context_value,
)
from backend.app.trip_planner.routing import plan_route, validate_route_schedule
from backend.app.trip_planner.schemas import PlaceResult, TripPlannerResponse


CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / "data" / "trip_planner.sqlite"


def build_trip_graph(dependencies: PlannerDependencies, checkpointer: Any):
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command, Send, interrupt
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LangGraph is not installed.",
        ) from exc

    async def context_loader(state: PlannerState) -> dict[str, Any]:
        return {
            "original_instruction": state.get("original_instruction") or state["instruction"],
            "revision": state.get("revision", 0),
            "pending_question": None,
            "schedule_error": None,
        }

    async def intent_parser(state: PlannerState) -> dict[str, Any]:
        parsed = await _parse_with_deepseek(state, dependencies)
        return {
            "parsed": parsed,
            "revision": state.get("revision", 0) + 1,
            "pending_question": None,
            "schedule_error": None,
        }

    async def ambiguity_checker(state: PlannerState) -> dict[str, Any]:
        parsed = state["parsed"]
        question = parsed.clarificationQuestion
        if not question and not parsed.waypoints:
            question = "What is your final destination?"
        return {"pending_question": question}

    def after_ambiguity(state: PlannerState) -> str:
        return "clarification_gate" if state.get("pending_question") else "tag_resolver"

    async def clarification_gate(state: PlannerState):
        answer = interrupt(
            {
                "kind": "clarification",
                "prompt": state.get("pending_question") or "Please clarify your trip.",
            }
        )
        answer_text = answer.get("answer", "") if isinstance(answer, dict) else str(answer)
        instruction = (
            f"{state.get('original_instruction') or state['instruction']}\n"
            f"Clarification answer: {_clean(answer_text)}"
        )
        return Command(
            update={"instruction": instruction, "pending_question": None},
            goto="intent_parser",
        )

    async def tag_resolver(state: PlannerState) -> dict[str, Any]:
        parsed = state["parsed"]
        if parsed.origin:
            origin, question = _resolve_context_value(
                parsed.origin,
                state["location_tags"],
                state["user_settings"],
            )
        else:
            origin, question = _default_origin(
                state["location_tags"],
                state["user_settings"],
            )
        return {"resolved_origin": origin, "pending_question": question}

    def after_tags(state: PlannerState) -> str:
        return "clarification_gate" if state.get("pending_question") else "preference_resolver"

    async def preference_resolver(state: PlannerState) -> dict[str, Any]:
        return {
            "preferences": _merge_preferences(
                state["parsed"].preferences,
                state["stored_preferences"],
            )
        }

    async def waypoint_dispatch(state: PlannerState) -> dict[str, Any]:
        return {}

    def dispatch_waypoints(state: PlannerState):
        parsed = state["parsed"]
        if not parsed.waypoints:
            return "candidate_ranker"
        return [
            Send(
                "place_resolver",
                {
                    **state,
                    "waypoint_task": (index, waypoint),
                },
            )
            for index, waypoint in enumerate(parsed.waypoints)
        ]

    async def place_resolver(state: dict[str, Any]) -> dict[str, Any]:
        index, intent = state["waypoint_task"]
        intent, included_type = _normalize_place_intent(intent)
        reference = intent.nearbyReference or state["resolved_origin"]
        reference, reference_question = _resolve_context_value(
            reference,
            state["location_tags"],
            state["user_settings"],
        )
        if reference_question:
            return {"pending_question": reference_question}

        direct, direct_question = _resolve_context_value(
            intent.query,
            state["location_tags"],
            state["user_settings"],
        )
        if direct_question:
            return {"pending_question": direct_question}

        if _tag_name(intent.query) or intent.query.lower() in CURRENT_LOCATION_ALIASES:
            selected = Candidate(name=intent.query.title(), address=direct)
            item = ResolvedWaypoint(
                revision=state["revision"],
                index=index,
                intent=intent,
                referenceAddress=reference,
                candidates=[selected],
                selected=selected,
            )
            return {"resolved_waypoints": [item]}

        if intent.resolution == "food_choice":
            item = ResolvedWaypoint(
                revision=state["revision"],
                index=index,
                intent=intent,
                referenceAddress=reference,
            )
            return {"resolved_waypoints": [item]}

        query = direct
        should_search_near_reference = bool(intent.nearbyReference) or (
            intent.selectionMode == "nearest" or intent.resolution == "category"
        )
        if should_search_near_reference and reference and reference.lower() not in query.lower():
            query = f"{query} near {reference}"
        places = await search_places(
            text_query=query,
            fallback_label=intent.query,
            api_key=dependencies.google_maps_server_key,
            max_result_count=3,
            included_type=included_type,
            strict_type_filtering=bool(included_type),
        )
        item = ResolvedWaypoint(
            revision=state["revision"],
            index=index,
            intent=intent,
            referenceAddress=reference,
            candidates=[_candidate_from_place(place) for place in places],
        )
        return {"resolved_waypoints": [item]}

    async def candidate_ranker(state: PlannerState) -> dict[str, Any]:
        latest = _latest_resolved(state)
        updates: list[ResolvedWaypoint] = []
        for index in sorted(latest):
            item = latest[index]
            if item.selected or not item.candidates:
                continue
            if item.intent.resolution == "specific" and item.intent.selectionMode == "auto":
                updates.append(item.model_copy(update={"selected": item.candidates[0]}))
                continue
            try:
                matrix = await compute_route_matrix(
                    origin=item.referenceAddress,
                    destinations=[candidate.address for candidate in item.candidates],
                    preferences=state["preferences"],
                    api_key=dependencies.google_maps_server_key,
                )
            except HTTPException:
                matrix = []
            ranked: list[Candidate] = []
            for candidate, route_data in zip(item.candidates, matrix, strict=False):
                seconds, distance = route_data
                ranked.append(candidate.model_copy(update={
                    "driveSeconds": seconds,
                    "distanceMeters": distance,
                }))
            if len(ranked) < len(item.candidates):
                ranked.extend(item.candidates[len(ranked):])
            ranked.sort(key=lambda value: (
                -_candidate_text_score(item.intent.query, value),
                value.driveSeconds is None,
                value.driveSeconds or 10**9,
                -(value.rating or 0),
                -(value.userRatingCount or 0),
            ))
            if item.intent.maxDriveMinutes:
                ranked = [
                    value for value in ranked
                    if value.driveSeconds is None
                    or value.driveSeconds <= item.intent.maxDriveMinutes * 60
                ]
            selected = None
            if len(ranked) == 1:
                selected = ranked[0]
            elif item.intent.selectionMode == "nearest" and ranked:
                selected = ranked[0]
            elif item.intent.selectionMode == "auto" and ranked and _candidate_is_confident(item.intent.query, ranked[0]):
                selected = ranked[0]
            updates.append(item.model_copy(update={"candidates": ranked, "selected": selected}))
        return {"resolved_waypoints": updates}

    async def choice_gate(state: PlannerState):
        latest = _latest_resolved(state)
        for index in range(len(state["parsed"].waypoints)):
            item = latest.get(index)
            if not item:
                continue
            if item.selected:
                continue
            if not item.candidates and item.intent.resolution != "food_choice":
                return Command(
                    update={
                        "pending_question": (
                            f"I couldn't find {item.intent.query} near {item.referenceAddress}. "
                            "What alternative should I use?"
                        )
                    },
                    goto="clarification_gate",
                )

            prompt = (
                "What would you like to eat?"
                if item.intent.resolution == "food_choice"
                else f"Choose {item.intent.query}."
            )
            selection = interrupt(
                {
                    "kind": "choice",
                    "prompt": prompt,
                    "choiceType": "food" if item.intent.resolution == "food_choice" else "location",
                    "choiceQuery": "" if item.intent.resolution == "food_choice" else item.intent.query,
                    "choiceReference": item.intent.nearbyReference,
                    "referenceOrigin": item.referenceAddress,
                    "choices": [_place_result(candidate).model_dump() for candidate in item.candidates],
                }
            )
            selected_data = selection.get("selectedPlace") if isinstance(selection, dict) else None
            if not selected_data:
                return Command(
                    update={"pending_question": "Please choose a place to continue."},
                    goto="clarification_gate",
                )
            selected_place = PlaceResult.model_validate(selected_data)
            selected = Candidate(
                name=selected_place.name,
                address=selected_place.address,
                placeId=selected_place.placeId,
                latitude=selected_place.latitude,
                longitude=selected_place.longitude,
                rating=selected_place.rating,
                userRatingCount=selected_place.userRatingCount,
                googleMapsUri=selected_place.googleMapsUri,
            )
            resolved = item.model_copy(update={"selected": selected})
            return Command(
                update={"resolved_waypoints": [resolved]},
                goto="candidate_ranker",
            )
        return Command(goto="route_planner")

    async def route_planner(state: PlannerState) -> dict[str, Any]:
        return await plan_route(state, dependencies)

    def after_route(state: PlannerState) -> str:
        return "clarification_gate" if state.get("pending_question") else "route_validator"

    async def route_validator(state: PlannerState) -> dict[str, Any]:
        return await validate_route_schedule(state)

    def after_validation(state: PlannerState) -> str:
        return "clarification_gate" if state.get("schedule_error") else "response_builder"

    async def response_builder(state: PlannerState) -> dict[str, Any]:
        update_preferences({
            "avoidHighways": state["preferences"].avoidHighways,
            "avoidTolls": state["preferences"].avoidTolls,
            "fastestRoute": state["preferences"].fastestRoute,
        })
        return {}

    graph = StateGraph(PlannerState)
    graph.add_node("context_loader", context_loader)
    graph.add_node("intent_parser", intent_parser)
    graph.add_node("ambiguity_checker", ambiguity_checker)
    graph.add_node(
        "clarification_gate",
        clarification_gate,
        destinations=("intent_parser",),
    )
    graph.add_node("tag_resolver", tag_resolver)
    graph.add_node("preference_resolver", preference_resolver)
    graph.add_node("waypoint_dispatch", waypoint_dispatch)
    graph.add_node("place_resolver", place_resolver)
    graph.add_node("candidate_ranker", candidate_ranker)
    graph.add_node(
        "choice_gate",
        choice_gate,
        destinations=("candidate_ranker", "clarification_gate", "route_planner"),
    )
    graph.add_node("route_planner", route_planner)
    graph.add_node("route_validator", route_validator)
    graph.add_node("response_builder", response_builder)

    graph.add_edge(START, "context_loader")
    graph.add_edge("context_loader", "intent_parser")
    graph.add_edge("intent_parser", "ambiguity_checker")
    graph.add_conditional_edges(
        "ambiguity_checker",
        after_ambiguity,
        {
            "clarification_gate": "clarification_gate",
            "tag_resolver": "tag_resolver",
        },
    )
    graph.add_conditional_edges(
        "tag_resolver",
        after_tags,
        {
            "clarification_gate": "clarification_gate",
            "preference_resolver": "preference_resolver",
        },
    )
    graph.add_edge("preference_resolver", "waypoint_dispatch")
    graph.add_conditional_edges(
        "waypoint_dispatch",
        dispatch_waypoints,
        {
            "place_resolver": "place_resolver",
            "candidate_ranker": "candidate_ranker",
        },
    )
    graph.add_edge("place_resolver", "candidate_ranker")
    graph.add_edge("candidate_ranker", "choice_gate")
    graph.add_conditional_edges(
        "route_planner",
        after_route,
        {
            "clarification_gate": "clarification_gate",
            "route_validator": "route_validator",
        },
    )
    graph.add_conditional_edges(
        "route_validator",
        after_validation,
        {
            "clarification_gate": "clarification_gate",
            "response_builder": "response_builder",
        },
    )
    graph.add_edge("response_builder", END)
    return graph.compile(checkpointer=checkpointer)


class _GraphRuntime:
    def __init__(self) -> None:
        self._graph: Any = None
        self._checkpoint_connection: Any = None
        self._lock = asyncio.Lock()

    async def get(self, dependencies: PlannerDependencies):
        if self._graph is not None:
            return self._graph
        async with self._lock:
            if self._graph is not None:
                return self._graph
            CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
            try:
                import aiosqlite
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
                from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

                self._checkpoint_connection = await aiosqlite.connect(str(CHECKPOINT_PATH))
                serializer = JsonPlusSerializer(
                    allowed_msgpack_modules=[
                        ("backend.app.trip_planner.models", "ParsedPreferences"),
                        ("backend.app.trip_planner.models", "WaypointIntent"),
                        ("backend.app.trip_planner.models", "ParsedTrip"),
                        ("backend.app.trip_planner.models", "Candidate"),
                        ("backend.app.trip_planner.models", "ResolvedWaypoint"),
                        ("backend.app.trip_planner.service", "ParsedPreferences"),
                        ("backend.app.trip_planner.service", "WaypointIntent"),
                        ("backend.app.trip_planner.service", "ParsedTrip"),
                        ("backend.app.trip_planner.service", "Candidate"),
                        ("backend.app.trip_planner.service", "ResolvedWaypoint"),
                        ("backend.app.schemas.trip_planner", "TripPreferences"),
                        ("backend.app.schemas.trip_planner", "NormalizedTripPlan"),
                        ("backend.app.schemas.trip_planner", "TripWaypoint"),
                        ("backend.app.trip_planner.schemas", "TripPreferences"),
                        ("backend.app.trip_planner.schemas", "NormalizedTripPlan"),
                        ("backend.app.trip_planner.schemas", "TripWaypoint"),
                        ("backend.app.schemas.routes", "RouteResponse"),
                        ("backend.app.schemas.routes", "RouteSummary"),
                    ]
                )
                checkpointer = AsyncSqliteSaver(
                    self._checkpoint_connection,
                    serde=serializer,
                )
            except ImportError:
                from langgraph.checkpoint.memory import InMemorySaver

                checkpointer = InMemorySaver()
            self._graph = build_trip_graph(dependencies, checkpointer)
            return self._graph


_RUNTIME = _GraphRuntime()


def _interrupt_payload(final_state: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = final_state.get("__interrupt__") or []
    if not interrupts:
        return None
    value = getattr(interrupts[0], "value", interrupts[0])
    return value if isinstance(value, dict) else {"kind": "clarification", "prompt": str(value)}


def _response_from_state(final_state: dict[str, Any], thread_id: str) -> TripPlannerResponse:
    payload = _interrupt_payload(final_state)
    if payload:
        kind = payload.get("kind")
        choices = [PlaceResult.model_validate(choice) for choice in payload.get("choices", [])]
        prompt = payload.get("prompt") or "More information is needed."
        return TripPlannerResponse(
            status="needs_choice" if kind == "choice" else "needs_clarification",
            threadId=thread_id,
            prompt=prompt,
            choices=choices,
            clarificationRequired=kind != "choice",
            clarificationMessage=prompt if kind != "choice" else None,
            choiceRequired=kind == "choice",
            choiceType=payload.get("choiceType"),
            choiceQuery=payload.get("choiceQuery", ""),
            choiceReference=payload.get("choiceReference", ""),
            referenceOrigin=payload.get("referenceOrigin", ""),
            message=prompt,
        )

    if "route_response" not in final_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This trip-planning session expired. Start the trip again.",
        )
    route_response = final_state["route_response"]
    return TripPlannerResponse(
        status="completed",
        threadId=thread_id,
        normalizedPlan=final_state["normalized_plan"],
        waypoints=final_state["waypoints"],
        duration=route_response.duration,
        distanceMeters=route_response.distanceMeters,
        encodedPolyline=route_response.encodedPolyline,
        summary=route_response.summary,
    )


async def plan_trip(
    instruction: str,
    location_tags: dict[str, str],
    user_settings: dict[str, str],
    google_maps_server_key: str,
    deepseek_api_key: str,
    deepseek_model: str,
    deepseek_base_url: str,
    thread_id: str | None = None,
    departure_time: datetime | None = None,
) -> TripPlannerResponse:
    dependencies = PlannerDependencies(
        google_maps_server_key=google_maps_server_key,
        deepseek_api_key=deepseek_api_key,
        deepseek_model=deepseek_model,
        deepseek_base_url=deepseek_base_url,
    )
    graph = await _RUNTIME.get(dependencies)
    resolved_thread_id = thread_id or str(uuid4())
    final_state = await graph.ainvoke(
        {
            "instruction": instruction,
            "original_instruction": instruction,
            "location_tags": location_tags,
            "user_settings": user_settings,
            "stored_preferences": get_preferences(),
            "requested_departure_time": departure_time.isoformat() if departure_time else None,
            "revision": 0,
            "resolved_waypoints": [],
        },
        config={"configurable": {"thread_id": resolved_thread_id}},
    )
    return _response_from_state(final_state, resolved_thread_id)


async def resume_trip(
    thread_id: str,
    answer: str,
    selected_place: PlaceResult | None,
    google_maps_server_key: str,
    deepseek_api_key: str,
    deepseek_model: str,
    deepseek_base_url: str,
) -> TripPlannerResponse:
    try:
        from langgraph.types import Command
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="LangGraph is not installed.") from exc

    dependencies = PlannerDependencies(
        google_maps_server_key=google_maps_server_key,
        deepseek_api_key=deepseek_api_key,
        deepseek_model=deepseek_model,
        deepseek_base_url=deepseek_base_url,
    )
    graph = await _RUNTIME.get(dependencies)
    resume_value: dict[str, Any]
    if selected_place:
        resume_value = {"selectedPlace": selected_place.model_dump()}
    else:
        resume_value = {"answer": answer}
    try:
        final_state = await graph.ainvoke(
            Command(resume=resume_value),
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        if "checkpoint" in str(exc).lower() or "thread" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This trip-planning session expired. Start the trip again.",
            ) from exc
        raise
    return _response_from_state(final_state, thread_id)
