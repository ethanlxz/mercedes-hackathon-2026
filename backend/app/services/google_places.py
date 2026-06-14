from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status


TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
TEXT_SEARCH_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.types,places.googleMapsUri,places.rating,places.userRatingCount"
)


@dataclass
class ResolvedPlace:
    label: str
    address: str
    place_id: str = ""
    latitude: float | None = None
    longitude: float | None = None
    types: tuple[str, ...] = ()
    google_maps_uri: str = ""
    rating: float | None = None
    user_rating_count: int | None = None


def _google_error_message(payload: dict, fallback: str) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        return error.get("message") or fallback
    return fallback


async def resolve_nearby_place(
    place_query: str,
    reference_location: str,
    api_key: str,
) -> ResolvedPlace | None:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_MAPS_SERVER_KEY is missing from .env.",
        )

    cleaned_query = place_query.strip()
    cleaned_reference = reference_location.strip()
    if not cleaned_query or not cleaned_reference:
        return None

    return await search_place(
        text_query=f"{cleaned_query} near {cleaned_reference}",
        fallback_label=cleaned_query,
        api_key=api_key,
    )


async def search_place(
    text_query: str,
    fallback_label: str,
    api_key: str,
    included_type: str | None = None,
    strict_type_filtering: bool = False,
    location_bias: tuple[float, float] | None = None,
) -> ResolvedPlace | None:
    places = await search_places(
        text_query=text_query,
        fallback_label=fallback_label,
        api_key=api_key,
        max_result_count=1,
        included_type=included_type,
        strict_type_filtering=strict_type_filtering,
        location_bias=location_bias,
    )
    return places[0] if places else None


async def search_places(
    text_query: str,
    fallback_label: str,
    api_key: str,
    max_result_count: int = 3,
    included_type: str | None = None,
    strict_type_filtering: bool = False,
    location_bias: tuple[float, float] | None = None,
) -> list[ResolvedPlace]:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_MAPS_SERVER_KEY is missing from .env.",
        )

    cleaned_query = text_query.strip()
    cleaned_label = fallback_label.strip() or cleaned_query
    if not cleaned_query:
        return []

    request_body = {
        "textQuery": cleaned_query,
        "pageSize": max(1, min(max_result_count, 10)),
        "languageCode": "en",
        "regionCode": "MY",
    }
    if included_type:
        request_body["includedType"] = included_type
        request_body["strictTypeFiltering"] = strict_type_filtering
    if location_bias:
        latitude, longitude = location_bias
        request_body["locationBias"] = {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": 50000.0,
            }
        }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": TEXT_SEARCH_FIELD_MASK,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                TEXT_SEARCH_URL,
                json=request_body,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Google Places API timed out. Please try again.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Google Places API.",
        ) from exc

    payload = response.json() if response.content else {}
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_google_error_message(
                payload,
                "Google Places API rejected the request.",
            ),
        )

    places = payload.get("places") or []
    if not places:
        return []

    resolved_places: list[ResolvedPlace] = []
    for place in places:
        display_name = place.get("displayName") or {}
        label = display_name.get("text") or cleaned_label
        address = place.get("formattedAddress") or label
        rating = place.get("rating")
        location = place.get("location") or {}
        rating_count = place.get("userRatingCount")
        resolved_places.append(
            ResolvedPlace(
                label=label,
                address=address,
                place_id=place.get("id") or "",
                latitude=location.get("latitude"),
                longitude=location.get("longitude"),
                types=tuple(place.get("types") or ()),
                google_maps_uri=place.get("googleMapsUri") or "",
                rating=rating if isinstance(rating, (int, float)) else None,
                user_rating_count=rating_count if isinstance(rating_count, int) else None,
            )
        )
    return resolved_places
