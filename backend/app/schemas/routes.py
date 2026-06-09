from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    origin: str = Field(default="", max_length=500)
    destination: str = Field(..., min_length=1, max_length=500)


class RouteSummary(BaseModel):
    durationText: str
    distanceText: str


class RouteWaypoint(BaseModel):
    role: str
    label: str
    address: str
    rating: float | None = None
    googleMapsUri: str = ""


class RouteResponse(BaseModel):
    duration: str
    distanceMeters: int
    encodedPolyline: str
    summary: RouteSummary
    waypoints: list[RouteWaypoint] = Field(default_factory=list)
