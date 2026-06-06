"""
routers/simulation.py
---------------------
Routes related to the vehicle simulation state.

Endpoints:
  GET  /simulation/state  — fetch current state
  POST /simulation/state  — overwrite current state
"""

from fastapi import APIRouter

from backend.models.schemas import SimulationState

router = APIRouter(
    prefix="/simulation",
    tags=["Simulation"],
)

# ---------------------------------------------------------------------------
# Module-level global: cached simulation state
# ---------------------------------------------------------------------------
# A single SimulationState instance is kept in memory for the lifetime of the
# process. All other modules that need to read the live state should import
# this router and access `simulation_router.current_state` (or use a
# dependency in a future refactor).
# ---------------------------------------------------------------------------

current_simulation_state = SimulationState()


@router.get("/state", response_model=SimulationState)
def get_simulation_state() -> SimulationState:
    """Return the current vehicle simulation state."""
    return current_simulation_state


@router.post("/state", response_model=SimulationState)
def update_simulation_state(state: SimulationState) -> SimulationState:
    """Replace the current vehicle simulation state wholesale."""
    global current_simulation_state
    current_simulation_state = state
    return current_simulation_state
