from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.routes import RouteSummary, RouteWaypoint


class LocationTagsResponse(BaseModel):
    home: str = ""
    work: str = ""


class LocationTagRequest(BaseModel):
    tag: Literal["home", "work"]
    address: str = Field(..., min_length=1, max_length=500)


class UserSettingsResponse(BaseModel):
    currentLocation: str = ""


class CurrentLocationRequest(BaseModel):
    address: str = Field(default="", max_length=500)


class PlaceSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    origin: str = Field(default="", max_length=500)


class PlaceResult(BaseModel):
    name: str
    address: str
    rating: float | None = None
    googleMapsUri: str = ""


class PlaceSearchResponse(BaseModel):
    referenceOrigin: str
    results: list[PlaceResult] = Field(default_factory=list)


class TripPreferences(BaseModel):
    avoidHighways: bool = False
    avoidTolls: bool = False
    fastestRoute: bool = False
    timeWindows: dict[str, str] = Field(default_factory=dict)


class NormalizedTripPlan(BaseModel):
    origin: str
    stops: list[str] = Field(default_factory=list)
    destination: str
    preferences: TripPreferences = Field(default_factory=TripPreferences)


class TripWaypoint(RouteWaypoint):
    role: Literal["origin", "stop", "destination"]


class TripPlannerRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=3000)


class TripPlannerResponse(BaseModel):
    normalizedPlan: NormalizedTripPlan | None = None
    waypoints: list[TripWaypoint] = Field(default_factory=list)
    duration: str = ""
    distanceMeters: int = 0
    encodedPolyline: str = ""
    summary: RouteSummary = Field(
        default_factory=lambda: RouteSummary(durationText="--", distanceText="--")
    )
    clarificationRequired: bool = False
    clarificationMessage: str | None = None
    choiceRequired: bool = False
    choiceType: Literal["food", "location"] | None = None
    choiceQuery: str = ""
    message: str | None = None
    referenceOrigin: str = ""
