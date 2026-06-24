"""Compatibility facade for the trip planner implementation.

The implementation is split across focused modules, but this module preserves the
old import path used by routers, tests, and checkpoint serializer allow-lists.
"""

from backend.app.services.google_places import search_places
from backend.app.services.google_routes import compute_multi_stop_route, compute_route_matrix
from backend.app.services.memory_service import update_preferences
from backend.app.trip_planner import graph as _graph
from backend.app.trip_planner import parser as _parser
from backend.app.trip_planner import routing as _routing
from backend.app.trip_planner.graph import (
    _GraphRuntime,
    _RUNTIME,
    _interrupt_payload,
    _response_from_state,
)
from backend.app.trip_planner.models import (
    CURRENT_LOCATION_ALIASES,
    FOOD_CATEGORY_TERMS,
    MALAYSIA_TZ,
    TAG_ALIASES,
    Candidate,
    ParsedPreferences,
    ParsedTrip,
    PlannerDependencies,
    PlannerState,
    ResolvedWaypoint,
    WaypointIntent,
    _clean,
    _latest_resolved,
    _tag_name,
)
from backend.app.trip_planner.parser import (
    _normalize_model_payload,
    _parse_with_deepseek,
)
from backend.app.trip_planner.resolution import (
    _candidate_from_place,
    _candidate_is_confident,
    _candidate_text_score,
    _default_origin,
    _is_food_category_query,
    _merge_preferences,
    _normalize_place_intent,
    _place_result,
    _resolve_context_value,
)
from backend.app.trip_planner.routing import (
    _duration_seconds,
    _parse_clock,
    plan_route,
    validate_route_schedule,
)


def _sync_compat_overrides() -> None:
    _graph._parse_with_deepseek = _parse_with_deepseek
    _parser._parse_with_deepseek = _parse_with_deepseek
    _graph.search_places = search_places
    _graph.compute_route_matrix = compute_route_matrix
    _graph.update_preferences = update_preferences
    _routing.compute_multi_stop_route = compute_multi_stop_route


def build_trip_graph(dependencies: PlannerDependencies, checkpointer):
    _sync_compat_overrides()
    return _graph.build_trip_graph(dependencies, checkpointer)


async def plan_trip(*args, **kwargs):
    _sync_compat_overrides()
    return await _graph.plan_trip(*args, **kwargs)


async def resume_trip(*args, **kwargs):
    _sync_compat_overrides()
    return await _graph.resume_trip(*args, **kwargs)
