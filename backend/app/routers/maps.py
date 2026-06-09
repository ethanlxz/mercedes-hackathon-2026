from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.routes import RouteRequest, RouteResponse
from backend.app.services.google_routes import compute_route


router = APIRouter(prefix="/api", tags=["maps"])


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
    return await compute_route(
        origin=request.origin,
        destination=request.destination,
        api_key=settings.google_maps_server_key,
    )
