"""
services/agent_service.py
-------------------------
Core business logic for the MBUX AI agent.
Analyses vehicle state and optional voice/text commands to produce
proactive recommendations and a chat response.

Completely decoupled from FastAPI — no Request/Response objects here,
making this layer independently testable.
"""

from typing import Any, Dict, List, Optional, Tuple

from models.schemas import SimulationState
from services.memory_service import load_memory


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_agent_analysis(
    state: SimulationState,
    command: Optional[str],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Analyse the current simulation state and an optional user command.

    Returns:
        (chat_response, recommendations)  – both ready for JSON serialisation.
    """
    recommendations: List[Dict[str, Any]] = []
    chat_response: str = ""
    memory = load_memory()

    # ------------------------------------------------------------------
    # 1. Proactive Safety Checks (Attention Assist)
    # ------------------------------------------------------------------
    if state.fatigue_level == "High":
        recommendations.append({
            "type": "rest_stop",
            "location": "Nearest R&R (Tapah / Ipoh)",
            "reason": (
                "CRITICAL fatigue detected. Attention Assist recommends "
                "taking an immediate break at the nearest rest area."
            ),
            "confidence": 0.99,
        })
    elif state.fatigue_level == "Medium":
        recommendations.append({
            "type": "rest_stop",
            "location": "Starbucks Ipoh",
            "reason": (
                "Fatigue warning. Based on your memory, you usually stop "
                "at Starbucks Ipoh for a break around this time."
            ),
            "confidence": 0.85,
        })

    # ------------------------------------------------------------------
    # 2. Battery State of Charge (SoC) Warnings
    # ------------------------------------------------------------------
    if state.battery_soc < 20.0:
        recommendations.append({
            "type": "charging",
            "location": "Shell Recharge Tapah",
            "reason": (
                f"Critical Battery ({state.battery_soc:.0f}%). "
                "High-speed charger at Shell Recharge Tapah is on your route."
            ),
            "confidence": 0.95,
        })
    elif state.battery_soc < 35.0 and len(recommendations) == 0:
        recommendations.append({
            "type": "charging",
            "location": "Caltex EV Charge",
            "reason": (
                f"Low Battery ({state.battery_soc:.0f}%). "
                "It is recommended to schedule a charging stop soon."
            ),
            "confidence": 0.78,
        })

    # ------------------------------------------------------------------
    # 3. Cabin Environment & Climate Checks
    # ------------------------------------------------------------------
    if state.cabin_temp_c > 24.5:
        recommendations.append({
            "type": "climate",
            "location": "Cabin A/C System",
            "reason": (
                f"Cabin temp is warm ({state.cabin_temp_c:.1f}°C). "
                "Adjusting to 21°C helps maintain driver alertness."
            ),
            "confidence": 0.70,
        })

    # ------------------------------------------------------------------
    # 4. Command Parsing (Mimicking NLP Assistant)
    # ------------------------------------------------------------------
    if command:
        chat_response, recommendations = _parse_command(
            command, state, memory, recommendations
        )

    # ------------------------------------------------------------------
    # 5. Post-process: sort by confidence, de-duplicate by (type, location)
    # ------------------------------------------------------------------
    recommendations = _deduplicate(
        sorted(recommendations, key=lambda x: x["confidence"], reverse=True)
    )

    return (
        chat_response or "MBUX driving analysis complete. System operations nominal.",
        recommendations,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_command(
    command: str,
    state: SimulationState,
    memory: Dict[str, Any],
    recommendations: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse a natural-language command and append the relevant recommendation."""

    cmd_lower = command.lower().strip()
    chat_response = ""

    # Scenario A: Plan Trip (KL -> Penang)
    if "plan" in cmd_lower and (
        "kl" in cmd_lower or "kuala lumpur" in cmd_lower
    ) and "penang" in cmd_lower:
        frequent_trip = next(
            (
                t for t in memory["frequent_trips"]
                if t["origin"].lower() in ["kuala lumpur", "kl"]
                and t["destination"].lower() == "penang"
            ),
            None,
        )
        chat_response = (
            "Route planned from Kuala Lumpur to Penang (approx 350 km). "
            "Loaded frequent stops from long-term memory."
        )
        if frequent_trip:
            for stop in frequent_trip["stops"]:
                recommendations.append({
                    "type": stop["type"],
                    "location": stop["location"],
                    "reason": (
                        f"Personalized stop: {stop['reason']} "
                        "loaded from your long-term memory."
                    ),
                    "confidence": stop["confidence"],
                })
        else:
            recommendations.append({
                "type": "rest_stop",
                "location": "Tapah R&R",
                "reason": "Standard recommended rest point on KL-Penang highway.",
                "confidence": 0.80,
            })

    # Scenario B: Next stop recommendation
    elif "stop next" in cmd_lower or "where should i stop" in cmd_lower:
        if state.route_active:
            progress = state.progress_percentage
            if progress < 40:
                chat_response = (
                    "You are currently 30% into the trip. "
                    "Shell Recharge Tapah is approaching in 45 km."
                )
                recommendations.append({
                    "type": "charging",
                    "location": "Shell Recharge Tapah",
                    "reason": "Usual high-speed charging stop on this route.",
                    "confidence": 0.88,
                })
            elif progress < 70:
                chat_response = (
                    "You are approaching the mid-point. "
                    "Starbucks Ipoh is in 25 km."
                )
                recommendations.append({
                    "type": "rest_stop",
                    "location": "Starbucks Ipoh",
                    "reason": (
                        "Your favorite coffee stop. Highly recommended "
                        "to grab a coffee for the remaining drive."
                    ),
                    "confidence": 0.95,
                })
            else:
                chat_response = (
                    "You are close to Penang. No major stops needed, "
                    "but digital extra parking booking is available."
                )
                recommendations.append({
                    "type": "digital_extra",
                    "location": "Penang Parking Hub",
                    "reason": "Reserve a parking space in advance for convenience.",
                    "confidence": 0.70,
                })
        else:
            chat_response = (
                "No active route found. Please set a destination first "
                "(e.g. Plan my trip from KL to Penang)."
            )

    # Scenario C: Battery / charge / range query
    elif "battery" in cmd_lower or "charge" in cmd_lower or "range" in cmd_lower:
        est_range = state.battery_soc * 4.0  # 4 km per 1 % SoC
        chat_response = (
            f"Battery State of Charge is {state.battery_soc:.0f}%. "
            f"Estimated remaining range: {est_range:.0f} km."
        )
        if state.battery_soc < 30.0:
            recommendations.append({
                "type": "charging",
                "location": "EV Charger Tapah",
                "reason": (
                    "Battery is below 30%. "
                    "Recommend routing to the next available DC charger."
                ),
                "confidence": 0.90,
            })
        else:
            chat_response += " Range is sufficient for immediate driving."

    # Scenario D: Temperature / climate adjustment
    elif "temp" in cmd_lower or "climate" in cmd_lower or "cool" in cmd_lower:
        chat_response = "Adjusting cabin temperature settings."
        recommendations.append({
            "type": "climate",
            "location": "Climate Control",
            "reason": (
                "Setting cabin temperature to preferred 21.0°C "
                "based on profile preferences."
            ),
            "confidence": 0.95,
        })

    # Scenario E: Music / audio
    elif "music" in cmd_lower or "play" in cmd_lower or "sound" in cmd_lower:
        fav_genre = memory["profile"]["preferences"]["favorite_music_genre"]
        chat_response = f"Streaming '{fav_genre}' channel via Mercedes Digital Extras."
        recommendations.append({
            "type": "digital_extra",
            "location": f"MBUX Sound: {fav_genre}",
            "reason": f"Enhance drive ambiance with your favorite genre: {fav_genre}.",
            "confidence": 0.90,
        })

    # Fallback
    else:
        chat_response = (
            f"I received your command: '{command}'. "
            "Analyzing drive parameters..."
        )
        recommendations.append({
            "type": "digital_extra",
            "location": "MBUX Assistant",
            "reason": (
                "Active query processed. Let me know if you want to "
                "plan routes or modify climate settings."
            ),
            "confidence": 0.60,
        })

    return chat_response, recommendations


def _deduplicate(
    recommendations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remove duplicate recommendations with the same (type, location) key."""
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for rec in recommendations:
        key = (rec["type"], rec.get("location", ""))
        if key not in seen:
            seen.add(key)
            unique.append(rec)
    return unique
