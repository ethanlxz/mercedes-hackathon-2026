# MBUX Mobility Assistant - Backend Architecture

This document provides a comprehensive overview of the backend architecture, its directory structure, and a detailed list of all exposed APIs. The backend is built using **FastAPI** to provide a fast, modern REST API.

## Directory Structure

The `backend/` directory is organized into distinct layers to separate routing, business logic, data models, and configurations:

```text
backend/
├── main.py                 # Application entry point. Registers routers and CORS middleware.
├── memory.json             # A lightweight JSON-based database for user profile & wallet balance.
├── config/
│   └── settings.py         # App configuration settings (e.g. CORS, version, titles).
├── models/
│   └── schemas.py          # Pydantic models for API request/response validation.
├── routers/                # API route definitions separated by feature domains.
│   ├── agent.py            # AI agent endpoints.
│   ├── frontend.py         # Serves frontend static files (HTML, CSS, JS).
│   ├── simulation.py       # Manages vehicle telemetry/simulation state.
│   └── wallet.py           # Manages mobility wallet transactions.
└── services/               # Core business logic and AI processing.
    ├── agent_service.py    # Interfaces with the MBUX AI agent.
    ├── langgraph_agent.py  # LangGraph implementation of the proactive AI agent.
    └── memory_service.py   # Utility to read/write from memory.json.
```

## API Endpoints List

Below is a detailed breakdown of all the API endpoints provided by the backend, grouped by their feature router.

### 1. Agent API (`routers/agent.py`)
Handles requests to the AI agent for generating proactive suggestions based on the vehicle state.

- **`POST /agent/analyze`**
  - **Purpose**: Processes the current simulation state along with an optional natural-language command.
  - **Payload**: `AnalyzeRequest` (contains `state` and `command`).
  - **Response**: Returns a `chat_response` string and a list of proactive `recommendations` (e.g., EV charging, rest stops, climate adjustments).

### 2. Simulation API (`routers/simulation.py`)
Manages the real-time simulation state of the vehicle (speed, battery, fatigue, location, etc.). This acts as a module-level cache during the application lifetime.

- **`GET /simulation/state`**
  - **Purpose**: Fetches the current vehicle simulation state.
  - **Response**: `SimulationState` object.
  - **Usage**: Used by the frontend to sync telemetry data visually.
- **`POST /simulation/state`**
  - **Purpose**: Overwrites the current vehicle simulation state.
  - **Payload**: `SimulationState`
  - **Response**: The updated `SimulationState`.

### 3. Wallet API (`routers/wallet.py`)
Manages the user's Mobility Wallet balance and transactions (charging EV, buying coffee at rest stops, purchasing digital extras). 

- **`GET /wallet/balance`**
  - **Purpose**: Returns the current wallet balance by reading from `memory.json`.
  - **Response**: `{ "balance": float }`
- **`POST /wallet/topup`**
  - **Purpose**: Adds funds to the mobility wallet.
  - **Payload**: `WalletTopUpRequest` (contains `amount`).
  - **Response**: Success status, the new balance, and a message.
- **`POST /wallet/charge`**
  - **Purpose**: Deducts a specific amount from the mobility wallet for services (e.g., EV charging, coffee).
  - **Payload**: `WalletChargeRequest` (contains `amount` and `reason`).
  - **Response**: Success status, the new balance, and a message. Raises HTTP 400 if funds are insufficient.

### 4. Frontend API (`routers/frontend.py`)
Serves the static frontend files directly via FastAPI, allowing you to run the entire app using a single `uvicorn` instance.

- **`GET /`** or **`GET /frontend/index.html`**
  - **Purpose**: Serves the `index.html` file containing the MBUX Dashboard UI.
- **`GET /style.css`** or **`GET /frontend/style.css`**
  - **Purpose**: Serves the `style.css` stylesheet.
- **`GET /app.js`** or **`GET /frontend/app.js`**
  - **Purpose**: Serves the `app.js` logic script.

## Core Services

- **Memory Service** (`memory_service.py`): A simple helper that persists the wallet balance into `memory.json`, preventing data loss on API restart.

## How the LangGraph Agent Orchestrates Functions

The true "brain" of the backend lies in the **Agent Service** (`agent_service.py`) and the **LangGraph Agent** (`langgraph_agent.py`), which orchestrate safety checks and recommendations dynamically.

Here is how the orchestration flows step-by-step when `POST /agent/analyze` is called:

1. **Context Assembly (`agent_service.py`)**: 
   The backend pulls the live `SimulationState` (speed, battery, location) and merges it with the driver's long-term memory (frequent stops, wallet balance, climate preferences). It constructs a comprehensive prompt containing the current state and any explicit user commands.

2. **Graph Entry (`langgraph_agent.py`)**: 
   The initial state is passed into a compiled LangGraph `StateGraph`. The graph begins at the **`agent`** node, invoking the `ChatGoogleGenerativeAI` model. The LLM is bound with several specialized Python `@tool` functions (e.g., `check_trip_feasibility`, `check_fatigue_alert`, `recommend_charging`).

3. **Tool Invocation Loop**:
   - The LLM determines which checks are necessary based on the context.
   - **Conditional Edge**: A router function (`_should_continue`) checks if the LLM requested any tools. If yes, the graph routes to the **`tools`** node.
   - The **`tools`** node safely executes the requested Python functions. These functions perform domain-specific logic (like matching fatigue levels against memory to suggest a specific coffee shop) and return JSON payloads.
   - The results are fed back to the **`agent`** node, allowing the LLM to process the tool results and formulate a cohesive, natural-language `chat_response`.

4. **Extraction & Output**:
   Once the LLM decides no more tools are needed, the graph routes to the terminal **`extract`** node. This node scans the conversation history, extracts the raw JSON payloads emitted by the tools, deduplicates them by location/type, and packages them into the final `recommendations` array. 

This state-machine architecture ensures that multiple safety checks can be orchestrated in parallel or sequence, combining rigid rule-based tool logic with flexible LLM conversational capabilities.
