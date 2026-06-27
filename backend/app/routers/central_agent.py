from fastapi import APIRouter, Depends

from backend.app.central_agent.graph import (
    accept_rest_stop,
    recommend_rest_stop,
    record_preference_feedback,
    reset_preference_memory,
)
from backend.app.central_agent.schemas import (
    ActiveRoadTripRequest,
    ActiveRoadTripResponse,
    FatigueRecommendationRequest,
    FatigueRecommendationResponse,
    RestStopAcceptRequest,
)
from backend.app.central_agent.state import store_active_road_trip
from backend.app.core.config import Settings, get_settings
from backend.app.schemas.preferences import (
    PreferenceMemoryResponse,
    StopPreferenceFeedbackRequest,
)
from backend.app.schemas.routes import RouteResponse
from backend.app.services.memory_service import get_preference_memory_summary


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


@router.get("/preferences", response_model=PreferenceMemoryResponse)
async def central_agent_preferences() -> PreferenceMemoryResponse:
    return get_preference_memory_summary()


@router.post("/preferences/feedback", response_model=PreferenceMemoryResponse)
async def central_agent_preference_feedback(
    request: StopPreferenceFeedbackRequest,
) -> PreferenceMemoryResponse:
    return await record_preference_feedback(request)


@router.delete("/preferences", response_model=PreferenceMemoryResponse)
async def central_agent_preference_reset() -> PreferenceMemoryResponse:
    return await reset_preference_memory()
