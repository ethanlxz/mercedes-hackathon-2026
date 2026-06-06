"""
routers/agent.py
----------------
Routes for the MBUX AI Agent.

Endpoints:
  POST /agent/analyze  — analyse vehicle state + optional command,
                         return recommendations and a chat response
"""

from fastapi import APIRouter

from backend.models.schemas import AnalyzeRequest, FrequentStopRequest
from backend.services.agent_service import run_agent_analysis
from backend.services.memory_service import load_memory, add_frequent_stop

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)


@router.post("/analyze")
def analyze_state(request: AnalyzeRequest) -> dict:
    """
    Run the MBUX agent analysis pipeline.

    Processes the current simulation state and an optional natural-language
    command, returning proactive recommendations and a chat response string.
    """
    chat_response, recommendations = run_agent_analysis(
        state=request.state,
        command=request.command,
    )
    return {
        "chat_response": chat_response,
        "recommendations": recommendations,
    }


@router.get("/memory")
def get_memory() -> dict:
    """
    Retrieve the current persistent driver memory.
    """
    return load_memory()


@router.post("/memory/frequent_stop")
def create_frequent_stop(request: FrequentStopRequest) -> dict:
    """
    Add or update a frequent stop in persistent memory.
    """
    saved_stop = add_frequent_stop(
        origin=request.origin,
        destination=request.destination,
        location=request.location,
        stop_type=request.type,
        reason=request.reason,
    )
    return {
        "status": "success",
        "message": f"Successfully remembered stop '{request.location}' on route '{request.origin} -> {request.destination}'",
        "stop": saved_stop,
    }

