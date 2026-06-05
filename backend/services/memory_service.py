"""
services/memory_service.py
--------------------------
Handles all reads and writes to the persistent JSON memory file.
Isolates file I/O from route handlers and business logic.
"""

import json
import logging
from typing import Any, Dict

from config.settings import MEMORY_FILE

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
