"""
services/langgraph_agent.py
---------------------------
LangGraph state-machine agent powered by Google Gemini.

Defines:
  - AgentState   : the typed-dict flowing through the graph
  - Tool functions: domain-specific checks (fatigue, battery, cabin, etc.)
  - build_graph(): compiles the LangGraph StateGraph

The compiled graph is invoked by agent_service.run_agent_analysis().
"""

import json
import logging
from datetime import datetime
from typing import Any, Annotated, Dict, List, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from backend.config.settings import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("mercedes-assistant")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Agent State                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class AgentState(TypedDict):
    """State dictionary flowing through every node of the LangGraph."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    simulation_state: Dict[str, Any]
    memory: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    chat_response: str


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Tool Definitions                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝

@tool
def check_trip_feasibility(
    battery_soc: float,
    progress_percentage: float,
    route_active: bool,
    origin: str,
    destination: str,
) -> str:
    """Check whether the vehicle has enough battery range to complete the
    remaining trip distance.  Returns a JSON summary with feasibility status
    and recommended actions."""

    if not route_active:
        return json.dumps({
            "feasible": True,
            "detail": "No active route — feasibility check not applicable.",
        })

    remaining_pct = 100.0 - progress_percentage
    est_range_km = battery_soc * 4.0          # 4 km per 1 % SoC
    remaining_distance_km = remaining_pct * 3.5  # ~350 km total route

    feasible = est_range_km >= remaining_distance_km
    detail = (
        f"Remaining distance: ~{remaining_distance_km:.0f} km. "
        f"Estimated range: ~{est_range_km:.0f} km. "
        f"{'Trip is feasible.' if feasible else 'Battery may not last — recommend a charging stop.'}"
    )

    result: Dict[str, Any] = {"feasible": feasible, "detail": detail}
    if not feasible:
        result["recommendation"] = {
            "type": "charging",
            "location": "Shell Recharge Tapah",
            "reason": (
                f"Battery at {battery_soc:.0f}% may not cover the remaining "
                f"{remaining_distance_km:.0f} km.  High-speed charger available "
                "at Shell Recharge Tapah."
            ),
            "confidence": 0.93,
        }
    return json.dumps(result)


@tool
def check_fatigue_alert(
    fatigue_level: str,
    progress_percentage: float,
    frequent_stops: str,
) -> str:
    """Evaluate the driver's fatigue level and recommend rest stops when
    drowsiness is medium or high.  ``frequent_stops`` is a JSON string of
    the driver's favourite stops from long-term memory."""

    stops = json.loads(frequent_stops) if frequent_stops else []

    if fatigue_level == "High":
        # Find a rest stop from memory, or fall back to generic
        rest_location = "Nearest R&R (Tapah / Ipoh)"
        for s in stops:
            if s.get("type") == "rest_stop":
                rest_location = s["location"]
                break

        return json.dumps({
            "alert": True,
            "severity": "CRITICAL",
            "recommendation": {
                "type": "rest_stop",
                "location": rest_location,
                "reason": (
                    "CRITICAL fatigue detected.  Attention Assist recommends "
                    "taking an immediate break for driver safety."
                ),
                "confidence": 0.99,
            },
        })

    if fatigue_level == "Medium":
        rest_location = "Starbucks Ipoh"
        for s in stops:
            if s.get("type") == "rest_stop":
                rest_location = s["location"]
                break

        return json.dumps({
            "alert": True,
            "severity": "WARNING",
            "recommendation": {
                "type": "rest_stop",
                "location": rest_location,
                "reason": (
                    "Moderate fatigue detected.  Based on your driving history, "
                    f"a coffee break at {rest_location} is recommended."
                ),
                "confidence": 0.85,
            },
        })

    return json.dumps({
        "alert": False,
        "severity": "NORMAL",
        "detail": "Fatigue level is low. No action required.",
    })


@tool
def recommend_charging(
    battery_soc: float,
    route_active: bool,
    frequent_stops: str,
) -> str:
    """Analyse battery state-of-charge and recommend a charging station when
    the level is low.  ``frequent_stops`` is a JSON string of the driver's
    favourite stops from long-term memory."""

    stops = json.loads(frequent_stops) if frequent_stops else []

    if battery_soc < 20.0:
        charge_location = "Shell Recharge Tapah"
        for s in stops:
            if s.get("type") == "charging":
                charge_location = s["location"]
                break

        return json.dumps({
            "urgent": True,
            "recommendation": {
                "type": "charging",
                "location": charge_location,
                "reason": (
                    f"Critical battery level ({battery_soc:.0f}%).  "
                    f"Route to {charge_location} for high-speed DC charging."
                ),
                "confidence": 0.95,
            },
        })

    if battery_soc < 35.0:
        return json.dumps({
            "urgent": False,
            "recommendation": {
                "type": "charging",
                "location": "Caltex EV Charge",
                "reason": (
                    f"Battery is at {battery_soc:.0f}%.  "
                    "Consider scheduling a charging stop soon."
                ),
                "confidence": 0.78,
            },
        })

    est_range = battery_soc * 4.0
    return json.dumps({
        "urgent": False,
        "detail": (
            f"Battery at {battery_soc:.0f}% — estimated range {est_range:.0f} km.  "
            "Sufficient for current driving conditions."
        ),
    })


@tool
def adjust_cabin_comfort(
    cabin_temp_c: float,
    preferred_temp_c: float,
) -> str:
    """Compare the current cabin temperature with the driver's preferred
    temperature and suggest adjustments if needed."""

    diff = cabin_temp_c - preferred_temp_c
    if abs(diff) < 1.0:
        return json.dumps({
            "adjustment_needed": False,
            "detail": (
                f"Cabin temperature ({cabin_temp_c:.1f}°C) is close to your "
                f"preference ({preferred_temp_c:.1f}°C).  No adjustment needed."
            ),
        })

    direction = "Cooling" if diff > 0 else "Heating"
    return json.dumps({
        "adjustment_needed": True,
        "recommendation": {
            "type": "climate",
            "location": "Cabin A/C System",
            "reason": (
                f"Cabin is {cabin_temp_c:.1f}°C — {abs(diff):.1f}° "
                f"{'above' if diff > 0 else 'below'} your preferred "
                f"{preferred_temp_c:.1f}°C.  {direction} recommended to "
                "maintain driver alertness."
            ),
            "confidence": 0.70 if abs(diff) < 3 else 0.90,
        },
    })


@tool
def recommend_digital_extras(
    favorite_music_genre: str,
    route_active: bool,
    progress_percentage: float,
) -> str:
    """Suggest digital extras such as music streaming or parking reservations
    based on the driver's profile and trip progress."""

    extras: List[Dict[str, Any]] = []

    if favorite_music_genre:
        extras.append({
            "type": "digital_extra",
            "location": f"MBUX Sound: {favorite_music_genre}",
            "reason": (
                f"Enhance your drive with your favourite genre: "
                f"{favorite_music_genre}."
            ),
            "confidence": 0.88,
        })

    if route_active and progress_percentage > 75:
        extras.append({
            "type": "digital_extra",
            "location": "Penang Parking Hub",
            "reason": (
                "You are nearing your destination.  Reserve a parking space "
                "in Penang for a seamless arrival."
            ),
            "confidence": 0.72,
        })

    return json.dumps({"extras": extras})


@tool
def check_wallet(
    wallet_balance: float,
    route_active: bool,
) -> str:
    """Check the mobility wallet balance and warn if it is low for upcoming
    potential charges (charging ~RM 45, rest stops ~RM 15)."""

    min_needed = 60.0 if route_active else 15.0
    is_low = wallet_balance < min_needed

    result: Dict[str, Any] = {
        "balance": wallet_balance,
        "sufficient": not is_low,
    }
    if is_low:
        result["warning"] = (
            f"Wallet balance is RM {wallet_balance:.2f}.  "
            f"Recommended minimum for this trip is RM {min_needed:.2f}.  "
            "Consider topping up."
        )
    return json.dumps(result)


@tool
def save_frequent_stop(
    location: str,
    stop_type: str,
    reason: str,
    origin: str,
    destination: str,
) -> str:
    """Save a new frequent stop/location (like a cafe, charging station, or rest area) 
    to the driver's persistent memory. Use this tool whenever the driver requests to 
    remember a stop, cafe, restaurant, charger, or location for their trip."""
    from backend.services.memory_service import add_frequent_stop
    try:
        add_frequent_stop(
            origin=origin,
            destination=destination,
            location=location,
            stop_type=stop_type,
            reason=reason
        )
        return f"Successfully saved '{location}' to long-term memory for the route {origin} -> {destination}."
    except Exception as e:
        return f"Failed to save stop: {str(e)}"


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  System Prompt                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════╝

SYSTEM_PROMPT = """\
You are the Mercedes-Benz MBUX Mobility Assistant — a proactive, safety-first \
in-car AI agent.  Your job is to keep the driver safe, comfortable, and \
informed during their journey.

You will receive:
1. The current vehicle simulation state (speed, battery SoC, fatigue level, \
   cabin temperature, route progress, coordinates).
2. The driver's long-term memory (profile, favourite stops, trip history).
3. An optional natural-language command from the driver.

Your workflow:
- ALWAYS call the relevant tool functions to analyse the current state.  \
  At minimum, check fatigue and battery on every invocation.
- If the driver sent a command, address it conversationally AND call any \
  extra tools needed.
- Return a short, friendly, professional chat message summarising the \
  situation and any recommendations.

IMPORTANT RULES:
- Be concise. Drivers should not read long paragraphs.
- Prioritise safety: fatigue and battery alerts come first.
- Reference the driver's memory (name, favourite stops) to feel personalised.
- Never fabricate tool output — only use results returned by your tools.
"""


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Graph Construction                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

ALL_TOOLS = [
    check_trip_feasibility,
    check_fatigue_alert,
    recommend_charging,
    adjust_cabin_comfort,
    recommend_digital_extras,
    check_wallet,
    save_frequent_stop,
]


def _build_llm():
    """Construct the ChatGoogleGenerativeAI LLM with tools bound."""
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.3,
        convert_system_message_to_human=True,
    )
    # Do NOT bind tools directly to the LLM here. The LangGraph `ToolNode`
    # executes our @tool functions based on the model's tool-calls. Binding
    # tools to the LLM causes tools to be executed twice (LLM + ToolNode),
    # which can produce an infinite loop of tool-calls and Gemini invocations.
    return llm


def _agent_node(state: AgentState) -> dict:
    """Invoke Gemini with the current messages and return its reply."""
    llm = _build_llm()
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def _should_continue(state: AgentState) -> str:
    """Conditional edge: route to 'tools' if the last message has tool calls,
    otherwise end the graph."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


def _extract_recommendations(state: AgentState) -> dict:
    """Terminal node: parse all tool-call results from the message history
    and collect recommendations into the state."""
    recommendations: List[Dict[str, Any]] = []

    for msg in state["messages"]:
        # ToolMessages carry the JSON strings returned by our @tool functions
        if msg.type == "tool":
            try:
                data = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                continue

            # Single recommendation
            if "recommendation" in data:
                recommendations.append(data["recommendation"])

            # List of extras
            if "extras" in data:
                recommendations.extend(data["extras"])

    # Deduplicate by (type, location)
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for rec in sorted(recommendations, key=lambda r: r.get("confidence", 0), reverse=True):
        key = (rec.get("type", ""), rec.get("location", ""))
        if key not in seen:
            seen.add(key)
            unique.append(rec)

    # Extract the final chat response from the last AI message
    chat_response = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            chat_response = msg.content.strip()
            break

    return {
        "recommendations": unique,
        "chat_response": chat_response,
    }


def build_graph() -> StateGraph:
    """Build and compile the LangGraph agent graph.

    Flow::

        START → agent → should_continue?
                        ├─ tool_calls → tools → agent  (loop)
                        └─ no calls  → extract → END
    """
    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AgentState)

    graph.add_node("agent", _agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("extract", _extract_recommendations)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        _should_continue,
        {
            "tools": "tools",
            END: "extract",
        },
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("extract", END)

    return graph.compile()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Module-level compiled graph (singleton)                               ║
# ╚══════════════════════════════════════════════════════════════════════════╝

compiled_graph = None


def get_graph():
    """Lazy-initialise and return the compiled LangGraph."""
    global compiled_graph
    if compiled_graph is None:
        compiled_graph = build_graph()
        logger.info("LangGraph agent compiled successfully.")
    return compiled_graph
