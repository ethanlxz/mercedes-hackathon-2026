"""
services/memory_service.py
--------------------------
Handles all reads and writes to the persistent JSON memory file.
Isolates file I/O from route handlers and business logic.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.config.settings import MEMORY_FILE

logger = logging.getLogger("mercedes-assistant")

# ---------------------------------------------------------------------------
# Default in-memory fallback (used when the file is missing or corrupt)
# ---------------------------------------------------------------------------

_DEFAULT_MEMORY: Dict[str, Any] = {
    "profile": {
        "name": "Ethan",
        "wallet_balance": 150.0,
        "preferences": {
            "cabin_temp_c": 21.0,
            "favorite_music_genre": "Lo-Fi Beats",
        },
    },
    "frequent_trips": [
        {
            "origin": "Kuala Lumpur",
            "destination": "Penang",
            "stops": [
                {
                    "location": "Starbucks Ipoh",
                    "type": "rest_stop",
                    "reason": "Frequent coffee stop on KL -> Penang route",
                    "confidence": 0.95,
                },
                {
                    "location": "Shell Recharge Tapah",
                    "type": "charging",
                    "reason": "Usual high-speed EV charging point",
                    "confidence": 0.88,
                },
            ],
        }
    ],
    "trip_history": [],
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def load_memory() -> Dict[str, Any]:
    """
    Load user memory from the persistent JSON file.
    Returns the default memory structure if the file is missing or corrupt.
    """
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("memory.json not found — using default memory.")
    except Exception as e:
        logger.error(f"Error loading memory: {e}")

    return _DEFAULT_MEMORY.copy()


def save_memory(data: Dict[str, Any]) -> None:
    """
    Persist user memory to the JSON file.
    Logs an error silently on failure so the app keeps running.
    """
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving memory: {e}")


def append_trip_to_history(
    route: str,
    stops_made: List[str],
    energy_consumed_kwh: float,
) -> None:
    """
    Append a completed trip record to the persistent trip_history array.

    Args:
        route: Human-readable route description (e.g. "KL -> Penang").
        stops_made: List of stop location names visited.
        energy_consumed_kwh: Total energy consumed in kWh.
    """
    memory = load_memory()
    history = memory.setdefault("trip_history", [])
    history.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "route": route,
        "stops_made": stops_made,
        "energy_consumed_kwh": round(energy_consumed_kwh, 1),
    })
    save_memory(memory)
    logger.info("Trip recorded in memory: %s", route)


def update_preferences(
    cabin_temp_c: Optional[float] = None,
    favorite_music_genre: Optional[str] = None,
) -> None:
    """
    Update driver preferences in the persistent memory file.

    Only the provided (non-None) fields are overwritten; the rest are kept.
    """
    memory = load_memory()
    prefs = memory.setdefault("profile", {}).setdefault("preferences", {})

    if cabin_temp_c is not None:
        prefs["cabin_temp_c"] = cabin_temp_c
    if favorite_music_genre is not None:
        prefs["favorite_music_genre"] = favorite_music_genre

    save_memory(memory)
    logger.info("Driver preferences updated in memory.")


def add_frequent_stop(
    origin: str,
    destination: str,
    location: str,
    stop_type: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Add a frequent stop/location to persistent memory.
    """
    memory = load_memory()
    trips = memory.setdefault("frequent_trips", [])
    
    # Try to find a matching trip
    matching_trip = None
    for trip in trips:
        if (
            trip.get("origin", "").strip().lower() == origin.strip().lower()
            and trip.get("destination", "").strip().lower() == destination.strip().lower()
        ):
            matching_trip = trip
            break
            
    if not matching_trip:
        matching_trip = {
            "origin": origin,
            "destination": destination,
            "stops": []
        }
        trips.append(matching_trip)
        
    stops = matching_trip.setdefault("stops", [])
    
    # Check if stop already exists
    existing_stop = None
    for s in stops:
        if s.get("location", "").strip().lower() == location.strip().lower():
            existing_stop = s
            break
            
    new_stop = {
        "location": location,
        "type": stop_type,
        "reason": reason,
        "confidence": 0.90
    }
    
    if existing_stop:
        existing_stop.update(new_stop)
    else:
        stops.append(new_stop)
        
    save_memory(memory)
    logger.info(f"Saved frequent stop '{location}' on route '{origin} -> {destination}' to memory.")
    return new_stop

