from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.routes import RouteResponse, RouteWaypoint
from backend.app.services.google_routes import compute_multi_stop_route
from backend.app.services.memory_service import (
    get_location_tags,
    get_user_settings,
)
from backend.app.trip_planner.road_trip_service import plan_road_trip
from backend.app.trip_planner.schemas import (
    RoadTripPlannerRequest,
    RoadTripPlannerResponse,
    TripChoiceRouteRequest,
    TripPlannerRequest,
    TripPlannerResumeRequest,
    TripPlannerResponse,
    TripPreferences,
)
from backend.app.trip_planner.service import plan_trip, resume_trip


router = APIRouter(prefix="/api", tags=["trip-planner"])


def _default_origin() -> str:
    current_location = get_user_settings().get("currentLocation", "").strip()
    if current_location:
        return current_location

    home = get_location_tags().get("home", "").strip()
    if home:
        return home

    return ""


def _origin_or_default(origin: str) -> str:
    return origin.strip() or _default_origin()


def _matches_reference(value: str, reference: str) -> bool:
    cleaned_value = " ".join(value.lower().split())
    cleaned_reference = " ".join(reference.lower().split())
    return bool(cleaned_reference) and (
        cleaned_reference in cleaned_value or cleaned_value in cleaned_reference
    )


def _choice_route_addresses(
    request: TripChoiceRouteRequest,
) -> tuple[str, list[str], str]:
    selected_address = request.selectedPlace.address.strip()
    if not selected_address:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected place is missing an address.",
        )

    plan = request.normalizedPlan
    if not plan:
        origin = _origin_or_default("")
        if not origin:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Set Current Location in Settings or save your Home address first.",
            )
        return origin, [], selected_address

    sequence = [
        plan.origin.strip(),
        *[stop.strip() for stop in plan.stops if stop.strip()],
        plan.destination.strip(),
    ]
    sequence = [address for address in sequence if address]
    if not sequence:
        origin = _origin_or_default("")
        return origin, [], selected_address

    insert_after = len(sequence) - 1
    if request.choiceReference.strip():
        for index, address in enumerate(sequence):
            if _matches_reference(address, request.choiceReference):
                insert_after = index

    sequence.insert(insert_after + 1, selected_address)
    return sequence[0], sequence[1:-1], sequence[-1]


@router.post("/trip-planner/choice-route", response_model=RouteResponse)
async def trip_choice_route(
    request: TripChoiceRouteRequest,
    settings: Settings = Depends(get_settings),
) -> RouteResponse:
    origin, stops, destination = _choice_route_addresses(request)
    response = await compute_multi_stop_route(
        origin=origin,
        stops=stops,
        destination=destination,
        preferences=request.normalizedPlan.preferences
        if request.normalizedPlan
        else TripPreferences(),
        api_key=settings.google_maps_server_key,
        optimize_waypoints=False,
    )
    response.waypoints = [
        RouteWaypoint(role="origin", label="Start", address=origin),
        *[
            RouteWaypoint(role="stop", label=f"Stop {index + 1}", address=stop)
            for index, stop in enumerate(stops)
        ],
        RouteWaypoint(
            role="destination",
            label=request.selectedPlace.name or "Destination",
            address=destination,
            rating=request.selectedPlace.rating,
            userRatingCount=request.selectedPlace.userRatingCount,
            googleMapsUri=request.selectedPlace.googleMapsUri,
        ),
    ]
    return response


@router.post("/road-trip-planner", response_model=RoadTripPlannerResponse)
async def road_trip_planner(
    request: RoadTripPlannerRequest,
    settings: Settings = Depends(get_settings),
) -> RoadTripPlannerResponse:
    return await plan_road_trip(
        origin=request.origin,
        destination=request.destination,
        google_maps_server_key=settings.google_maps_server_key,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_model=settings.deepseek_model,
        deepseek_base_url=settings.deepseek_base_url,
    )


@router.post("/trip-planner", response_model=TripPlannerResponse)
async def trip_planner(
    request: TripPlannerRequest,
    settings: Settings = Depends(get_settings),
) -> TripPlannerResponse:
    return await plan_trip(
        instruction=request.instruction,
        location_tags=get_location_tags(),
        user_settings=get_user_settings(),
        google_maps_server_key=settings.google_maps_server_key,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_model=settings.deepseek_model,
        deepseek_base_url=settings.deepseek_base_url,
        thread_id=request.threadId,
        departure_time=request.departureTime,
    )


@router.post("/trip-planner/resume", response_model=TripPlannerResponse)
async def resume_trip_planner(
    request: TripPlannerResumeRequest,
    settings: Settings = Depends(get_settings),
) -> TripPlannerResponse:
    if not request.answer.strip() and request.selectedPlace is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide a clarification answer or select a place.",
        )
    return await resume_trip(
        thread_id=request.threadId,
        answer=request.answer,
        selected_place=request.selectedPlace,
        google_maps_server_key=settings.google_maps_server_key,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_model=settings.deepseek_model,
        deepseek_base_url=settings.deepseek_base_url,
    )
