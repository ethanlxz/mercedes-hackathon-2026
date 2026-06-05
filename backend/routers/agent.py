"""
routers/agent.py
----------------
Routes for the MBUX AI Agent.

Endpoints:
  POST /agent/analyze  — analyse vehicle state + optional command,
                         return recommendations and a chat response
"""

from fastapi import APIRouter

from models.schemas import AnalyzeRequest
from services.agent_service import run_agent_analysis

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
