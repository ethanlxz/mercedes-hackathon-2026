import json
from pathlib import Path
from typing import Any

from backend.app.schemas.preferences import (
    PreferenceMemoryItem,
    PreferenceMemoryResponse,
    StopPreferenceFeedbackRequest,
)


ROOT_DIR = Path(__file__).resolve().parents[3]
MEMORY_FILE = ROOT_DIR / "backend" / "data" / "user_memory.json"

DEFAULT_CENTRAL_AGENT_MEMORY: dict[str, Any] = {
    "preferredStopTypes": {},
    "dislikedStopTypes": {},
    "lovedPlaces": {},
    "dismissedPlaces": {},
}

DEFAULT_MEMORY: dict[str, Any] = {
    "locationTags": {
        "home": "",
        "work": "",
    },
    "preferences": {
        "avoidHighways": False,
        "avoidTolls": False,
        "fastestRoute": False,
        "timeWindows": {},
    },
    "settings": {
        "currentLocation": "",
        "evBatteryLevel": 82,
    },
    "centralAgentMemory": DEFAULT_CENTRAL_AGENT_MEMORY,
}


def _merged_memory(memory: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_MEMORY))
    for key, value in memory.items():
        if key == "centralAgentMemory" and isinstance(value, dict):
            merged[key] = _normalized_central_agent_memory(value)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def _normalized_category(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized_counter_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, int] = {}
    for raw_key, raw_count in value.items():
        key = _normalized_category(str(raw_key))
        if not key:
            continue
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            normalized[key] = count
    return normalized


def _normalized_places(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for raw_key, raw_place in value.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        place = raw_place if isinstance(raw_place, dict) else {}
        normalized[key] = {
            "id": str(place.get("id") or ""),
            "placeId": str(place.get("placeId") or ""),
            "name": str(place.get("name") or ""),
            "address": str(place.get("address") or ""),
            "category": _normalized_category(str(place.get("category") or "")),
            "section": str(place.get("section") or ""),
        }
    return normalized


def _normalized_central_agent_memory(memory: dict[str, Any] | None = None) -> dict[str, Any]:
    memory = memory or {}
    return {
        "preferredStopTypes": _normalized_counter_map(memory.get("preferredStopTypes")),
        "dislikedStopTypes": _normalized_counter_map(memory.get("dislikedStopTypes")),
        "lovedPlaces": _normalized_places(memory.get("lovedPlaces")),
        "dismissedPlaces": _normalized_places(memory.get("dismissedPlaces")),
    }


def _place_memory_key(feedback: StopPreferenceFeedbackRequest) -> str:
    if feedback.placeId.strip():
        return f"place:{feedback.placeId.strip()}"
    if feedback.id.strip():
        return f"id:{feedback.id.strip()}"
    return f"text:{feedback.name.strip().lower()}|{feedback.address.strip().lower()}"


def _place_payload(feedback: StopPreferenceFeedbackRequest) -> dict[str, str]:
    return {
        "id": feedback.id.strip(),
        "placeId": feedback.placeId.strip(),
        "name": feedback.name.strip(),
        "address": feedback.address.strip(),
        "category": _normalized_category(feedback.category),
        "section": feedback.section,
    }


def _increment_category(counts: dict[str, int], category: str) -> None:
    if category:
        counts[category] = counts.get(category, 0) + 1


def _decrement_category(counts: dict[str, int], category: str) -> None:
    if not category or category not in counts:
        return
    next_count = counts[category] - 1
    if next_count > 0:
        counts[category] = next_count
    else:
        counts.pop(category, None)


def _preference_items(counts: dict[str, int]) -> list[PreferenceMemoryItem]:
    return [
        PreferenceMemoryItem(category=category, count=count)
        for category, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0].lower()),
        )
        if count > 0
    ]


def load_memory() -> dict[str, Any]:
    if not MEMORY_FILE.exists():
        return json.loads(json.dumps(DEFAULT_MEMORY))

    try:
        raw_memory = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULT_MEMORY))

    if not isinstance(raw_memory, dict):
        return json.loads(json.dumps(DEFAULT_MEMORY))

    return _merged_memory(raw_memory)


def save_memory(memory: dict[str, Any]) -> None:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(
        json.dumps(_merged_memory(memory), indent=2),
        encoding="utf-8",
    )


def get_location_tags() -> dict[str, str]:
    tags = load_memory()["locationTags"]
    return {
        "home": str(tags.get("home") or ""),
        "work": str(tags.get("work") or ""),
    }


def set_location_tag(tag: str, address: str) -> dict[str, str]:
    normalized_tag = tag.strip().lower()
    if normalized_tag not in {"home", "work"}:
        raise ValueError("Only home and work tags are supported.")

    memory = load_memory()
    memory["locationTags"][normalized_tag] = address.strip()
    save_memory(memory)
    return get_location_tags()


def get_user_settings() -> dict[str, Any]:
    settings = load_memory()["settings"]
    try:
        ev_battery_level = int(settings.get("evBatteryLevel", 82))
    except (TypeError, ValueError):
        ev_battery_level = 82
    return {
        "currentLocation": str(settings.get("currentLocation") or ""),
        "evBatteryLevel": min(max(ev_battery_level, 0), 100),
    }


def set_current_location(address: str) -> dict[str, Any]:
    memory = load_memory()
    memory["settings"]["currentLocation"] = address.strip()
    save_memory(memory)
    return get_user_settings()


def set_ev_battery_level(level: int) -> dict[str, Any]:
    memory = load_memory()
    memory["settings"]["evBatteryLevel"] = min(max(int(level), 0), 100)
    save_memory(memory)
    return get_user_settings()


def get_preferences() -> dict[str, Any]:
    return load_memory()["preferences"]


def update_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    memory = load_memory()
    memory["preferences"].update(preferences)
    save_memory(memory)
    return memory["preferences"]


def get_central_agent_memory() -> dict[str, Any]:
    return _normalized_central_agent_memory(load_memory().get("centralAgentMemory"))


def get_preference_memory_summary() -> PreferenceMemoryResponse:
    memory = get_central_agent_memory()
    return PreferenceMemoryResponse(
        preferredStopTypes=_preference_items(memory["preferredStopTypes"]),
        dislikedStopTypes=_preference_items(memory["dislikedStopTypes"]),
    )


def record_stop_preference_feedback(
    feedback: StopPreferenceFeedbackRequest,
) -> PreferenceMemoryResponse:
    memory = load_memory()
    central_memory = _normalized_central_agent_memory(memory.get("centralAgentMemory"))
    category = _normalized_category(feedback.category)
    if not category:
        return get_preference_memory_summary()

    key = _place_memory_key(feedback)
    place = _place_payload(feedback)
    place["category"] = category

    if feedback.action == "love":
        if key not in central_memory["lovedPlaces"]:
            dismissed = central_memory["dismissedPlaces"].pop(key, None)
            if dismissed:
                _decrement_category(
                    central_memory["dislikedStopTypes"],
                    _normalized_category(dismissed.get("category", "")),
                )
            central_memory["lovedPlaces"][key] = place
            _increment_category(central_memory["preferredStopTypes"], category)
    elif feedback.action == "unlove":
        loved = central_memory["lovedPlaces"].pop(key, None)
        if loved:
            _decrement_category(
                central_memory["preferredStopTypes"],
                _normalized_category(loved.get("category", category)),
            )
    else:
        if key not in central_memory["dismissedPlaces"]:
            loved = central_memory["lovedPlaces"].pop(key, None)
            if loved:
                _decrement_category(
                    central_memory["preferredStopTypes"],
                    _normalized_category(loved.get("category", "")),
                )
            central_memory["dismissedPlaces"][key] = place
            _increment_category(central_memory["dislikedStopTypes"], category)

    memory["centralAgentMemory"] = central_memory
    save_memory(memory)
    return PreferenceMemoryResponse(
        preferredStopTypes=_preference_items(central_memory["preferredStopTypes"]),
        dislikedStopTypes=_preference_items(central_memory["dislikedStopTypes"]),
    )


def reset_stop_preference_memory() -> PreferenceMemoryResponse:
    memory = load_memory()
    memory["centralAgentMemory"] = json.loads(json.dumps(DEFAULT_CENTRAL_AGENT_MEMORY))
    save_memory(memory)
    return get_preference_memory_summary()
