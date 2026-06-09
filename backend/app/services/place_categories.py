PLACE_CATEGORY_TYPES: dict[str, str] = {
    "cafe": "cafe",
    "coffee": "coffee_shop",
    "coffee shop": "coffee_shop",
    "restaurant": "restaurant",
    "mall": "shopping_mall",
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
