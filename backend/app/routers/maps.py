from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.routes import RouteRequest, RouteResponse
from backend.app.trip_planner.schemas import (
    CurrentLocationRequest,
    EVBatteryLevelRequest,
    LocationTagRequest,
    LocationTagsResponse,
    PlaceResult,
    PlaceSearchRequest,
    PlaceSearchResponse,
    UserSettingsResponse,
)
from backend.app.services.google_places import search_place, search_places
from backend.app.services.google_routes import compute_route
from backend.app.services.location_context import origin_or_default
from backend.app.services.memory_service import (
    get_preference_memory_summary,
    get_location_tags,
    get_user_settings,
    set_ev_battery_level,
    set_current_location,
    set_location_tag,
)
from backend.app.services.place_categories import google_place_type_for_category


router = APIRouter(prefix="/api", tags=["maps"])


def _place_type_filter(query: str) -> str | None:
    return google_place_type_for_category(query)


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
    origin = origin_or_default(request.origin, get_location_tags(), get_user_settings())
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
    return UserSettingsResponse(
        **get_user_settings(),
        preferenceMemory=get_preference_memory_summary(),
    )


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


@router.post("/settings/ev-battery-level", response_model=UserSettingsResponse)
def save_ev_battery_level(request: EVBatteryLevelRequest) -> UserSettingsResponse:
    return UserSettingsResponse(**set_ev_battery_level(request.level))


@router.post("/places/search-nearby", response_model=PlaceSearchResponse)
async def search_nearby_places(
    request: PlaceSearchRequest,
    settings: Settings = Depends(get_settings),
) -> PlaceSearchResponse:
    origin = origin_or_default(request.origin, get_location_tags(), get_user_settings())
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set Current Location in Settings or save your Home address first.",
        )

    query = request.query.strip()
    included_type = _place_type_filter(query)
    places = await search_places(
        text_query=f"{query} near {origin}",
        fallback_label=query,
        api_key=settings.google_maps_server_key,
        max_result_count=3,
        included_type=included_type,
        strict_type_filtering=bool(included_type),
    )
    return PlaceSearchResponse(
        referenceOrigin=origin,
        results=[
            PlaceResult(
                name=place.label,
                address=place.address,
                placeId=place.place_id,
                latitude=place.latitude,
                longitude=place.longitude,
                rating=place.rating,
                userRatingCount=place.user_rating_count,
                googleMapsUri=place.google_maps_uri,
            )
            for place in places
        ],
    )
