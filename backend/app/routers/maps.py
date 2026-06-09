from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.routes import RouteRequest, RouteResponse
from backend.app.schemas.trip_planner import (
    CurrentLocationRequest,
    LocationTagRequest,
    LocationTagsResponse,
    TripPlannerRequest,
    TripPlannerResponse,
    UserSettingsResponse,
)
from backend.app.services.google_places import search_place
from backend.app.services.google_routes import compute_route
from backend.app.services.memory_service import (
    get_location_tags,
    get_user_settings,
    set_current_location,
    set_location_tag,
)
from backend.app.services.trip_planner_service import plan_trip


router = APIRouter(prefix="/api", tags=["maps"])


def _default_origin() -> str:
    current_location = get_user_settings().get("currentLocation", "").strip()
    if current_location:
        return current_location

    home = get_location_tags().get("home", "").strip()
    if home:
        return home

    return ""


@router.get("/maps/config")
def maps_config(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    if not settings.google_maps_browser_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_MAPS_BROWSER_KEY is missing from .env.",
        )

    return {"browserKey": settings.google_maps_browser_key}


@router.post("/routes", response_model=RouteResponse)
async def routes(
    request: RouteRequest,
    settings: Settings = Depends(get_settings),
) -> RouteResponse:
    origin = request.origin.strip() or _default_origin()
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter an origin, or save Current Location or Home first.",
        )

    return await compute_route(
        origin=origin,
        destination=request.destination,
        api_key=settings.google_maps_server_key,
    )


@router.get("/location-tags", response_model=LocationTagsResponse)
def location_tags() -> LocationTagsResponse:
    return LocationTagsResponse(**get_location_tags())


@router.post("/location-tags", response_model=LocationTagsResponse)
def save_location_tag(request: LocationTagRequest) -> LocationTagsResponse:
    try:
        tags = set_location_tag(request.tag, request.address)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return LocationTagsResponse(**tags)


@router.get("/settings", response_model=UserSettingsResponse)
def user_settings() -> UserSettingsResponse:
    return UserSettingsResponse(**get_user_settings())


@router.post("/settings/current-location", response_model=UserSettingsResponse)
async def save_current_location(
    request: CurrentLocationRequest,
    settings: Settings = Depends(get_settings),
) -> UserSettingsResponse:
    address = request.address.strip()
    if not address:
        return UserSettingsResponse(**set_current_location(""))

    place = await search_place(
        text_query=address,
        fallback_label=address,
        api_key=settings.google_maps_server_key,
    )
    if not place:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="I couldn't resolve that current location. Try a clearer address or landmark.",
        )

    return UserSettingsResponse(**set_current_location(place.address))


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
    )
