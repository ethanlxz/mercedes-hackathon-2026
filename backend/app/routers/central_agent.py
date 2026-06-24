from fastapi import APIRouter, Depends

from backend.app.central_agent.graph import accept_rest_stop, recommend_rest_stop
from backend.app.central_agent.schemas import (
    ActiveRoadTripRequest,
    ActiveRoadTripResponse,
    FatigueRecommendationRequest,
    FatigueRecommendationResponse,
    RestStopAcceptRequest,
)
from backend.app.central_agent.state import store_active_road_trip
from backend.app.core.config import Settings, get_settings
from backend.app.schemas.routes import RouteResponse


router = APIRouter(prefix="/api/central-agent", tags=["central-agent"])


@router.post("/active-road-trip", response_model=ActiveRoadTripResponse)
async def active_road_trip(request: ActiveRoadTripRequest) -> ActiveRoadTripResponse:
    active = store_active_road_trip(
        origin=request.origin,
        destination=request.destination,
        route=request.route,
    )
    return ActiveRoadTripResponse(activeRouteId=active.route_id)


@router.post("/fatigue/recommendation", response_model=FatigueRecommendationResponse)
async def fatigue_recommendation(
    request: FatigueRecommendationRequest,
    settings: Settings = Depends(get_settings),
) -> FatigueRecommendationResponse:
    return await recommend_rest_stop(request, settings.google_maps_server_key)


@router.post("/rest-stop/accept", response_model=RouteResponse)
async def rest_stop_accept(
    request: RestStopAcceptRequest,
    settings: Settings = Depends(get_settings),
) -> RouteResponse:
    return await accept_rest_stop(request, settings.google_maps_server_key)

