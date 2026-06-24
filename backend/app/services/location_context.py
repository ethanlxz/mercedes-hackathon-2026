from typing import Any


DEFAULT_ORIGIN_ERROR = "Please set Current Location in Settings or save your Home address first."


def clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def default_origin(
    location_tags: dict[str, str],
    user_settings: dict[str, Any],
) -> tuple[str, str | None]:
    current = clean_text(str(user_settings.get("currentLocation") or ""))
    if current:
        return current, None

    home = clean_text(str(location_tags.get("home") or ""))
    if home:
        return home, None

    return "", DEFAULT_ORIGIN_ERROR


def origin_or_default(
    origin: str,
    location_tags: dict[str, str],
    user_settings: dict[str, Any],
) -> str:
    cleaned_origin = origin.strip()
    if cleaned_origin:
        return cleaned_origin

    resolved_origin, _ = default_origin(location_tags, user_settings)
    return resolved_origin


def matches_reference(value: str, reference: str) -> bool:
    cleaned_value = clean_text(value.lower())
    cleaned_reference = clean_text(reference.lower())
    return bool(cleaned_reference) and (
        cleaned_reference in cleaned_value or cleaned_value in cleaned_reference
    )
