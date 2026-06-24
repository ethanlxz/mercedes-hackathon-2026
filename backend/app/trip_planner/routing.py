from datetime import datetime, time, timedelta
from typing import Literal

from backend.app.services.google_routes import compute_multi_stop_route
from backend.app.trip_planner.models import (
    MALAYSIA_TZ,
    PlannerDependencies,
    PlannerState,
    _latest_resolved,
)
from backend.app.trip_planner.schemas import NormalizedTripPlan, TripWaypoint


def _parse_clock(value: str | None) -> time | None:
    if not value:
        return None
    cleaned = value.strip().upper().replace(" ", "")
    for pattern in ("%H:%M", "%I:%M%p", "%I%p"):
        try:
            return datetime.strptime(cleaned, pattern).time()
        except ValueError:
            continue
    return None


def _duration_seconds(value: str) -> int:
    try:
        return max(0, int(float(value.rstrip("s"))))
    except (TypeError, ValueError):
        return 0


async def plan_route(
    state: PlannerState,
    dependencies: PlannerDependencies,
) -> dict[str, object]:
    latest = _latest_resolved(state)
    selected = [latest[index] for index in sorted(latest)]
    addresses = [item.selected.address for item in selected if item.selected]
    if len(addresses) != len(state["parsed"].waypoints):
        return {"pending_question": "Please resolve every stop before routing."}

    destination = addresses[-1]
    stops = addresses[:-1]
    preferences = state["preferences"]
    optimize = (
        state["parsed"].optimizeFlexible
        and len(stops) > 1
        and all(item.intent.flexible for item in selected[:-1])
    )
    route_response = await compute_multi_stop_route(
        origin=state["resolved_origin"],
        stops=stops,
        destination=destination,
        stop_place_ids=[item.selected.placeId for item in selected[:-1]],
        destination_place_id=selected[-1].selected.placeId,
        preferences=preferences,
        api_key=dependencies.google_maps_server_key,
        optimize_waypoints=optimize,
    )
    planned_order = list(range(len(selected)))
    if optimize and route_response.optimizedWaypointOrder:
        stop_order = [
            index
            for index in route_response.optimizedWaypointOrder
            if 0 <= index < len(stops)
        ]
        if len(stop_order) == len(stops):
            planned_order = [*stop_order, len(selected) - 1]
            stops = [addresses[index] for index in stop_order]
    plan = NormalizedTripPlan(
        origin=state["resolved_origin"],
        stops=stops,
        destination=destination,
        preferences=preferences,
    )
    return {
        "normalized_plan": plan,
        "route_response": route_response,
        "planned_order": planned_order,
    }


async def validate_route_schedule(state: PlannerState) -> dict[str, object]:
    parsed = state["parsed"]
    now = datetime.now(MALAYSIA_TZ)
    requested = state.get("requested_departure_time")
    departure: datetime
    if requested:
        departure = datetime.fromisoformat(requested)
        departure = departure.replace(tzinfo=MALAYSIA_TZ) if departure.tzinfo is None else departure.astimezone(MALAYSIA_TZ)
    else:
        parsed_time = _parse_clock(parsed.departureTime)
        departure = datetime.combine(now.date(), parsed_time, MALAYSIA_TZ) if parsed_time else now

    latest = _latest_resolved(state)
    leg_durations = list(state["route_response"].legDurations)
    if len(leg_durations) < len(parsed.waypoints):
        total = _duration_seconds(state["route_response"].duration)
        average = total // max(1, len(parsed.waypoints))
        leg_durations = [f"{average}s"] * len(parsed.waypoints)

    waypoints = [
        TripWaypoint(
            role="origin",
            label="Start",
            address=state["resolved_origin"],
            arrivalTime=departure.isoformat(),
            departureTime=departure.isoformat(),
        )
    ]
    cursor = departure
    schedule_error = None
    planned_order = state.get("planned_order") or list(range(len(parsed.waypoints)))
    for route_index, intent_index in enumerate(planned_order):
        intent = parsed.waypoints[intent_index]
        cursor += timedelta(seconds=_duration_seconds(leg_durations[route_index]))
        item = latest[intent_index]
        candidate = item.selected
        deadline = _parse_clock(intent.arriveBy)
        status_value: Literal["none", "met", "missed"] = "none"
        if deadline:
            deadline_at = datetime.combine(cursor.date(), deadline, MALAYSIA_TZ)
            status_value = "met" if cursor <= deadline_at else "missed"
            if status_value == "missed" and not schedule_error:
                schedule_error = (
                    f"The earliest estimated arrival at {candidate.name} is "
                    f"{cursor.strftime('%I:%M %p').lstrip('0')}, "
                    f"after the requested {deadline_at.strftime('%H:%M')}. "
                    "Which time, stop, or route preference should I change?"
                )
        arrival = cursor
        depart_after = _parse_clock(intent.departAfter)
        if depart_after:
            required_departure = datetime.combine(cursor.date(), depart_after, MALAYSIA_TZ)
            cursor = max(cursor, required_departure)
        cursor += timedelta(minutes=intent.dwellMinutes)
        role: Literal["stop", "destination"] = "destination" if route_index == len(planned_order) - 1 else "stop"
        waypoints.append(
            TripWaypoint(
                role=role,
                label=candidate.name,
                address=candidate.address,
                placeId=candidate.placeId,
                rating=candidate.rating,
                googleMapsUri=candidate.googleMapsUri,
                arrivalTime=arrival.isoformat(),
                departureTime=cursor.isoformat(),
                constraintStatus=status_value,
            )
        )
    return {
        "waypoints": waypoints,
        "departure_datetime": departure.isoformat(),
        "schedule_error": schedule_error,
        "pending_question": schedule_error,
    }
