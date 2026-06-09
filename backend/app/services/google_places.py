from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status


TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
TEXT_SEARCH_FIELD_MASK = (
    "places.displayName,places.formattedAddress,places.location,places.googleMapsUri"
)


@dataclass
class ResolvedPlace:
    label: str
    address: str
    google_maps_uri: str = ""


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

    request_body = {
        "textQuery": f"{cleaned_query} near {cleaned_reference}",
        "maxResultCount": 1,
        "languageCode": "en",
        "regionCode": "MY",
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
        return None

    place = places[0]
    display_name = place.get("displayName") or {}
    label = display_name.get("text") or cleaned_query
    address = place.get("formattedAddress") or label
    return ResolvedPlace(
        label=label,
        address=address,
        google_maps_uri=place.get("googleMapsUri") or "",
    )
