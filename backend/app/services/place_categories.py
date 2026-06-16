PLACE_CATEGORY_TYPES: dict[str, str] = {
    "accommodation": "lodging",
    "accommodations": "lodging",
    "attraction": "tourist_attraction",
    "attractions": "tourist_attraction",
    "cafe": "cafe",
    "cafes": "cafe",
    "coffee": "coffee_shop",
    "coffee shop": "coffee_shop",
    "hotel": "lodging",
    "hotels": "lodging",
    "kopitiam": "restaurant",
    "landmark": "tourist_attraction",
    "landmarks": "tourist_attraction",
    "local food": "restaurant",
    "lodging": "lodging",
    "restaurant": "restaurant",
    "restaurants": "restaurant",
    "scenic stop": "tourist_attraction",
    "scenic stops": "tourist_attraction",
    "sightseeing": "tourist_attraction",
    "tourist attraction": "tourist_attraction",
    "tourist attractions": "tourist_attraction",
    "mall": "shopping_mall",
    "malls": "shopping_mall",
    "hospital": "hospital",
    "clinic": "medical_clinic",
}


def normalize_place_category(value: str) -> str:
    return " ".join(value.lower().strip().split())


def google_place_type_for_category(value: str) -> str | None:
    return PLACE_CATEGORY_TYPES.get(normalize_place_category(value))


def place_category_pattern() -> str:
    return "|".join(
        sorted(
            (category.replace(" ", r"\s+") for category in PLACE_CATEGORY_TYPES),
            key=len,
            reverse=True,
        )
    )
