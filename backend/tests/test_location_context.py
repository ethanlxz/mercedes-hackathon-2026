from backend.app.services.location_context import (
    default_origin,
    matches_reference,
    origin_or_default,
)


def test_origin_defaults_to_current_location_then_home():
    tags = {"home": "Home Address", "work": ""}

    origin, error = default_origin(tags, {"currentLocation": "Current Address"})
    assert origin == "Current Address"
    assert error is None

    origin, error = default_origin(tags, {"currentLocation": ""})
    assert origin == "Home Address"
    assert error is None


def test_origin_or_default_keeps_explicit_origin():
    origin = origin_or_default(
        "Explicit Address",
        {"home": "Home Address"},
        {"currentLocation": "Current Address"},
    )
    assert origin == "Explicit Address"


def test_matches_reference_compares_normalized_substrings():
    assert matches_reference("KL Sentral, Kuala Lumpur", "kl sentral")
    assert matches_reference("klcc", "Suria KLCC")
    assert not matches_reference("Mid Valley", "")
