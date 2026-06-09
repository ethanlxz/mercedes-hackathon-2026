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
from backend.app.services.google_places import resolve_nearby_place, search_place
from backend.app.services.google_routes import compute_multi_stop_route
from backend.app.services.memory_service import get_preferences, update_preferences
from backend.app.services.place_categories import (
    PLACE_CATEGORY_TYPES,
    normalize_place_category,
    place_category_pattern,
)


class AgentParseResult(BaseModel):
    origin: str = ""
    stops: list[str] = Field(default_factory=list)
    destination: str = ""
    preferences: TripPreferences = Field(default_factory=TripPreferences)
    clarificationRequired: bool = False
    clarificationMessage: str | None = None
    choiceRequired: bool = False
    choiceType: str | None = None
    choiceQuery: str = ""
    choiceReference: str = ""
    message: str | None = None


class PlannerState(TypedDict, total=False):
    instruction: str
    location_tags: dict[str, str]
    user_settings: dict[str, str]
    stored_preferences: dict[str, Any]
    parsed: AgentParseResult
    normalized_plan: NormalizedTripPlan
    waypoints: list[TripWaypoint]
    route_response: Any
    clarification_message: str | None
    choice_response: TripPlannerResponse | None


TAG_ALIASES = {
    "home": {"home", "my home", "house", "my house"},
    "work": {"work", "office", "my office", "workplace", "my workplace"},
}
CURRENT_LOCATION_ALIASES = {
    "current location",
    "my current location",
    "here",
    "from here",
    "my location",
}
NEARBY_WORDS = {"nearby", "nearest", "closest", "near me"}
NEARBY_TERMS = r"(?:nearby|neaby|nearest|closest|near me)"
VAGUE_FOOD_TERMS = {"breakfast", "lunch", "dinner", "supper", "food", "eat", "hungry"}
SPECIFIC_FOOD_TERMS = {
    "mcdonald",
    "mcdonald's",
    "burger king",
    "kfc",
    "starbucks",
    "japanese",
    "chinese",
    "hotpot",
    "mamak",
    "indian",
    "malay",
    "western",
    "italian",
    "restaurant",
    "cafe",
    "coffee",
}
PLACE_CATEGORY_TERMS = set(PLACE_CATEGORY_TYPES)


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


def _resolve_origin_value(
    value: str,
    location_tags: dict[str, str],
    user_settings: dict[str, str],
) -> tuple[str, str | None]:
    cleaned = _clean_text(value)
    if cleaned.lower() in CURRENT_LOCATION_ALIASES:
        current_location = str(user_settings.get("currentLocation") or "").strip()
        if not current_location:
            return cleaned, "currentLocation"
        return current_location, None

    return _resolve_tag_value(cleaned, location_tags)


def _waypoint_label(address: str, location_tags: dict[str, str]) -> str:
    for tag, saved_address in location_tags.items():
        if saved_address and address.strip().lower() == saved_address.strip().lower():
            return tag.title()
    return address


def _default_origin(
    user_settings: dict[str, str],
    location_tags: dict[str, str],
) -> tuple[str, str | None]:
    current_location = str(user_settings.get("currentLocation") or "").strip()
    if current_location:
        return current_location, None

    home = str(location_tags.get("home") or "").strip()
    if home:
        return home, None

    return "", "Please set Current Location in Settings or save your Home address first."


async def _choice_reference_origin(
    reference: str,
    user_settings: dict[str, str],
    location_tags: dict[str, str],
    google_maps_server_key: str,
) -> tuple[str, str | None]:
    cleaned_reference = _clean_text(reference)
    if not cleaned_reference:
        return _default_origin(user_settings, location_tags)

    resolved_tag, missing_tag = _resolve_tag_value(cleaned_reference, location_tags)
    if missing_tag:
        return "", f"Please save your {missing_tag.title()} address with Add Tags first."

    try:
        place = await search_place(
            text_query=resolved_tag,
            fallback_label=resolved_tag,
            api_key=google_maps_server_key,
        )
    except HTTPException:
        place = None

    return (place.address if place else resolved_tag), None


def _has_nearby_intent(value: str) -> bool:
    normalized = _clean_text(value).lower()
    return (
        any(word in normalized for word in {*NEARBY_WORDS, "neaby"})
        or bool(re.search(r"\bnear\s+.+", normalized))
    )


def _choice_message(instruction: str) -> str:
    normalized = _clean_text(instruction).lower()
    for meal in ("breakfast", "lunch", "dinner", "supper"):
        if meal in normalized:
            return f"What would you like for {meal}?"
    return "What would you like to eat?"


def _extract_near_reference(instruction: str) -> str:
    normalized = _clean_text(instruction)
    match = re.search(
        r"\bnear\s+(?P<reference>.+?)(?:\s+(?:too|also|as well))?$",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    reference = _clean_text(match.group("reference"))
    return re.sub(r"[.?!,;:]+$", "", reference).strip()


def _category_picker_match(instruction: str) -> re.Match[str] | None:
    normalized = _clean_text(instruction).lower()
    return re.search(
        rf"\b(?:nearest|nearby|closest|bring|take|drive|go|send|route|navigate)\s+(?:me\s+)?(?:to\s+)?(?:a\s+|an\s+|the\s+)?(?P<category>{place_category_pattern()})s?\b",
        normalized,
    )


def _contains_concrete_place_category(instruction: str) -> bool:
    normalized = _clean_text(instruction).lower()
    return any(
        re.search(rf"\b{re.escape(category)}s?\b", normalized)
        for category in PLACE_CATEGORY_TERMS | SPECIFIC_FOOD_TERMS
    )


def _has_itinerary_context(instruction: str) -> bool:
    normalized = _clean_text(instruction).lower()
    return bool(
        re.search(r"\b(?:from|start(?:ing)? at|start(?:ing)? from)\b", normalized)
        or len(re.findall(r"\b(?:then|after that|next)\b", normalized)) > 0
        or len(re.findall(r"\bto\b", normalized)) > 1
    )


def _direct_choice_intent(instruction: str) -> AgentParseResult | None:
    normalized = _clean_text(instruction).lower()
    if not normalized:
        return None

    mentions_specific_food = any(term in normalized for term in SPECIFIC_FOOD_TERMS)
    mentions_vague_food = any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in VAGUE_FOOD_TERMS)
    if mentions_vague_food and not mentions_specific_food:
        return AgentParseResult(
            choiceRequired=True,
            choiceType="food",
            choiceQuery="",
            choiceReference=_extract_near_reference(instruction),
            message=_choice_message(instruction),
        )

    nearby_category_match = _category_picker_match(instruction)
    if nearby_category_match:
        category = normalize_place_category(nearby_category_match.group("category"))
        return AgentParseResult(
            choiceRequired=True,
            choiceType="location",
            choiceQuery=category,
            choiceReference=_extract_near_reference(instruction),
            message=f"Choose a nearby {category}.",
        )

    return None


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


async def _enrich_waypoint_metadata(
    waypoints: list[TripWaypoint],
    google_maps_server_key: str,
) -> list[TripWaypoint]:
    enriched: list[TripWaypoint] = []
    for waypoint in waypoints:
        try:
            place = await search_place(
                text_query=waypoint.address,
                fallback_label=waypoint.label,
                api_key=google_maps_server_key,
            )
        except HTTPException:
            place = None

        if not place:
            enriched.append(waypoint)
            continue

        should_keep_label = waypoint.label.strip().lower() in {"home", "work"}
        label = waypoint.label if should_keep_label else place.label

        enriched.append(
            TripWaypoint(
                role=waypoint.role,
                label=label or waypoint.label,
                address=place.address or waypoint.address,
                rating=place.rating,
                googleMapsUri=place.google_maps_uri,
            )
        )
    return enriched


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
    user_settings: dict[str, str],
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
  "clarificationMessage": null,
  "choiceRequired": false,
  "choiceType": null,
  "choiceQuery": "",
  "choiceReference": "",
  "message": null
}}

Saved location tag context:
- home: {location_tags.get("home") or "(not set)"}
- work: {location_tags.get("work") or "(not set)"}

Settings context:
- currentLocation: {user_settings.get("currentLocation") or "(not set)"}

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
- If the origin is omitted without a home reference, leave origin as an empty string so backend default origin rules can use currentLocation, then home.
- If the final destination is omitted but the user says return home, use home.
- For vague meal or hunger requests like "bring me to dinner", "I want to eat breakfast", "eat food", "find me a lunch spot", or "I'm hungry", set choiceRequired true, choiceType "food", and message like "What would you like for lunch?". Do not set a destination.
- If a vague meal request is embedded in a larger itinerary, still fill origin, stops, and destination for the non-meal route context, then set choiceRequired true for the meal choice.
- Example: "I want to go from home to KLCC then go Everynation Puchong, find me a lunch spot near Everynation too" should keep origin home, include KLCC as a stop, destination Everynation Puchong, set choiceRequired true, choiceType "food", message "What would you like for lunch?", and choiceReference "Everynation".
- If a choice request includes a nearby reference like "near Everynation", "around KLCC", or "near my office", put that reference in choiceReference so backend tools search near that place instead of Current Location/Home.
- Do not treat concrete place categories like cafe, coffee shop, restaurant, mall, hospital, or clinic as vague meals.
- Do not set choiceRequired for specific food/place requests like "nearest McDonald's", "Burger King nearby", "Japanese food near me", or "Starbucks near KL Sentral"; keep those as routable nearby place strings.
- For category requests like "bring me to cafe", "nearest restaurant", "nearest mall", "nearest hospital", or "nearest clinic", set choiceRequired true, choiceType "location", choiceQuery to the category, and message like "Choose a nearby cafe.".
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
        category_choice = _direct_choice_intent(instruction)
        if (
            parsed_result.choiceRequired
            and parsed_result.choiceType == "food"
            and _contains_concrete_place_category(instruction)
            and category_choice
        ):
            return category_choice
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
    user_settings: dict[str, str],
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
        direct_choice = _direct_choice_intent(state["instruction"])
        if direct_choice and not _has_itinerary_context(state["instruction"]):
            return {"parsed": direct_choice}

        parsed = await _parse_with_deepseek(
            instruction=state["instruction"],
            location_tags=state["location_tags"],
            user_settings=state["user_settings"],
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

        if parsed.choiceRequired:
            reference_origin, reference_clarification = await _choice_reference_origin(
                reference=parsed.choiceReference,
                user_settings=state["user_settings"],
                location_tags=state["location_tags"],
                google_maps_server_key=google_maps_server_key,
            )
            if reference_clarification:
                return {"clarification_message": reference_clarification}

            plan: NormalizedTripPlan | None = None
            waypoints: list[TripWaypoint] = []
            if parsed.origin or parsed.stops or parsed.destination:
                origin, missing_origin = _resolve_origin_value(
                    parsed.origin,
                    state["location_tags"],
                    state["user_settings"],
                )
                if missing_origin:
                    if missing_origin == "currentLocation":
                        return {
                            "clarification_message": (
                                "Please set Current Location in Settings first."
                            )
                        }
                    return {
                        "clarification_message": (
                            f"Please save your {missing_origin.title()} address with Add Tags first."
                        )
                    }

                if not origin:
                    origin, default_origin_clarification = _default_origin(
                        user_settings=state["user_settings"],
                        location_tags=state["location_tags"],
                    )
                    if default_origin_clarification:
                        return {"clarification_message": default_origin_clarification}

                stops: list[str] = []
                stop_labels: list[str] = []
                previous_waypoint = origin
                for stop in parsed.stops:
                    resolved_stop, missing_stop = _resolve_tag_value(
                        stop,
                        state["location_tags"],
                    )
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

                if destination:
                    destination, destination_label, destination_clarification = await _resolve_nearby_waypoint(
                        value=destination,
                        default_reference=origin,
                        location_tags=state["location_tags"],
                        google_maps_server_key=google_maps_server_key,
                    )
                    if destination_clarification:
                        return {"clarification_message": destination_clarification}

                    preferences = _merge_preferences(
                        parsed_preferences=parsed.preferences,
                        stored_preferences=state["stored_preferences"],
                    )
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
                    waypoints = await _enrich_waypoint_metadata(
                        waypoints=waypoints,
                        google_maps_server_key=google_maps_server_key,
                    )

            return {
                "choice_response": TripPlannerResponse(
                    normalizedPlan=plan,
                    waypoints=waypoints,
                    choiceRequired=True,
                    choiceType=parsed.choiceType if parsed.choiceType in {"food", "location"} else "food",
                    choiceQuery=parsed.choiceQuery,
                    choiceReference=parsed.choiceReference,
                    message=parsed.message or "What would you like?",
                    referenceOrigin=reference_origin,
                )
            }

        origin, missing_origin = _resolve_origin_value(
            parsed.origin,
            state["location_tags"],
            state["user_settings"],
        )
        if missing_origin:
            if missing_origin == "currentLocation":
                return {
                    "clarification_message": (
                        "Please set Current Location in Settings first."
                    )
                }
            return {
                "clarification_message": (
                    f"Please save your {missing_origin.title()} address with Add Tags first."
                )
            }

        if not origin:
            origin, default_origin_clarification = _default_origin(
                user_settings=state["user_settings"],
                location_tags=state["location_tags"],
            )
            if default_origin_clarification:
                return {"clarification_message": default_origin_clarification}

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
        waypoints = await _enrich_waypoint_metadata(
            waypoints=waypoints,
            google_maps_server_key=google_maps_server_key,
        )

        return {
            "normalized_plan": plan,
            "waypoints": waypoints,
        }

    async def route_node(state: PlannerState) -> PlannerState:
        if state.get("clarification_message") or state.get("choice_response"):
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
            "user_settings": user_settings,
            "stored_preferences": get_preferences(),
        }
    )

    clarification_message = final_state.get("clarification_message")
    if clarification_message:
        return TripPlannerResponse(
            clarificationRequired=True,
            clarificationMessage=clarification_message,
        )

    choice_response = final_state.get("choice_response")
    if choice_response:
        return choice_response

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
