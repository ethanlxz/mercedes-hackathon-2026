import json
import re
from typing import Any, TypedDict

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, ValidationError

from backend.app.schemas.routes import RouteSummary
from backend.app.schemas.trip_planner import (
    NormalizedTripPlan,
    TripPlannerResponse,
    TripPreferences,
    TripWaypoint,
)
from backend.app.services.google_places import resolve_nearby_place
from backend.app.services.google_routes import compute_multi_stop_route
from backend.app.services.memory_service import get_preferences, update_preferences


class AgentParseResult(BaseModel):
    origin: str = ""
    stops: list[str] = Field(default_factory=list)
    destination: str = ""
    preferences: TripPreferences = Field(default_factory=TripPreferences)
    clarificationRequired: bool = False
    clarificationMessage: str | None = None


class PlannerState(TypedDict, total=False):
    instruction: str
    location_tags: dict[str, str]
    stored_preferences: dict[str, Any]
    parsed: AgentParseResult
    normalized_plan: NormalizedTripPlan
    waypoints: list[TripWaypoint]
    route_response: Any
    clarification_message: str | None


TAG_ALIASES = {
    "home": {"home", "my home", "house", "my house"},
    "work": {"work", "office", "my office", "workplace", "my workplace"},
}
NEARBY_WORDS = {"nearby", "nearest", "closest", "near me"}
NEARBY_TERMS = r"(?:nearby|neaby|nearest|closest|near me)"


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def _is_tag_alias(value: str, tag: str) -> bool:
    normalized = _clean_text(value).lower()
    return normalized in TAG_ALIASES[tag]


def _resolve_tag_value(value: str, location_tags: dict[str, str]) -> tuple[str, str | None]:
    cleaned = _clean_text(value)
    for tag in ("home", "work"):
        if _is_tag_alias(cleaned, tag):
            saved_address = location_tags.get(tag, "").strip()
            if not saved_address:
                return cleaned, tag
            return saved_address, None
    return cleaned, None


def _waypoint_label(address: str, location_tags: dict[str, str]) -> str:
    for tag, saved_address in location_tags.items():
        if saved_address and address.strip().lower() == saved_address.strip().lower():
            return tag.title()
    return address


def _has_nearby_intent(value: str) -> bool:
    normalized = _clean_text(value).lower()
    return (
        any(word in normalized for word in {*NEARBY_WORDS, "neaby"})
        or bool(re.search(r"\bnear\s+.+", normalized))
    )


def _nearby_lookup(value: str) -> tuple[str, str | None] | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None

    patterns = [
        rf"^(?:the\s+)?(?:nearest|closest|nearby|neaby)\s+(?P<query>.+)$",
        rf"^(?P<query>.+?)\s+{NEARBY_TERMS}(?:\s+(?P<reference>.+))?$",
        r"^(?P<query>.+?)\s+near\s+(?P<reference>.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            query = _clean_text(match.group("query"))
            reference = match.groupdict().get("reference")
            if query:
                return query, _clean_text(reference) if reference else None

    return None


def _fallback_nearby_parse(instruction: str) -> AgentParseResult | None:
    if not _has_nearby_intent(instruction):
        return None

    patterns = [
        r"^(?:please\s+)?(?:start\s+)?(?:from|at)\s+(?P<origin>.+?)\s+(?:to|towards|go\s+to)\s+(?P<destination>.+)$",
        r"^(?:please\s+)?go\s+from\s+(?P<origin>.+?)\s+to\s+(?P<destination>.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, _clean_text(instruction), flags=re.IGNORECASE)
        if match:
            return AgentParseResult(
                origin=_clean_text(match.group("origin")),
                stops=[],
                destination=_clean_text(match.group("destination")),
                preferences=TripPreferences(),
                clarificationRequired=False,
                clarificationMessage=None,
            )

    return None


def _place_query_label(query: str) -> str:
    return re.sub(r"^(?:a|an|the)\s+", "", _clean_text(query), flags=re.IGNORECASE)


async def _resolve_nearby_waypoint(
    value: str,
    default_reference: str,
    location_tags: dict[str, str],
    google_maps_server_key: str,
) -> tuple[str, str, str | None]:
    lookup = _nearby_lookup(value)
    if not lookup:
        return value, _waypoint_label(value, location_tags), None

    place_query, reference_override = lookup
    reference_location = default_reference
    if reference_override:
        reference_location, missing_tag = _resolve_tag_value(
            reference_override,
            location_tags,
        )
        if missing_tag:
            return (
                value,
                _place_query_label(place_query),
                f"Please save your {missing_tag.title()} address with Add Tags first.",
            )

    resolved_place = await resolve_nearby_place(
        place_query=place_query,
        reference_location=reference_location,
        api_key=google_maps_server_key,
    )
    if not resolved_place:
        return (
            value,
            _place_query_label(place_query),
            (
                f"I couldn't find a {_place_query_label(place_query)} near "
                f"{reference_location}. Try another landmark or address."
            ),
        )

    return resolved_place.address, resolved_place.label, None


def _merge_preferences(
    parsed_preferences: TripPreferences,
    stored_preferences: dict[str, Any],
) -> TripPreferences:
    return TripPreferences(
        avoidHighways=parsed_preferences.avoidHighways
        or bool(stored_preferences.get("avoidHighways")),
        avoidTolls=parsed_preferences.avoidTolls
        or bool(stored_preferences.get("avoidTolls")),
        fastestRoute=parsed_preferences.fastestRoute
        or bool(stored_preferences.get("fastestRoute")),
        timeWindows={
            **dict(stored_preferences.get("timeWindows") or {}),
            **parsed_preferences.timeWindows,
        },
    )


def _should_optimize_waypoints(plan: NormalizedTripPlan) -> bool:
    return (
        plan.preferences.fastestRoute
        and len(plan.stops) > 1
        and not plan.preferences.timeWindows
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek response was not a JSON object.")
    return parsed


async def _parse_with_deepseek(
    instruction: str,
    location_tags: dict[str, str],
    stored_preferences: dict[str, Any],
    deepseek_api_key: str,
    deepseek_model: str,
    deepseek_base_url: str,
) -> AgentParseResult:
    if not deepseek_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DEEPSEEK_API_KEY is missing from .env.",
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LangChain OpenAI dependencies are not installed. Run pip install -r backend/requirements.txt.",
        ) from exc

    model = ChatOpenAI(
        model=deepseek_model,
        api_key=deepseek_api_key,
        base_url=deepseek_base_url,
        temperature=0,
    )

    prompt = f"""
You are a trip-planning parser for a driving app in Malaysia.
Return exactly one raw JSON object. Do not use markdown fences.

Schema:
{{
  "origin": "string",
  "stops": ["string"],
  "destination": "string",
  "preferences": {{
    "avoidHighways": false,
    "avoidTolls": false,
    "fastestRoute": false,
    "timeWindows": {{}}
  }},
  "clarificationRequired": false,
  "clarificationMessage": null
}}

Saved location tag context:
- home: {location_tags.get("home") or "(not set)"}
- work: {location_tags.get("work") or "(not set)"}

Stored route preferences:
{stored_preferences}

Instructions:
- First silently rewrite the user instruction into clear trip-planning language before filling the JSON.
- Correct obvious typos and informal phrasing, for example "neaby" -> "nearby", "mcdonald" -> "McDonald's", "my house" -> "home", and "my office" -> "work".
- Normalize flexible natural language into origin, ordered stops, destination, and preferences.
- Understand aliases: home/my home/house, work/office/my office/workplace.
- If a saved tag is used and available, use the saved address.
- If a saved tag is referenced but missing, set clarificationRequired true and ask for that address.
- Do not ask which branch for chain or category names when the user says nearby, neaby, nearest, closest, near me, or near another place.
- Treat "neaby" as a typo for "nearby".
- Preserve nearby place lookups as strings like "Burger King nearby", "nearest Starbucks", "McDonald's near home", or "McDonald neaby my house" so backend tools can resolve them.
- Preserve chronological order for pickups, dropoffs, errands, sightseeing, meals, and time windows.
- Extract avoidHighways, avoidTolls, fastestRoute, and time windows.
- If the origin is omitted but the instruction starts from home and home is saved, use home.
- If the final destination is omitted but the user says return home, use home.
- If an important location is ambiguous, set clarificationRequired true with one short question.

User instruction:
{instruction}
"""
    try:
        result = await model.ainvoke(prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DeepSeek could not parse the trip instruction: {exc}",
        ) from exc

    try:
        parsed_content = _extract_json_object(str(result.content))
        parsed_result = AgentParseResult.model_validate(parsed_content)
        if parsed_result.clarificationRequired:
            fallback_result = _fallback_nearby_parse(instruction)
            if fallback_result:
                return fallback_result
        return parsed_result
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DeepSeek returned an invalid trip plan: {exc}",
        ) from exc


async def plan_trip(
    instruction: str,
    location_tags: dict[str, str],
    google_maps_server_key: str,
    deepseek_api_key: str,
    deepseek_model: str,
    deepseek_base_url: str,
) -> TripPlannerResponse:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LangGraph is not installed. Run pip install -r backend/requirements.txt.",
        ) from exc

    async def parse_node(state: PlannerState) -> PlannerState:
        parsed = await _parse_with_deepseek(
            instruction=state["instruction"],
            location_tags=state["location_tags"],
            stored_preferences=state["stored_preferences"],
            deepseek_api_key=deepseek_api_key,
            deepseek_model=deepseek_model,
            deepseek_base_url=deepseek_base_url,
        )
        return {"parsed": parsed}

    async def normalize_node(state: PlannerState) -> PlannerState:
        parsed = state["parsed"]
        if parsed.clarificationRequired:
            return {"clarification_message": parsed.clarificationMessage}

        origin, missing_origin = _resolve_tag_value(parsed.origin, state["location_tags"])
        if missing_origin:
            return {
                "clarification_message": (
                    f"Please save your {missing_origin.title()} address with Add Tags first."
                )
            }

        if not origin:
            return {
                "clarification_message": (
                    "Please include a clear start point and final destination."
                )
            }

        stops: list[str] = []
        stop_labels: list[str] = []
        previous_waypoint = origin
        for stop in parsed.stops:
            resolved_stop, missing_stop = _resolve_tag_value(stop, state["location_tags"])
            if missing_stop:
                return {
                    "clarification_message": (
                        f"Please save your {missing_stop.title()} address with Add Tags first."
                    )
                }

            stop_address, stop_label, stop_clarification = await _resolve_nearby_waypoint(
                value=resolved_stop,
                default_reference=previous_waypoint,
                location_tags=state["location_tags"],
                google_maps_server_key=google_maps_server_key,
            )
            if stop_clarification:
                return {"clarification_message": stop_clarification}

            stops.append(stop_address)
            stop_labels.append(stop_label)
            previous_waypoint = stop_address

        destination, missing_destination = _resolve_tag_value(
            parsed.destination,
            state["location_tags"],
        )
        if missing_destination:
            return {
                "clarification_message": (
                    f"Please save your {missing_destination.title()} address with Add Tags first."
                )
            }

        if not destination:
            return {
                "clarification_message": (
                    "Please include a clear start point and final destination."
                )
            }

        destination, destination_label, destination_clarification = await _resolve_nearby_waypoint(
            value=destination,
            default_reference=origin,
            location_tags=state["location_tags"],
            google_maps_server_key=google_maps_server_key,
        )
        if destination_clarification:
            return {"clarification_message": destination_clarification}

        if stops and stops[-1].strip().lower() == destination.strip().lower():
            stops.pop()
            stop_labels.pop()

        preferences = _merge_preferences(
            parsed_preferences=parsed.preferences,
            stored_preferences=state["stored_preferences"],
        )
        update_preferences(preferences.model_dump())

        plan = NormalizedTripPlan(
            origin=origin,
            stops=stops,
            destination=destination,
            preferences=preferences,
        )
        waypoints = [
            TripWaypoint(
                role="origin",
                label=_waypoint_label(origin, state["location_tags"]),
                address=origin,
            )
        ]
        waypoints.extend(
            TripWaypoint(role="stop", label=label, address=stop)
            for label, stop in zip(stop_labels, stops, strict=False)
        )
        waypoints.append(
            TripWaypoint(
                role="destination",
                label=destination_label,
                address=destination,
            )
        )

        return {
            "normalized_plan": plan,
            "waypoints": waypoints,
        }

    async def route_node(state: PlannerState) -> PlannerState:
        if state.get("clarification_message"):
            return {}

        plan = state["normalized_plan"]
        route_response = await compute_multi_stop_route(
            origin=plan.origin,
            stops=plan.stops,
            destination=plan.destination,
            preferences=plan.preferences,
            api_key=google_maps_server_key,
            optimize_waypoints=_should_optimize_waypoints(plan),
        )
        return {"route_response": route_response}

    graph = StateGraph(PlannerState)
    graph.add_node("parse", parse_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("route", route_node)
    graph.set_entry_point("parse")
    graph.add_edge("parse", "normalize")
    graph.add_edge("normalize", "route")
    graph.add_edge("route", END)
    app = graph.compile()

    final_state = await app.ainvoke(
        {
            "instruction": instruction,
            "location_tags": location_tags,
            "stored_preferences": get_preferences(),
        }
    )

    clarification_message = final_state.get("clarification_message")
    if clarification_message:
        return TripPlannerResponse(
            clarificationRequired=True,
            clarificationMessage=clarification_message,
        )

    route_response = final_state["route_response"]
    return TripPlannerResponse(
        normalizedPlan=final_state["normalized_plan"],
        waypoints=final_state["waypoints"],
        duration=route_response.duration,
        distanceMeters=route_response.distanceMeters,
        encodedPolyline=route_response.encodedPolyline,
        summary=route_response.summary,
        clarificationRequired=False,
        clarificationMessage=None,
    )
