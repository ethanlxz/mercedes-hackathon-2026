from typing import Literal

from pydantic import BaseModel, Field


PreferenceAction = Literal["love", "unlove", "close"]
PreferenceSection = Literal["route", "destination", "food", "rest"]


class PreferenceMemoryItem(BaseModel):
    category: str
    count: int = Field(default=0, ge=0)


class PreferenceMemoryResponse(BaseModel):
    preferredStopTypes: list[PreferenceMemoryItem] = Field(default_factory=list)
    dislikedStopTypes: list[PreferenceMemoryItem] = Field(default_factory=list)


class StopPreferenceFeedbackRequest(BaseModel):
    action: PreferenceAction
    id: str = Field(default="", max_length=240)
    placeId: str = Field(default="", max_length=240)
    name: str = Field(default="", max_length=500)
    address: str = Field(default="", max_length=800)
    category: str = Field(..., min_length=1, max_length=120)
    section: PreferenceSection
