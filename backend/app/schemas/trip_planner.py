from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.routes import RouteResponse, RouteSummary, RouteWaypoint


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
    placeId: str = ""
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    userRatingCount: int | None = None
    googleMapsUri: str = ""


class PlaceSearchResponse(BaseModel):
    referenceOrigin: str
    results: list[PlaceResult] = Field(default_factory=list)


class RoadTripPlannerRequest(BaseModel):
    origin: str = Field(..., min_length=1, max_length=500)
    destination: str = Field(..., min_length=1, max_length=500)


class RoadTripRecommendation(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    category: str
    section: Literal["route", "destination", "food"]
    rating: float | None = None
    userRatingCount: int | None = None
    googleMapsUri: str = ""
    explanation: str


class RoadTripPlannerResponse(BaseModel):
    route: RouteResponse
    routeRecommendations: list[RoadTripRecommendation] = Field(default_factory=list)
    destinationRecommendations: list[RoadTripRecommendation] = Field(default_factory=list)
    foodRecommendations: list[RoadTripRecommendation] = Field(default_factory=list)


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
    placeId: str = ""
    arrivalTime: str | None = None
    departureTime: str | None = None
    constraintStatus: Literal["none", "met", "missed"] = "none"


class TripPlannerRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=3000)
    threadId: str | None = Field(default=None, max_length=100)
    departureTime: datetime | None = None


class TripPlannerResumeRequest(BaseModel):
    threadId: str = Field(..., min_length=1, max_length=100)
    answer: str = Field(default="", max_length=1000)
    selectedPlace: PlaceResult | None = None


class TripChoiceRouteRequest(BaseModel):
    normalizedPlan: NormalizedTripPlan | None = None
    choiceReference: str = Field(default="", max_length=500)
    selectedPlace: PlaceResult


class TripPlannerResponse(BaseModel):
    status: Literal[
        "completed",
        "needs_clarification",
        "needs_choice",
        "failed",
    ] = "completed"
    threadId: str = ""
    prompt: str | None = None
    choices: list[PlaceResult] = Field(default_factory=list)
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
    choiceReference: str = ""
    message: str | None = None
    referenceOrigin: str = ""
