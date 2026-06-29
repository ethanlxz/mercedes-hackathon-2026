import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from backend.app.trip_planner.schemas import RoadTripRecommendation, RoadTripPlannerResponse
from backend.app.services.google_places import ResolvedPlace, search_places
from backend.app.services.google_routes import compute_route
from backend.app.services.memory_service import get_central_agent_memory
from backend.app.services.place_categories import google_place_type_for_category


ROUTE_SEARCHES: tuple[tuple[str, str, str], ...] = (
    ("kopitiam", "Local food stop", "route"),
    ("cafe", "Coffee break", "route"),
    ("attractions", "Scenic stop", "route"),
    ("mall", "Rest stop", "route"),
)
DESTINATION_SEARCHES: tuple[tuple[str, str, str], ...] = (
    ("attractions", "Fun place", "destination"),
    ("sightseeing", "Sightseeing", "destination"),
    ("landmarks", "Landmark", "destination"),
    ("mall", "Shopping stop", "destination"),
    ("restaurants", "Restaurant", "food"),
    ("cafe", "Cafe", "food"),
    ("local food", "Local food", "food"),
)

DESTINATION_RECOMMENDATION_LIMIT = 8
DESTINATION_SEARCH_RADIUS_METERS = 35_000
ROUTE_RECOMMENDATION_LIMIT = 10
ROUTE_SEARCH_RESULT_COUNT = 3
ROUTE_RECOMMENDATION_MAX_DISTANCE_METERS = 8_000


@dataclass(frozen=True)
class RecommendationCandidate:
    place: ResolvedPlace
    category: str
    section: str
    route_index: int


class ExplainedRecommendation(BaseModel):
    placeId: str = ""
    name: str = ""
    explanation: str = Field(default="", max_length=260)


class ExplainedRecommendations(BaseModel):
    recommendations: list[ExplainedRecommendation] = Field(default_factory=list)


def _decode_polyline(value: str) -> list[tuple[float, float]]:
    index = 0
    lat = 0
    lng = 0
    points: list[tuple[float, float]] = []

    while index < len(value):
        result = 0
        shift = 0
        while True:
            byte = ord(value[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lat += ~(result >> 1) if result & 1 else result >> 1

        result = 0
        shift = 0
        while True:
            byte = ord(value[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        lng += ~(result >> 1) if result & 1 else result >> 1
        points.append((lat / 1e5, lng / 1e5))

    return points


def _sample_route_points(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(path) < 2:
        return path

    segment_lengths = [
        _distance_meters(start, end)
        for start, end in zip(path, path[1:], strict=False)
    ]
    total_distance = sum(segment_lengths)
    if total_distance <= 0:
        return path[:1]

    samples: list[tuple[float, float]] = []
    for fraction in (0.15, 0.3, 0.5, 0.7, 0.85):
        target_distance = total_distance * fraction
        traveled = 0.0
        for index, segment_length in enumerate(segment_lengths):
            next_traveled = traveled + segment_length
            if target_distance <= next_traveled or index == len(segment_lengths) - 1:
                start_lat, start_lng = path[index]
                end_lat, end_lng = path[index + 1]
                position = 0 if segment_length == 0 else (target_distance - traveled) / segment_length
                samples.append((
                    start_lat + (end_lat - start_lat) * position,
                    start_lng + (end_lng - start_lng) * position,
                ))
                break
            traveled = next_traveled
    return samples


def _candidate_key(candidate: RecommendationCandidate) -> str:
    place = candidate.place
    if place.place_id:
        return place.place_id
    return f"{place.label.lower()}|{place.address.lower()}"


def _dedupe_candidates(
    candidates: list[RecommendationCandidate],
) -> list[RecommendationCandidate]:
    seen: set[str] = set()
    deduped: list[RecommendationCandidate] = []
    for candidate in candidates:
        if candidate.place.latitude is None or candidate.place.longitude is None:
            continue
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _distance_meters(
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    first_lat, first_lng = first
    second_lat, second_lng = second
    radius_meters = 6_371_000
    lat_delta = math.radians(second_lat - first_lat)
    lng_delta = math.radians(second_lng - first_lng)
    first_lat_rad = math.radians(first_lat)
    second_lat_rad = math.radians(second_lat)
    haversine = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(first_lat_rad)
        * math.cos(second_lat_rad)
        * math.sin(lng_delta / 2) ** 2
    )
    return 2 * radius_meters * math.asin(min(1, math.sqrt(haversine)))


def _distance_to_segment_meters(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    lat, lng = point
    start_lat, start_lng = start
    end_lat, end_lng = end
    reference_lat = math.radians((lat + start_lat + end_lat) / 3)
    meters_per_degree_lat = 111_320
    meters_per_degree_lng = 111_320 * math.cos(reference_lat)
    px = lng * meters_per_degree_lng
    py = lat * meters_per_degree_lat
    ax = start_lng * meters_per_degree_lng
    ay = start_lat * meters_per_degree_lat
    bx = end_lng * meters_per_degree_lng
    by = end_lat * meters_per_degree_lat
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    position = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    closest_x = ax + position * dx
    closest_y = ay + position * dy
    return math.hypot(px - closest_x, py - closest_y)


def _distance_to_route_meters(
    candidate: RecommendationCandidate,
    path: list[tuple[float, float]],
) -> float:
    place = candidate.place
    if place.latitude is None or place.longitude is None:
        return math.inf
    point = (place.latitude, place.longitude)
    if len(path) < 2:
        return _distance_meters(point, path[0]) if path else math.inf
    return min(
        _distance_to_segment_meters(point, start, end)
        for start, end in zip(path, path[1:], strict=False)
    )


def _within_radius(
    candidate: RecommendationCandidate,
    center: tuple[float, float],
    radius_meters: float,
) -> bool:
    place = candidate.place
    if place.latitude is None or place.longitude is None:
        return False
    return _distance_meters(center, (place.latitude, place.longitude)) <= radius_meters


async def _search_candidates(
    searches: tuple[tuple[str, str, str], ...],
    points: list[tuple[float, float]],
    api_key: str,
    max_result_count: int = 2,
    query_context: str = "",
    result_radius_meters: int | None = None,
    route_path: list[tuple[float, float]] | None = None,
    preference_memory: dict[str, Any] | None = None,
) -> list[RecommendationCandidate]:
    candidates: list[RecommendationCandidate] = []
    ordered_searches = _ordered_searches(searches, preference_memory or {})
    for route_index, point in enumerate(points):
        for query, category, section in ordered_searches:
            included_type = google_place_type_for_category(query)
            text_query = f"{query} in {query_context}" if query_context else query
            places = await search_places(
                text_query=text_query,
                fallback_label=query,
                api_key=api_key,
                max_result_count=max_result_count,
                included_type=included_type,
                strict_type_filtering=bool(included_type),
                location_bias=point,
            )
            candidates.extend(
                RecommendationCandidate(
                    place=place,
                    category=category,
                    section=section,
                    route_index=route_index,
                )
                for place in places
            )
    deduped = _dedupe_candidates(candidates)
    if result_radius_meters is None:
        return deduped
    if route_path:
        return [
            candidate
            for candidate in deduped
            if _distance_to_route_meters(candidate, route_path) <= result_radius_meters
        ]
    return [
        candidate
        for candidate in deduped
        if _within_radius(candidate, points[candidate.route_index], result_radius_meters)
    ]


def _candidate_payload(candidate: RecommendationCandidate) -> dict[str, Any]:
    place = candidate.place
    return {
        "placeId": place.place_id,
        "name": place.label,
        "googleFormattedAddress": place.address,
        "category": candidate.category,
        "section": candidate.section,
        "rating": place.rating,
        "userRatingCount": place.user_rating_count,
        "routeIndex": candidate.route_index,
    }


def _normalized_category(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _preference_count(
    preference_memory: dict[str, Any],
    key: str,
    category: str,
) -> int:
    counts = preference_memory.get(key) or {}
    if not isinstance(counts, dict):
        return 0
    normalized = _normalized_category(category)
    for raw_category, raw_count in counts.items():
        if _normalized_category(str(raw_category)) != normalized:
            continue
        try:
            return max(0, int(raw_count))
        except (TypeError, ValueError):
            return 0
    return 0


def _preference_score(
    preference_memory: dict[str, Any],
    category: str,
) -> int:
    return (
        _preference_count(preference_memory, "preferredStopTypes", category)
        - _preference_count(preference_memory, "dislikedStopTypes", category)
    )


def _ordered_searches(
    searches: tuple[tuple[str, str, str], ...],
    preference_memory: dict[str, Any],
) -> list[tuple[str, str, str]]:
    return sorted(
        searches,
        key=lambda item: (
            -_preference_score(preference_memory, item[1]),
            searches.index(item),
        ),
    )


def _preference_prompt(preference_memory: dict[str, Any]) -> str:
    preferred = preference_memory.get("preferredStopTypes") or {}
    disliked = preference_memory.get("dislikedStopTypes") or {}
    preferred_text = ", ".join(
        category
        for category, _ in sorted(
            preferred.items(),
            key=lambda item: (-int(item[1]), str(item[0]).lower()),
        )[:5]
    )
    disliked_text = ", ".join(
        category
        for category, _ in sorted(
            disliked.items(),
            key=lambda item: (-int(item[1]), str(item[0]).lower()),
        )[:5]
    )
    if not preferred_text and not disliked_text:
        return "No learned stop preferences yet."
    return (
        f"Soft user preferences: prefer [{preferred_text or 'none'}]; "
        f"deprioritize [{disliked_text or 'none'}]."
    )


def _fallback_explanation(candidate: RecommendationCandidate) -> str:
    place = candidate.place
    rating = f" It has a {place.rating:g} Google rating." if place.rating else ""
    return (
        f"{place.label} is a practical {candidate.category.lower()} for this road trip "
        f"because it fits the route area and uses the Google Maps address shown here.{rating}"
    )


def _sort_candidates(candidates: list[RecommendationCandidate]) -> list[RecommendationCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.route_index,
            -(candidate.place.rating or 0),
            -(candidate.place.user_rating_count or 0),
            candidate.place.label,
        ),
    )


def _candidate_explanation_key(candidate: RecommendationCandidate) -> str:
    return candidate.place.place_id or candidate.place.label.lower()


def _strip_fenced_json(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


async def _explain_with_deepseek(
    candidates: list[RecommendationCandidate],
    origin: str,
    destination: str,
    deepseek_api_key: str,
    deepseek_model: str,
    deepseek_base_url: str,
    preference_memory: dict[str, Any] | None = None,
) -> dict[str, str]:
    if not candidates or not deepseek_api_key:
        return {}

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return {}

    model = ChatOpenAI(
        model=deepseek_model,
        api_key=deepseek_api_key,
        base_url=deepseek_base_url,
        temperature=0.35,
        max_retries=1,
    ).bind(response_format={"type": "json_object"})
    candidate_payloads = [_candidate_payload(candidate) for candidate in candidates]
    prompt = f"""
You are recommending road-trip stops in Malaysia from {origin} to {destination}.

Use only the Google Places candidate data below. Do not invent addresses, ratings,
reviews, opening hours, history, or menu items. Return JSON only:
{{
  "recommendations": [
    {{"placeId": "...", "name": "...", "explanation": "short reason, max 26 words"}}
  ]
}}

Choose the best mix of along-route stops, destination attractions, and food.
{_preference_prompt(preference_memory or {})}
Mention why it is useful for this road trip. For food, mention cuisine/category
only if it is clear from the place name or category.

Candidates:
{json.dumps(candidate_payloads, ensure_ascii=True)}
"""
    try:
        result = await model.ainvoke(prompt)
        payload = json.loads(_strip_fenced_json(str(result.content)))
        parsed = ExplainedRecommendations.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return {}
    except Exception:
        return {}

    explanations: dict[str, str] = {}
    for item in parsed.recommendations:
        key = item.placeId or item.name.lower()
        if key and item.explanation:
            explanations[key] = item.explanation
    return explanations


def _recommendation_from_candidate(
    candidate: RecommendationCandidate,
    explanation: str,
) -> RoadTripRecommendation:
    place = candidate.place
    return RoadTripRecommendation(
        id=_recommendation_id(candidate),
        placeId=place.place_id,
        name=place.label,
        address=place.address,
        latitude=float(place.latitude),
        longitude=float(place.longitude),
        category=candidate.category,
        section=candidate.section,
        rating=place.rating,
        userRatingCount=place.user_rating_count,
        googleMapsUri=place.google_maps_uri,
        explanation=explanation,
    )


def _recommendation_id(candidate: RecommendationCandidate) -> str:
    place = candidate.place
    raw = place.place_id or f"{candidate.section}|{place.label}|{place.address}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{candidate.section}-{digest}"


def _select_recommendations(
    candidates: list[RecommendationCandidate],
    explanations: dict[str, str],
    section: str,
    limit: int,
    preference_memory: dict[str, Any] | None = None,
) -> list[RoadTripRecommendation]:
    preference_memory = preference_memory or {}
    deepseek_order = {
        key: index
        for index, key in enumerate(explanations)
    }
    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (
            -_preference_score(preference_memory, candidate.category),
            deepseek_order.get(_candidate_explanation_key(candidate), 10_000),
            candidate.route_index,
            -(candidate.place.rating or 0),
            -(candidate.place.user_rating_count or 0),
            candidate.place.label,
        ),
    )
    selected: list[RoadTripRecommendation] = []
    for candidate in ordered_candidates:
        if candidate.section != section:
            continue
        place = candidate.place
        key = _candidate_explanation_key(candidate)
        explanation = explanations.get(key) or _fallback_explanation(candidate)
        selected.append(_recommendation_from_candidate(candidate, explanation))
        if len(selected) >= limit:
            break
    return selected


def _candidate_rank_key(
    candidate: RecommendationCandidate,
    explanations: dict[str, str],
    preference_memory: dict[str, Any],
) -> tuple[int, int, float, int, str]:
    deepseek_order = {
        key: index
        for index, key in enumerate(explanations)
    }
    return (
        -_preference_score(preference_memory, candidate.category),
        deepseek_order.get(_candidate_explanation_key(candidate), 10_000),
        -(candidate.place.rating or 0),
        -(candidate.place.user_rating_count or 0),
        candidate.place.label,
    )


def _select_route_recommendations(
    candidates: list[RecommendationCandidate],
    explanations: dict[str, str],
    limit: int,
    preference_memory: dict[str, Any] | None = None,
) -> list[RoadTripRecommendation]:
    preference_memory = preference_memory or {}
    groups: dict[int, list[RecommendationCandidate]] = {}
    for candidate in candidates:
        if candidate.section != "route":
            continue
        groups.setdefault(candidate.route_index, []).append(candidate)

    for route_index, group in groups.items():
        groups[route_index] = sorted(
            group,
            key=lambda candidate: _candidate_rank_key(candidate, explanations, preference_memory),
        )

    selected: list[RoadTripRecommendation] = []
    seen: set[str] = set()
    ordered_indexes = sorted(groups)
    while len(selected) < limit:
        added_this_round = False
        for route_index in ordered_indexes:
            group = groups[route_index]
            while group:
                candidate = group.pop(0)
                key = _candidate_key(candidate)
                if key in seen:
                    continue
                seen.add(key)
                explanation_key = _candidate_explanation_key(candidate)
                explanation = explanations.get(explanation_key) or _fallback_explanation(candidate)
                selected.append(_recommendation_from_candidate(candidate, explanation))
                added_this_round = True
                break
            if len(selected) >= limit:
                break
        if not added_this_round:
            break
    return selected


async def plan_road_trip(
    origin: str,
    destination: str,
    google_maps_server_key: str,
    deepseek_api_key: str,
    deepseek_model: str,
    deepseek_base_url: str,
) -> RoadTripPlannerResponse:
    preference_memory = get_central_agent_memory()
    route = await compute_route(
        origin=origin,
        destination=destination,
        api_key=google_maps_server_key,
    )
    path = _decode_polyline(route.encodedPolyline)
    if not path:
        return RoadTripPlannerResponse(route=route)

    route_candidates = await _search_candidates(
        ROUTE_SEARCHES,
        _sample_route_points(path),
        google_maps_server_key,
        max_result_count=ROUTE_SEARCH_RESULT_COUNT,
        result_radius_meters=ROUTE_RECOMMENDATION_MAX_DISTANCE_METERS,
        route_path=path,
        preference_memory=preference_memory,
    )
    destination_candidates = await _search_candidates(
        DESTINATION_SEARCHES,
        [path[-1]],
        google_maps_server_key,
        max_result_count=4,
        query_context=destination,
        result_radius_meters=DESTINATION_SEARCH_RADIUS_METERS,
        preference_memory=preference_memory,
    )
    candidates = [*route_candidates, *destination_candidates]
    explanations = await _explain_with_deepseek(
        candidates,
        origin,
        destination,
        deepseek_api_key,
        deepseek_model,
        deepseek_base_url,
        preference_memory,
    )

    return RoadTripPlannerResponse(
        route=route,
        routeRecommendations=_select_route_recommendations(
            route_candidates,
            explanations,
            ROUTE_RECOMMENDATION_LIMIT,
            preference_memory,
        ),
        destinationRecommendations=_select_recommendations(
            candidates,
            explanations,
            "destination",
            DESTINATION_RECOMMENDATION_LIMIT,
            preference_memory,
        ),
        foodRecommendations=_select_recommendations(
            candidates,
            explanations,
            "food",
            4,
            preference_memory,
        ),
    )
