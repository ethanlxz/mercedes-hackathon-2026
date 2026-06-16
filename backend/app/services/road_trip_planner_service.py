import json
import math
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from backend.app.schemas.trip_planner import RoadTripRecommendation, RoadTripPlannerResponse
from backend.app.services.google_places import ResolvedPlace, search_places
from backend.app.services.google_routes import compute_route
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
    if len(path) <= 2:
        return path

    samples: list[tuple[float, float]] = []
    for fraction in (0.25, 0.5, 0.75):
        index = min(len(path) - 1, max(0, round((len(path) - 1) * fraction)))
        samples.append(path[index])
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
) -> list[RecommendationCandidate]:
    candidates: list[RecommendationCandidate] = []
    for route_index, point in enumerate(points):
        for query, category, section in searches:
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


def _select_recommendations(
    candidates: list[RecommendationCandidate],
    explanations: dict[str, str],
    section: str,
    limit: int,
) -> list[RoadTripRecommendation]:
    deepseek_order = {
        key: index
        for index, key in enumerate(explanations)
    }
    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (
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


async def plan_road_trip(
    origin: str,
    destination: str,
    google_maps_server_key: str,
    deepseek_api_key: str,
    deepseek_model: str,
    deepseek_base_url: str,
) -> RoadTripPlannerResponse:
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
    )
    destination_candidates = await _search_candidates(
        DESTINATION_SEARCHES,
        [path[-1]],
        google_maps_server_key,
        max_result_count=4,
        query_context=destination,
        result_radius_meters=DESTINATION_SEARCH_RADIUS_METERS,
    )
    candidates = [*route_candidates, *destination_candidates]
    explanations = await _explain_with_deepseek(
        candidates,
        origin,
        destination,
        deepseek_api_key,
        deepseek_model,
        deepseek_base_url,
    )

    return RoadTripPlannerResponse(
        route=route,
        routeRecommendations=_select_recommendations(candidates, explanations, "route", 5),
        destinationRecommendations=_select_recommendations(
            candidates,
            explanations,
            "destination",
            DESTINATION_RECOMMENDATION_LIMIT,
        ),
        foodRecommendations=_select_recommendations(candidates, explanations, "food", 4),
    )
