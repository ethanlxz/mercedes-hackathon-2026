import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[3]
MEMORY_FILE = ROOT_DIR / "backend" / "data" / "user_memory.json"

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
    },
}


def _merged_memory(memory: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_MEMORY))
    for key, value in memory.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


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


def get_user_settings() -> dict[str, str]:
    settings = load_memory()["settings"]
    return {
        "currentLocation": str(settings.get("currentLocation") or ""),
    }


def set_current_location(address: str) -> dict[str, str]:
    memory = load_memory()
    memory["settings"]["currentLocation"] = address.strip()
    save_memory(memory)
    return get_user_settings()


def get_preferences() -> dict[str, Any]:
    return load_memory()["preferences"]


def update_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    memory = load_memory()
    memory["preferences"].update(preferences)
    save_memory(memory)
    return memory["preferences"]
