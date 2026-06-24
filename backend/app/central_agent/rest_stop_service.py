import math
from dataclasses import dataclass

from backend.app.central_agent.schemas import GeoLocation, RestStopPlace
from backend.app.central_agent.state import ActiveRoadTrip
from backend.app.services.google_places import ResolvedPlace, search_places
from backend.app.services.place_categories import google_place_type_for_category
from backend.app.trip_planner.road_trip_service import _decode_polyline


REST_STOP_SEARCHES: tuple[tuple[str, str], ...] = (
    ("rest area", "Rest area"),
    ("R&R", "R&R"),
    ("petrol station", "Petrol station"),
    ("cafe", "Cafe"),
    ("mall", "Mall"),
    ("EV charging station", "EV charging"),
)


@dataclass(frozen=True)
class RestStopCandidate:
    place: RestStopPlace
    category: str
    distance_meters: int
    route_distance_meters: int
    estimated_drive_seconds: int


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


def _nearest_route_distance(
    point: tuple[float, float],
    path: list[tuple[float, float]],
) -> int:
    if not path:
        return 0
    return int(min(_distance_meters(point, route_point) for route_point in path))


def _current_point(
    path: list[tuple[float, float]],
    location: GeoLocation | None,
) -> tuple[float, float] | None:
    if location:
        return location.latitude, location.longitude
    if not path:
        return None
    index = min(len(path) - 1, max(0, round((len(path) - 1) * 0.15)))
    return path[index]


def _search_points(
    path: list[tuple[float, float]],
    current: tuple[float, float],
) -> list[tuple[float, float]]:
    if len(path) <= 3:
        return path or [current]

    nearest_index = min(
        range(len(path)),
        key=lambda index: _distance_meters(current, path[index]),
    )
    tail = path[nearest_index:] or path
    samples: list[tuple[float, float]] = []
    for fraction in (0.12, 0.28, 0.45):
        index = min(len(tail) - 1, max(0, round((len(tail) - 1) * fraction)))
        samples.append(tail[index])
    return samples


def _place_key(place: ResolvedPlace) -> str:
    if place.place_id:
        return place.place_id
    return f"{place.label.lower()}|{place.address.lower()}"


def _place_to_rest_stop(place: ResolvedPlace) -> RestStopPlace:
    return RestStopPlace(
        name=place.label,
        address=place.address,
        placeId=place.place_id,
        latitude=place.latitude,
        longitude=place.longitude,
        rating=place.rating,
        userRatingCount=place.user_rating_count,
        googleMapsUri=place.google_maps_uri,
    )


def rank_rest_stop_candidates(
    candidates: list[RestStopCandidate],
    severity: str,
) -> list[RestStopCandidate]:
    severity_weight = {"critical": 0.7, "high": 0.85}.get(severity, 1.0)
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.estimated_drive_seconds * severity_weight,
            candidate.route_distance_meters,
            -(candidate.place.rating or 0),
            -(candidate.place.userRatingCount or 0),
            candidate.place.name,
        ),
    )


async def find_rest_stop_candidates(
    *,
    active_route: ActiveRoadTrip,
    location: GeoLocation | None,
    severity: str,
    api_key: str,
) -> list[RestStopCandidate]:
    path = _decode_polyline(active_route.route.encodedPolyline)
    current = _current_point(path, location)
    if not path or not current:
        return []

    candidates: list[RestStopCandidate] = []
    seen: set[str] = set()
    route_points = _search_points(path, current)
    for route_point in route_points:
        for query, category in REST_STOP_SEARCHES:
            included_type = google_place_type_for_category(query)
            places = await search_places(
                text_query=query,
                fallback_label=query,
                api_key=api_key,
                max_result_count=2,
                included_type=included_type,
                strict_type_filtering=bool(included_type),
                location_bias=route_point,
            )
            for place in places:
                if place.latitude is None or place.longitude is None:
                    continue
                key = _place_key(place)
                if key in seen:
                    continue
                seen.add(key)
                place_point = (place.latitude, place.longitude)
                distance = int(_distance_meters(current, place_point))
                route_distance = _nearest_route_distance(place_point, path)
                candidates.append(
                    RestStopCandidate(
                        place=_place_to_rest_stop(place),
                        category=category,
                        distance_meters=distance,
                        route_distance_meters=route_distance,
                        estimated_drive_seconds=max(60, round(distance / 22.2)),
                    )
                )

    return rank_rest_stop_candidates(candidates, severity)

