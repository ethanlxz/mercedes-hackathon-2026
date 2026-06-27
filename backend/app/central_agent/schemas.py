from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.routes import RouteResponse


Severity = Literal["warning", "high", "critical"]
ChargingDecision = Literal[
    "no_charging_required",
    "charge_before_departure",
    "charge_during_trip",
    "charge_near_destination",
]


class ActiveRoadTripRequest(BaseModel):
    origin: str = Field(..., min_length=1, max_length=500)
    destination: str = Field(..., min_length=1, max_length=500)
    route: RouteResponse


class ActiveRoadTripResponse(BaseModel):
    activeRouteId: str


class FatigueSnapshot(BaseModel):
    faceDetected: bool = False
    fatigueLevel: str = ""
    fatigueScore: int = Field(default=0, ge=0, le=100)
    symptoms: list[str] = Field(default_factory=list)
    symptomCounts: dict[str, int] = Field(default_factory=dict)
    alert: bool = False


class GeoLocation(BaseModel):
    latitude: float
    longitude: float


class RestStopPlace(BaseModel):
    name: str
    address: str
    placeId: str = ""
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    userRatingCount: int | None = None
    googleMapsUri: str = ""


class NotificationAction(BaseModel):
    label: str
    type: str


class AgentNotification(BaseModel):
    id: str
    source: Literal["fatigue_rest_stop"] = "fatigue_rest_stop"
    severity: Severity
    title: str
    message: str
    place: RestStopPlace
    estimatedDriveSeconds: int | None = None
    distanceMeters: int | None = None
    primaryAction: NotificationAction = Field(
        default_factory=lambda: NotificationAction(
            label="Rest there",
            type="add_rest_stop",
        )
    )
    secondaryAction: NotificationAction = Field(
        default_factory=lambda: NotificationAction(
            label="Not now",
            type="dismiss",
        )
    )


class FatigueRecommendationRequest(BaseModel):
    activeRouteId: str = Field(default="", max_length=100)
    fatigue: FatigueSnapshot
    location: GeoLocation | None = None


class FatigueRecommendationResponse(BaseModel):
    notification: AgentNotification | None = None


class RestStopAcceptRequest(BaseModel):
    activeRouteId: str = Field(..., min_length=1, max_length=100)
    notificationId: str = Field(default="", max_length=100)
    place: RestStopPlace


class ChargingRecommendationRequest(BaseModel):
    activeRouteId: str = Field(..., min_length=1, max_length=100)


class ChargingRecommendation(BaseModel):
    id: str
    source: Literal["charging_decision"] = "charging_decision"
    chargingRequired: bool
    decision: ChargingDecision
    title: str
    message: str
    currentBatteryPercent: float
    requiredBatteryPercent: float
    remainingBatteryPercent: float
    tripDistanceKm: float
    triggerDistanceKm: float | None = None
    place: RestStopPlace | None = None
    estimatedDriveSeconds: int | None = None
    distanceMeters: int | None = None
    primaryAction: NotificationAction = Field(
        default_factory=lambda: NotificationAction(
            label="Add charger stop",
            type="add_charging_stop",
        )
    )
    secondaryAction: NotificationAction = Field(
        default_factory=lambda: NotificationAction(
            label="Not now",
            type="dismiss",
        )
    )


class ChargingRecommendationResponse(BaseModel):
    recommendation: ChargingRecommendation | None = None


class ChargingStopAcceptRequest(BaseModel):
    activeRouteId: str = Field(..., min_length=1, max_length=100)
    notificationId: str = Field(default="", max_length=100)
    place: RestStopPlace
