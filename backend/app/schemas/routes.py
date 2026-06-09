from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    origin: str = Field(..., min_length=1, max_length=500)
    destination: str = Field(..., min_length=1, max_length=500)


class RouteSummary(BaseModel):
    durationText: str
    distanceText: str


class RouteResponse(BaseModel):
    duration: str
    distanceMeters: int
    encodedPolyline: str
    summary: RouteSummary
