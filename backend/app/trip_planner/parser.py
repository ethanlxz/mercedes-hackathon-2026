import json
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from backend.app.trip_planner.models import (
    CURRENT_LOCATION_ALIASES,
    MALAYSIA_TZ,
    ParsedTrip,
    PlannerDependencies,
    PlannerState,
    _clean,
    _tag_name,
)


async def _parse_with_deepseek(
    state: PlannerState,
    dependencies: PlannerDependencies,
) -> ParsedTrip:
    if not dependencies.deepseek_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DEEPSEEK_API_KEY is missing from .env.",
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LangChain OpenAI dependencies are not installed.",
        ) from exc

    model = ChatOpenAI(
        model=dependencies.deepseek_model,
        api_key=dependencies.deepseek_api_key,
        base_url=dependencies.deepseek_base_url,
        temperature=0,
        max_retries=1,
    )
    json_model = model.bind(response_format={"type": "json_object"})
    schema = json.dumps(ParsedTrip.model_json_schema(), indent=2)
    prompt = f"""
You parse driving itineraries in Malaysia. Return one raw JSON object matching this exact JSON Schema:
{schema}

Today is {datetime.now(MALAYSIA_TZ).date().isoformat()} and the timezone is Asia/Kuala_Lumpur.

Context:
- home: {state['location_tags'].get('home') or '(not set)'}
- work: {state['location_tags'].get('work') or '(not set)'}
- current location: {state['user_settings'].get('currentLocation') or '(not set)'}
- stored route preferences: {json.dumps(state['stored_preferences'])}

Rules:
- Preserve chronological waypoint order and include the final destination as the last waypoint.
- Put the starting point only in origin. Never repeat the origin as the first waypoint.
- Use resolution=food_choice for vague meal requests such as lunch, dinner, hungry, or find food.
- Use resolution=category and selectionMode=choice for cuisine/category requests where the user should choose a business.
- Use selectionMode=nearest only when nearest/closest is explicit; otherwise use auto for a specifically named place.
- Put the requested area or landmark in nearbyReference for phrases such as near KLCC or around a named landmark.
- Keep aliases such as home, work, and current location as written; deterministic nodes resolve them.
- Set flexible=true only when the user permits reordering. Preserve explicit before/after constraints.
- Convert times to HH:MM Malaysia time. departureTime is the requested start time; arriveBy and departAfter belong to waypoints.
- Store visit duration in dwellMinutes.
- Route preference fields are null when unspecified, so explicit false can override a stored true value.
- If a named destination is genuinely ambiguous, set one concise clarificationQuestion.
- A vague food request inside a larger itinerary remains a waypoint at the position where the meal occurs.

Examples:
- "nearest McDonald's from home" => specific waypoint, selectionMode nearest.
- "find halal Japanese lunch near KLCC" => category waypoint, selectionMode choice, nearbyReference KLCC.
- "grab lunch" => food_choice waypoint, selectionMode choice.

Instruction:
{state['instruction']}
"""
    last_error: Exception | None = None
    for _ in range(2):
        try:
            result = await json_model.ainvoke(prompt)
            content = str(result.content).strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
                content = re.sub(r"\s*```$", "", content)
            payload = json.loads(content)
            return ParsedTrip.model_validate(_normalize_model_payload(payload, state["instruction"]))
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
            last_error = exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"DeepSeek could not parse the trip instruction: {exc}",
            ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"DeepSeek returned an invalid trip plan: {last_error}",
    )


def _normalize_model_payload(payload: Any, instruction: str) -> dict[str, Any]:
    """Accept minor DeepSeek schema drift while preserving typed graph state."""
    if not isinstance(payload, dict):
        raise ValueError("Trip parser output must be a JSON object.")

    normalized = dict(payload)
    if "preferences" not in normalized:
        normalized["preferences"] = normalized.get("routePreferences") or {}
    if "optimizeFlexible" not in normalized and isinstance(normalized.get("flexible"), bool):
        normalized["optimizeFlexible"] = normalized["flexible"]

    waypoints: list[dict[str, Any]] = []
    for raw in normalized.get("waypoints") or []:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item["query"] = _clean(str(item.get("query") or item.get("name") or item.get("alias") or ""))
        raw_resolution = str(item.get("resolution") or item.get("type") or "specific").lower()
        item["resolution"] = {
            "exact": "specific",
            "named": "specific",
            "location": "specific",
            "place": "specific",
            "food": "food_choice",
            "meal": "food_choice",
        }.get(raw_resolution, raw_resolution)
        if item["resolution"] not in {"specific", "category", "food_choice"}:
            item["resolution"] = "specific"
        if item.get("dwellMinutes") is None:
            item["dwellMinutes"] = 0
        if item.get("maxDriveMinutes") is None and item.get("maxDetourMinutes") is not None:
            item["maxDriveMinutes"] = item["maxDetourMinutes"]
        if item.get("flexible") is None:
            item["flexible"] = False
        if not item.get("selectionMode"):
            item["selectionMode"] = "choice" if item["resolution"] in {"category", "food_choice"} else "auto"
        if item["resolution"] == "food_choice":
            meal_words = {"food", "eat", "breakfast", "lunch", "dinner", "supper", "hungry", "place", "spot"}
            query_words = set(re.findall(r"[a-z]+", item["query"].lower()))
            if query_words - meal_words:
                item["resolution"] = "category"
                item["selectionMode"] = "choice"
        waypoints.append(item)

    if not normalized.get("origin") and waypoints:
        starts_with_origin = bool(
            re.search(r"^\s*(?:leave|from|start(?:ing)?\s+(?:at|from))\b", instruction, re.IGNORECASE)
        )
        first = waypoints[0]
        alias = _clean(str((normalized.get("waypoints") or [{}])[0].get("alias") or ""))
        if starts_with_origin or alias.lower() in CURRENT_LOCATION_ALIASES or _tag_name(alias):
            normalized["origin"] = alias or first["query"]
            waypoints.pop(0)

    normalized["waypoints"] = waypoints
    return normalized
