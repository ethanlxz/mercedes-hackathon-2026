import math

import httpx
from fastapi import HTTPException, status

from backend.app.schemas.routes import RouteResponse, RouteSummary, RouteWaypoint
from backend.app.schemas.trip_planner import TripPreferences
from backend.app.services.google_places import search_place


ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
MULTI_STOP_FIELD_MASK = (
    "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,"
    "routes.optimizedIntermediateWaypointIndex"
)


def _format_duration(duration: str) -> str:
    try:
        seconds = int(duration.rstrip("s"))
    except (TypeError, ValueError):
        return duration or "Unknown"

    minutes = max(1, math.ceil(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"

    hours, remaining_minutes = divmod(minutes, 60)
    if remaining_minutes == 0:
        return f"{hours} hr"
    return f"{hours} hr {remaining_minutes} min"


def _format_distance(distance_meters: int) -> str:
    if distance_meters < 1000:
        return f"{distance_meters} m"

    kilometers = distance_meters / 1000
    return f"{kilometers:.1f} km"


def _google_error_message(payload: dict, fallback: str) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        return error.get("message") or fallback
    return fallback


async def _route_waypoint(
    role: str,
    label: str,
    address: str,
    api_key: str,
) -> RouteWaypoint:
    try:
        place = await search_place(
            text_query=address,
            fallback_label=label,
            api_key=api_key,
        )
    except HTTPException:
        place = None

    if not place:
        return RouteWaypoint(role=role, label=label, address=address)

    return RouteWaypoint(
        role=role,
        label=place.label or label,
        address=place.address or address,
        rating=place.rating,
        googleMapsUri=place.google_maps_uri,
    )


async def compute_route(origin: str, destination: str, api_key: str) -> RouteResponse:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_MAPS_SERVER_KEY is missing from .env.",
        )

    origin = origin.strip()
    destination = destination.strip()
    if not origin or not destination:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Origin and destination are required.",
        )

    request_body = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "DRIVE",
        "polylineEncoding": "ENCODED_POLYLINE",
        "polylineQuality": "HIGH_QUALITY",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(ROUTES_URL, json=request_body, headers=headers)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Routes API timed out. Please try again.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Google Routes API.",
        ) from exc

    payload = response.json() if response.content else {}
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_google_error_message(payload, "Google Routes API rejected the request."),
        )

    routes = payload.get("routes") or []
    if not routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No route was found for those locations.",
        )

    route = routes[0]
    encoded_polyline = (route.get("polyline") or {}).get("encodedPolyline")
    distance_meters = route.get("distanceMeters")
    duration = route.get("duration")

    if not encoded_polyline or distance_meters is None or not duration:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Routes API returned an incomplete route.",
        )

    return RouteResponse(
        duration=duration,
        distanceMeters=distance_meters,
        encodedPolyline=encoded_polyline,
        summary=RouteSummary(
            durationText=_format_duration(duration),
            distanceText=_format_distance(distance_meters),
        ),
        waypoints=[
            await _route_waypoint("origin", origin, origin, api_key),
            await _route_waypoint("destination", destination, destination, api_key),
        ],
    )


async def compute_multi_stop_route(
    origin: str,
    stops: list[str],
    destination: str,
    preferences: TripPreferences,
    api_key: str,
    optimize_waypoints: bool = False,
) -> RouteResponse:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_MAPS_SERVER_KEY is missing from .env.",
        )

    origin = origin.strip()
    destination = destination.strip()
    cleaned_stops = [stop.strip() for stop in stops if stop.strip()]
    if not origin or not destination:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Origin and destination are required.",
        )

    request_body = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "polylineEncoding": "ENCODED_POLYLINE",
        "polylineQuality": "HIGH_QUALITY",
        "routeModifiers": {
            "avoidHighways": preferences.avoidHighways,
            "avoidTolls": preferences.avoidTolls,
        },
    }
    if cleaned_stops:
        request_body["intermediates"] = [
            {"address": stop} for stop in cleaned_stops
        ]
    if optimize_waypoints and cleaned_stops:
        request_body["optimizeWaypointOrder"] = True

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": MULTI_STOP_FIELD_MASK,
    }

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(ROUTES_URL, json=request_body, headers=headers)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Routes API timed out. Please try again.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Google Routes API.",
        ) from exc

    payload = response.json() if response.content else {}
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_google_error_message(payload, "Google Routes API rejected the request."),
        )

    routes = payload.get("routes") or []
    if not routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No route was found for those locations.",
        )

    route = routes[0]
    encoded_polyline = (route.get("polyline") or {}).get("encodedPolyline")
    distance_meters = route.get("distanceMeters")
    duration = route.get("duration")

    if not encoded_polyline or distance_meters is None or not duration:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Routes API returned an incomplete route.",
        )

    return RouteResponse(
        duration=duration,
        distanceMeters=distance_meters,
        encodedPolyline=encoded_polyline,
        summary=RouteSummary(
            durationText=_format_duration(duration),
            distanceText=_format_distance(distance_meters),
        ),
    )
