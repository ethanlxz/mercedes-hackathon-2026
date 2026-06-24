import operator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypedDict
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from backend.app.schemas.routes import RouteResponse
from backend.app.trip_planner.schemas import (
    NormalizedTripPlan,
    TripPreferences,
    TripWaypoint,
)


MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")
TAG_ALIASES = {
    "home": {"home", "my home", "house", "my house"},
    "work": {"work", "office", "my office", "workplace", "my workplace"},
}
CURRENT_LOCATION_ALIASES = {
    "current location",
    "my current location",
    "here",
    "from here",
    "my location",
}
FOOD_CATEGORY_TERMS = {
    "food", "breakfast", "lunch", "dinner", "supper", "halal", "japanese",
    "chinese", "mamak", "indian", "malay", "western", "italian", "restaurant",
    "cafe", "coffee",
}


class ParsedPreferences(BaseModel):
    avoidHighways: bool | None = None
    avoidTolls: bool | None = None
    fastestRoute: bool | None = None


class WaypointIntent(BaseModel):
    query: str
    purpose: str = "stop"
    resolution: Literal["specific", "category", "food_choice"] = "specific"
    selectionMode: Literal["auto", "nearest", "choice"] = "auto"
    nearbyReference: str = ""
    flexible: bool = False
    dwellMinutes: int = Field(default=0, ge=0, le=720)
    maxDriveMinutes: int | None = Field(default=None, ge=1, le=240)
    arriveBy: str | None = None
    departAfter: str | None = None


class ParsedTrip(BaseModel):
    origin: str = ""
    waypoints: list[WaypointIntent] = Field(default_factory=list)
    preferences: ParsedPreferences = Field(default_factory=ParsedPreferences)
    optimizeFlexible: bool = False
    departureTime: str | None = None
    clarificationQuestion: str | None = None


class Candidate(BaseModel):
    name: str
    address: str
    placeId: str = ""
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    userRatingCount: int | None = None
    googleMapsUri: str = ""
    driveSeconds: int | None = None
    distanceMeters: int | None = None


class ResolvedWaypoint(BaseModel):
    revision: int
    index: int
    intent: WaypointIntent
    referenceAddress: str
    candidates: list[Candidate] = Field(default_factory=list)
    selected: Candidate | None = None


class PlannerState(TypedDict, total=False):
    instruction: str
    original_instruction: str
    location_tags: dict[str, str]
    user_settings: dict[str, str]
    stored_preferences: dict[str, Any]
    requested_departure_time: str | None
    parsed: ParsedTrip
    revision: int
    resolved_origin: str
    preferences: TripPreferences
    resolved_waypoints: Annotated[list[ResolvedWaypoint], operator.add]
    pending_question: str | None
    normalized_plan: NormalizedTripPlan
    waypoints: list[TripWaypoint]
    route_response: RouteResponse
    departure_datetime: str
    planned_order: list[int]
    schedule_error: str | None


@dataclass(frozen=True)
class PlannerDependencies:
    google_maps_server_key: str
    deepseek_api_key: str
    deepseek_model: str
    deepseek_base_url: str


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _latest_resolved(state: PlannerState) -> dict[int, ResolvedWaypoint]:
    revision = state.get("revision", 0)
    latest: dict[int, ResolvedWaypoint] = {}
    for item in state.get("resolved_waypoints", []):
        if item.revision == revision:
            latest[item.index] = item
    return latest


def _tag_name(value: str) -> str | None:
    normalized = _clean(value).lower()
    for tag, aliases in TAG_ALIASES.items():
        if normalized in aliases:
            return tag
    return None
