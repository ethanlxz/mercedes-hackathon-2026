import re

from backend.app.services.google_places import ResolvedPlace
from backend.app.services.location_context import clean_text, default_origin
from backend.app.services.place_categories import google_place_type_for_category
from backend.app.trip_planner.models import (
    CURRENT_LOCATION_ALIASES,
    FOOD_CATEGORY_TERMS,
    Candidate,
    ParsedPreferences,
    WaypointIntent,
    _clean,
    _tag_name,
)
from backend.app.trip_planner.schemas import PlaceResult, TripPreferences


def _resolve_context_value(
    value: str,
    location_tags: dict[str, str],
    user_settings: dict[str, str],
) -> tuple[str, str | None]:
    cleaned = clean_text(value)
    if cleaned.lower() in CURRENT_LOCATION_ALIASES:
        current = clean_text(str(user_settings.get("currentLocation") or ""))
        return (current, None) if current else ("", "Please set Current Location in Settings first.")

    tag = _tag_name(cleaned)
    if tag:
        address = clean_text(str(location_tags.get(tag) or ""))
        if not address:
            return "", f"Please save your {tag.title()} address with Add Tags first."
        return address, None
    return cleaned, None


def _default_origin(
    location_tags: dict[str, str],
    user_settings: dict[str, str],
) -> tuple[str, str | None]:
    return default_origin(location_tags, user_settings)


def _merge_preferences(
    parsed: ParsedPreferences,
    stored: dict[str, object],
) -> TripPreferences:
    def selected(value: bool | None, key: str) -> bool:
        return bool(stored.get(key)) if value is None else value

    return TripPreferences(
        avoidHighways=selected(parsed.avoidHighways, "avoidHighways"),
        avoidTolls=selected(parsed.avoidTolls, "avoidTolls"),
        fastestRoute=selected(parsed.fastestRoute, "fastestRoute"),
        timeWindows={},
    )


def _candidate_from_place(place: ResolvedPlace) -> Candidate:
    return Candidate(
        name=place.label,
        address=place.address,
        placeId=place.place_id,
        latitude=place.latitude,
        longitude=place.longitude,
        rating=place.rating,
        userRatingCount=place.user_rating_count,
        googleMapsUri=place.google_maps_uri,
    )


def _place_result(candidate: Candidate) -> PlaceResult:
    return PlaceResult(
        name=candidate.name,
        address=candidate.address,
        placeId=candidate.placeId,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        rating=candidate.rating,
        userRatingCount=candidate.userRatingCount,
        googleMapsUri=candidate.googleMapsUri,
    )


def _is_food_category_query(value: str) -> bool:
    words = set(re.findall(r"[a-z]+", value.lower()))
    return bool(words & FOOD_CATEGORY_TERMS)


def _normalize_place_intent(intent: WaypointIntent) -> tuple[WaypointIntent, str | None]:
    included_type = google_place_type_for_category(intent.query)
    if intent.resolution == "food_choice":
        return intent, None

    if included_type:
        mode = "nearest" if intent.selectionMode == "nearest" else "choice"
        return intent.model_copy(update={"resolution": "category", "selectionMode": mode}), included_type

    if intent.resolution == "category" and _is_food_category_query(intent.query):
        return intent, "restaurant"

    if intent.resolution == "category":
        return intent.model_copy(update={"resolution": "specific", "selectionMode": "auto"}), None

    return intent, None


def _candidate_is_confident(query: str, candidate: Candidate) -> bool:
    ignored = {"the", "a", "an", "near", "nearest", "closest", "branch"}
    query_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if token not in ignored and len(token) > 2
    }
    name_tokens = set(re.findall(r"[a-z0-9]+", candidate.name.lower()))
    meaningful = query_tokens & name_tokens
    return bool(query_tokens) and len(meaningful) >= min(2, len(query_tokens))


def _candidate_text_score(query: str, candidate: Candidate) -> float:
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    name_tokens = set(re.findall(r"[a-z0-9]+", candidate.name.lower()))
    if not query_tokens:
        return 0.0
    return len(query_tokens & name_tokens) / len(query_tokens)
