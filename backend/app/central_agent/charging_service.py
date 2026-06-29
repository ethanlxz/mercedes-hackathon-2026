import math
from uuid import uuid4

from fastapi import HTTPException, status

from backend.app.central_agent.schemas import (
    ChargingDecision,
    ChargingRecommendation,
    ChargingRecommendationRequest,
    ChargingRecommendationResponse,
    ChargingStationOption,
    ChargingStopAcceptRequest,
    NotificationAction,
    RestStopPlace,
)
from backend.app.central_agent.state import (
    ActiveRoadTrip,
    get_active_road_trip,
    update_active_road_trip,
)
from backend.app.routers.battery import model_service as battery_model_service
from backend.app.schemas.routes import RouteResponse, RouteSummary, RouteWaypoint
from backend.app.services.google_places import ResolvedPlace, search_places
from backend.app.services.google_routes import compute_multi_stop_route
from backend.app.services.memory_service import get_user_settings
from backend.app.services.place_categories import google_place_type_for_category
from backend.app.trip_planner.road_trip_service import _decode_polyline
from backend.app.trip_planner.schemas import TripPreferences


RESERVE_BATTERY_PERCENT = 20.0
AVERAGE_DRIVE_METERS_PER_SECOND = 22.2
CHARGER_QUERY = "DC fast EV charging station"
CHARGER_RECOMMENDATION_LIMIT = 3


SearchAnchor = tuple[str, tuple[float, float]]


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


def _round_percent(value: float) -> float:
    return round(float(value), 1)


def _route_path(active_route: ActiveRoadTrip) -> list[tuple[float, float]]:
    try:
        return _decode_polyline(active_route.route.encodedPolyline)
    except (IndexError, TypeError, ValueError):
        return []


def _point_at_distance(
    path: list[tuple[float, float]],
    target_meters: float,
) -> tuple[float, float] | None:
    if not path:
        return None
    if len(path) == 1 or target_meters <= 0:
        return path[0]

    travelled = 0.0
    for index in range(1, len(path)):
        previous = path[index - 1]
        current = path[index]
        segment = _distance_meters(previous, current)
        if travelled + segment >= target_meters:
            if segment <= 0:
                return current
            ratio = max(0.0, min(1.0, (target_meters - travelled) / segment))
            return (
                previous[0] + (current[0] - previous[0]) * ratio,
                previous[1] + (current[1] - previous[1]) * ratio,
            )
        travelled += segment
    return path[-1]


def _charging_decision(
    *,
    current_battery: float,
    required_battery: float,
) -> tuple[bool, ChargingDecision]:
    remaining = current_battery - required_battery
    if current_battery < RESERVE_BATTERY_PERCENT:
        return True, "charge_before_departure"
    if remaining >= RESERVE_BATTERY_PERCENT:
        return False, "no_charging_required"
    if remaining >= 0:
        return True, "charge_near_destination"
    return True, "charge_during_trip"


def _trigger_distance_km(
    *,
    decision: ChargingDecision,
    current_battery: float,
    required_battery: float,
    trip_distance_km: float,
) -> float | None:
    if decision == "charge_before_departure":
        return 0.0
    if decision == "charge_near_destination":
        return round(trip_distance_km, 1)
    if decision != "charge_during_trip" or required_battery <= 0:
        return None

    usable_battery = max(0.0, current_battery - RESERVE_BATTERY_PERCENT)
    usage_per_km = required_battery / max(trip_distance_km, 0.1)
    return round(min(trip_distance_km, usable_battery / usage_per_km), 1)


def _search_anchors(
    *,
    decision: ChargingDecision,
    path: list[tuple[float, float]],
    trigger_distance_km: float | None,
) -> list[SearchAnchor]:
    if not path:
        return []
    anchors: list[SearchAnchor] = [("origin", path[0])]
    if decision == "charge_before_departure":
        return anchors
    if decision == "charge_near_destination":
        anchors.append(("destination", path[-1]))
        return anchors
    if decision == "charge_during_trip" and trigger_distance_km is not None:
        trigger_point = _point_at_distance(path, trigger_distance_km * 1000)
        if trigger_point is not None:
            anchors.append(("trigger", trigger_point))
    return anchors


def _place_to_charger(place: ResolvedPlace) -> RestStopPlace:
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


def _distance_label(
    *,
    decision: ChargingDecision,
    trigger_distance_km: float | None,
    distance_meters: int | None,
) -> str:
    if decision == "charge_before_departure":
        if distance_meters and distance_meters >= 1000:
            return f"{distance_meters / 1000:.1f} km from start"
        return "Near your starting point"
    if decision == "charge_near_destination":
        if distance_meters and distance_meters >= 1000:
            return f"{distance_meters / 1000:.1f} km from destination"
        return "Near your destination"
    if decision == "charge_during_trip" and trigger_distance_km is not None:
        return f"Around {trigger_distance_km:.1f} km from start"
    return ""


def _station_distance_label(
    *,
    anchor_kind: str,
    decision: ChargingDecision,
    trigger_distance_km: float | None,
    distance_meters: int | None,
) -> str:
    if anchor_kind == "origin":
        return "Near starting point"
    if anchor_kind == "destination":
        return "Near destination"
    if anchor_kind == "trigger" and trigger_distance_km is not None:
        return f"Around {trigger_distance_km:.1f} km from start"
    return _distance_label(
        decision=decision,
        trigger_distance_km=trigger_distance_km,
        distance_meters=distance_meters,
    )


def _place_key(place: ResolvedPlace) -> str:
    if place.place_id:
        return f"place:{place.place_id}"
    return f"text:{place.label.strip().lower()}|{place.address.strip().lower()}"


def _anchor_priority(anchor_kind: str, decision: ChargingDecision) -> int:
    if decision in {"charge_during_trip", "charge_near_destination"}:
        return 0 if anchor_kind != "origin" else 1
    return 0


async def _find_chargers(
    *,
    search_anchors: list[SearchAnchor],
    decision: ChargingDecision,
    trigger_distance_km: float | None,
    api_key: str,
) -> list[ChargingStationOption]:
    if not search_anchors:
        return []

    candidates: dict[str, tuple[ResolvedPlace, str, int, int]] = {}
    for anchor_kind, search_point in search_anchors:
        places = await search_places(
            text_query=CHARGER_QUERY,
            fallback_label="EV charging station",
            api_key=api_key,
            max_result_count=5,
            included_type=google_place_type_for_category(CHARGER_QUERY),
            strict_type_filtering=True,
            location_bias=search_point,
        )
        for place in places:
            if place.latitude is None or place.longitude is None:
                continue
            distance = int(
                _distance_meters(
                    search_point,
                    (float(place.latitude), float(place.longitude)),
                )
            )
            priority = _anchor_priority(anchor_kind, decision)
            key = _place_key(place)
            previous = candidates.get(key)
            if previous is None or (priority, distance) < (previous[2], previous[3]):
                candidates[key] = (place, anchor_kind, priority, distance)

    if not candidates:
        return []

    selected = sorted(
        candidates.values(),
        key=lambda candidate: (
            candidate[2],
            candidate[3],
            -(candidate[0].rating or 0),
            -(candidate[0].user_rating_count or 0),
            candidate[0].label,
        ),
    )[:CHARGER_RECOMMENDATION_LIMIT]
    stations: list[ChargingStationOption] = []
    for place, anchor_kind, _, distance in selected:
        stations.append(
            ChargingStationOption(
                place=_place_to_charger(place),
                distanceLabel=_station_distance_label(
                    anchor_kind=anchor_kind,
                    decision=decision,
                    trigger_distance_km=trigger_distance_km,
                    distance_meters=distance,
                ),
                estimatedDriveSeconds=max(60, round(distance / AVERAGE_DRIVE_METERS_PER_SECOND)),
                distanceMeters=distance,
            )
        )
    return stations


def _title(decision: ChargingDecision) -> str:
    if decision == "no_charging_required":
        return "No charge needed"
    if decision == "charge_before_departure":
        return "Charge before departure"
    if decision == "charge_near_destination":
        return "Charge near destination"
    return "Charge during trip"


def _message(
    *,
    decision: ChargingDecision,
    current_battery: float,
    required_battery: float,
    remaining_battery: float,
    trigger_distance_km: float | None,
    station_count: int,
) -> str:
    if decision == "no_charging_required":
        return (
            f"You can complete this trip with about {remaining_battery:g}% battery "
            "remaining."
        )
    if decision == "charge_before_departure":
        base = (
            f"Charge before starting. Current battery is {current_battery:g}%, "
            f"and the trip battery estimate is {required_battery:g}%."
        )
    elif decision == "charge_near_destination":
        base = (
            f"Trip is possible, but you will arrive with about {remaining_battery:g}% "
            "battery, below the 20% reserve."
        )
    else:
        base = (
            f"Recharge around {trigger_distance_km or 0:g} km into the drive. "
            "Predicted usage is higher than the current battery level."
        )

    if station_count:
        return f"{base} Choose one of the recommended charging stations below."
    return f"{base} I could not find matching EV charging stations nearby yet."


async def recommend_charging(
    request: ChargingRecommendationRequest,
    api_key: str,
) -> ChargingRecommendationResponse:
    active_route = get_active_road_trip(request.activeRouteId)
    if not active_route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This road-trip route is no longer active. Plan the road trip again.",
        )

    trip_distance_km = round(active_route.route.distanceMeters / 1000, 1)
    try:
        prediction = battery_model_service.predict_trip(distance_km=trip_distance_km)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    current_battery = _round_percent(float(get_user_settings().get("evBatteryLevel", 82)))
    required_battery = _round_percent(float(prediction.get("required_battery_percent") or 0))
    remaining_battery = _round_percent(current_battery - required_battery)
    charging_required, decision = _charging_decision(
        current_battery=current_battery,
        required_battery=required_battery,
    )
    trigger_distance_km = _trigger_distance_km(
        decision=decision,
        current_battery=current_battery,
        required_battery=required_battery,
        trip_distance_km=trip_distance_km,
    )

    stations: list[ChargingStationOption] = []
    path = _route_path(active_route)
    if charging_required:
        try:
            stations = await _find_chargers(
                search_anchors=_search_anchors(
                    decision=decision,
                    path=path,
                    trigger_distance_km=trigger_distance_km,
                ),
                decision=decision,
                trigger_distance_km=trigger_distance_km,
                api_key=api_key,
            )
        except HTTPException:
            stations = []
    first_station = stations[0] if stations else None
    place = first_station.place if first_station else None
    distance_meters = first_station.distanceMeters if first_station else None
    estimated_drive_seconds = first_station.estimatedDriveSeconds if first_station else None

    recommendation = ChargingRecommendation(
        id=str(uuid4()),
        chargingRequired=charging_required,
        decision=decision,
        title=_title(decision),
        message=_message(
            decision=decision,
            current_battery=current_battery,
            required_battery=required_battery,
            remaining_battery=remaining_battery,
            trigger_distance_km=trigger_distance_km,
            station_count=len(stations),
        ),
        currentBatteryPercent=current_battery,
        requiredBatteryPercent=required_battery,
        remainingBatteryPercent=remaining_battery,
        tripDistanceKm=trip_distance_km,
        triggerDistanceKm=trigger_distance_km,
        distanceLabel=_distance_label(
            decision=decision,
            trigger_distance_km=trigger_distance_km,
            distance_meters=distance_meters,
        ),
        place=place,
        stations=stations,
        estimatedDriveSeconds=estimated_drive_seconds,
        distanceMeters=distance_meters,
        primaryAction=NotificationAction(label="Add charger stop", type="add_charging_stop"),
        secondaryAction=NotificationAction(label="Not now", type="dismiss"),
    )
    return ChargingRecommendationResponse(recommendation=recommendation)


async def accept_charging_stop(
    request: ChargingStopAcceptRequest,
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
            label=f"Charge: {request.place.name}",
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
