from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from backend.app.schemas.routes import RouteResponse


@dataclass
class ActiveRoadTrip:
    route_id: str
    origin: str
    destination: str
    route: RouteResponse


_ROUTES: dict[str, ActiveRoadTrip] = {}
_LOCK = Lock()


def store_active_road_trip(
    *,
    origin: str,
    destination: str,
    route: RouteResponse,
) -> ActiveRoadTrip:
    active = ActiveRoadTrip(
        route_id=str(uuid4()),
        origin=origin.strip(),
        destination=destination.strip(),
        route=route,
    )
    with _LOCK:
        _ROUTES[active.route_id] = active
    return active


def get_active_road_trip(route_id: str) -> ActiveRoadTrip | None:
    with _LOCK:
        return _ROUTES.get(route_id)


def update_active_road_trip(route_id: str, route: RouteResponse) -> None:
    with _LOCK:
        active = _ROUTES.get(route_id)
        if active:
            active.route = route


def clear_active_road_trips() -> None:
    with _LOCK:
        _ROUTES.clear()

