"""
models/schemas.py
-----------------
Pydantic request / response schemas for the Mercedes Mobility Assistant.
All data models used across routers and services are defined here.
"""

from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Simulation State
# ---------------------------------------------------------------------------

class SimulationState(BaseModel):
    """Represents the full vehicle / trip simulation state."""

    speed_kmh: float = 0.0
    battery_soc: float = 100.0          # State of Charge: 0 – 100 %
    fatigue_level: str = "Low"          # Low | Medium | High
    cabin_temp_c: float = 22.0
    origin: str = ""
    destination: str = ""
    current_lat: float = 3.1390         # Default: Kuala Lumpur latitude
    current_lng: float = 101.6869       # Default: Kuala Lumpur longitude
    route_active: bool = False
    progress_percentage: float = 0.0


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Payload sent to the /agent/analyze endpoint."""

    state: SimulationState
    command: Optional[str] = None       # Optional natural-language command


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------

class WalletTopUpRequest(BaseModel):
    """Payload for topping up the mobility wallet."""

    amount: float


class WalletChargeRequest(BaseModel):
    """Payload for charging (deducting) from the mobility wallet."""

    amount: float
    reason: str


class FrequentStopRequest(BaseModel):
    """Payload for adding a frequent stop/location to memory."""

    origin: str
    destination: str
    location: str
    type: str
    reason: str

