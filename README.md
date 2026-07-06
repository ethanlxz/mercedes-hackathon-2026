<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&amp;height=260&amp;section=header&amp;color=0:0B1220,45:1769E8,100:24B46B&amp;text=MEME&amp;desc=Mercedes%20Enhanced%20Mobility%20Engine&amp;fontColor=FFFFFF&amp;fontSize=86&amp;fontAlignY=38&amp;descSize=24&amp;descAlignY=58&amp;animation=fadeIn" alt="MEME - Mercedes Enhanced Mobility Engine" />
</p>

<h1 align="center">MEME - Mercedes Enhanced Mobility Engine</h1>

<h2 align="center">Mercedes Vibathon 2026 Finalist Project</h2>

MEME is a centralized AI driving assistant that connects route planning, EV battery prediction, driver fatigue detection, and preference memory into one coordinated mobility engine. Instead of treating each vehicle feature as a separate tool, MEME acts as a unified decision layer that understands the full trip context and recommends the next safest, most useful action for the driver.

Built by **TehOLimauAis**.

## Live Links

| Resource | Link |
| --- | --- |
| Project presentation | [https://mercedes-slides.vercel.app/](https://mercedes-slides.vercel.app/) |
| Documentation website | [https://mercedes-docs.vercel.app/](https://mercedes-docs.vercel.app/) |

## Table of Contents

- [Overview](#overview)
- [Product Screenshots](#product-screenshots)
- [Problem](#problem)
- [Solution](#solution)
- [Core Features](#core-features)
- [Technical Architecture](#technical-architecture)
- [AI vs No-AI](#ai-vs-no-ai)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Roadmap](#roadmap)

## Overview

Modern vehicles already contain many intelligent systems: navigation, range estimation, fatigue alerts, driver profiles, and connected services. The problem is that these systems often operate independently. MEME connects them.

The project demonstrates a Mercedes CarPlay-inspired web experience backed by a FastAPI service, LangGraph AI workflows, Google Maps Platform routing, DeepSeek-powered trip understanding, XGBoost battery prediction, MediaPipe fatigue detection, and persistent driver preference memory.

The result is an assistant that can:

- Plan point-to-point or multi-stop trips from natural language instructions.
- Discover recommended stops and attractions for road trips.
- Predict EV battery needs based on trip distance and historical driving patterns.
- Detect fatigue from webcam frames in real time.
- Recommend rest stops or charging stops using the active route context.
- Learn from accepted and dismissed recommendations.
- Combine route, safety, battery, and preference signals into one recommendation.

## Product Screenshots

The following screenshots show the main MEME product experience across planning, battery intelligence, fatigue detection, and driver-facing recommendations.

### Road Trip Planner

![Road Trip Planner UI](https://raw.githubusercontent.com/ethanlxz/mercedes-hackathon-2026/new_vers/mercedes-slides/mercedes-hackathon-pitch-assets/road-trip-real.png)

### EV Battery Predictor

![EV Battery Predictor UI](https://raw.githubusercontent.com/ethanlxz/mercedes-hackathon-2026/new_vers/mercedes-slides/mercedes-hackathon-pitch-assets/battery-real.png)

### Driver Fatigue Detection

![Driver Fatigue Detection UI](https://raw.githubusercontent.com/ethanlxz/mercedes-hackathon-2026/new_vers/mercedes-slides/mercedes-hackathon-pitch-assets/fatigue-real.png)

### Demo Video

[![Watch the MEME demo video](https://raw.githubusercontent.com/ethanlxz/mercedes-hackathon-2026/new_vers/mercedes-slides/mercedes-hackathon-pitch-assets/road-trip-real.png)](https://github.com/ethanlxz/mercedes-hackathon-2026/raw/new_vers/mercedes-slides/mercedes-hackathon-pitch-assets/mercedes-demo.mp4)

[Open the demo video](https://github.com/ethanlxz/mercedes-hackathon-2026/raw/new_vers/mercedes-slides/mercedes-hackathon-pitch-assets/mercedes-demo.mp4)

### Team

![TehOLimauAis team](https://raw.githubusercontent.com/ethanlxz/mercedes-hackathon-2026/new_vers/mercedes-slides/mercedes-hackathon-pitch-assets/team-slide-9.jpg)

## Problem

Connected vehicles already collect rich driving data and include many advanced features, but the driver experience is still fragmented. Navigation, fatigue alerts, battery prediction, and personalization often work as separate systems instead of sharing context and acting together.

### 1. Lack of Personalization

Vehicle systems often fail to learn driver habits. Route suggestions, charging guidance, and rest-stop recommendations can feel generic even after repeated trips because the car does not build a meaningful preference memory around the driver.

### 2. Data Is Collected but Not Used Wisely

Cars collect route history, driving style, battery behavior, and usage patterns, but that data rarely turns into immediate, driver-facing value. The driver should benefit from their own data through better recommendations, smarter route choices, and more accurate battery guidance.

### 3. Isolated Vehicle Systems

Fatigue alerts, navigation, range prediction, and recommendation systems are usually separated. A tired driver may receive an alert, but the system does not automatically combine fatigue risk, route context, nearby places, and personal preferences to recommend a useful rest stop ahead.

## Solution

MEME - Mercedes Enhanced Mobility Engine - is a unified AI agent that behaves like the "head coach" for the vehicle's intelligent features.

It connects four main capabilities:

| Capability | Role in MEME |
| --- | --- |
| Trip Planner | Converts natural language into structured routes, stops, waypoints, and arrival constraints. |
| Road Trip Planner | Discovers interesting places, stop ideas, and destination recommendations for longer journeys. |
| EV Battery Predictor | Estimates battery needs and charging risk using trip distance and driving history. |
| Driver Fatigue Detection | Converts real-time driver safety signals into actionable intervention triggers. |

Instead of producing separate alerts, MEME combines these signals and recommends the most useful next step: rest, charge, reroute, or continue.

```mermaid
graph LR
    subgraph Inputs["Vehicle and Driver Signals"]
        Trip["Trip Planner<br/>Route and waypoint context"]
        RoadTrip["Road Trip Planner<br/>Discovery and stop ideas"]
        Battery["EV Battery Predictor<br/>Energy habits"]
        Fatigue["Driver Fatigue Detection<br/>Safety signal"]
        Memory["Preference Memory<br/>Driver habits"]
    end

    Agent["MEME<br/>Central AI Agent"]

    subgraph Actions["Driver-Facing Actions"]
        Rest["Recommend rest stop"]
        Charge["Recommend charging stop"]
        Route["Update active route"]
        Learn["Update preferences"]
    end

    Trip --> Agent
    RoadTrip --> Agent
    Battery --> Agent
    Fatigue --> Agent
    Memory --> Agent
    Agent --> Rest
    Agent --> Charge
    Agent --> Route
    Agent --> Learn
```

## Core Features

### Trip Planner

The Trip Planner is for turning a driver's natural-language route request into a usable trip. It handles the direct routing workflow: parse the instruction, resolve places, compute the route, and return map-ready route data.

Example:

```text
Get coffee at a good cafe, then go to Pavilion, arrive by 3pm.
```

The trip planner supports:

- Specific destinations and category-based stops.
- Saved location tags such as home, work, and current location.
- Multi-stop routing.
- Place choice and clarification flows.

### Road Trip Planner

The Road Trip Planner is a separate feature for exploration and discovery. It helps drivers find interesting stops along a route and around the destination, then explains why each recommendation is worth considering.

This feature is designed for open-ended trip discovery, not just route computation. It combines Google Maps data with LLM-generated recommendation context so the driver can turn a route into a richer journey.

The road trip planner supports:

- Suggested stops along the route.
- Destination-area recommendations.
- AI-generated explanations for recommended places.
- Preference-aware ordering through MEME's memory layer.

### EV Battery Prediction

The battery module uses XGBoost models trained from EV trip data to estimate:

| Model | Input | Output |
| --- | --- | --- |
| Trip model | `distance_km` | Battery percentage required for a trip. |
| Distance model | `day_of_week` | Expected daily driving distance. |
| Usage model | `day_of_week` | Expected daily battery usage. |

The central agent uses these predictions to decide whether the driver can continue, should charge before departure, should charge near the destination, or needs a mid-trip charging stop.

### Driver Fatigue Detection

The fatigue module streams webcam frames over WebSocket and evaluates driver alertness using MediaPipe FaceMesh. It tracks signals such as eye closure, blink patterns, yawning, and head nodding.

When risk increases, MEME can use the active route to recommend a useful rest stop instead of sending only a generic alert.

### Preference Memory

MEME stores preference memory in JSON so the assistant can improve over time.

```json
{
  "preferredStopTypes": {
    "cafe": 3,
    "kopitiam": 5
  },
  "dislikedStopTypes": {
    "petrol_station": 2
  },
  "lovedPlaces": [],
  "dismissedPlaces": []
}
```

Every accept or dismiss action can influence future recommendations.

### Central Agent Recommendations

The central agent coordinates:

- Active route state.
- Fatigue severity.
- Battery state of charge.
- Google Maps route and place search.
- Preference memory.
- Driver feedback.

This lets the system create recommendations that are route-aware, personalized, and useful at the exact driving moment.

## Technical Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend - Mercedes CarPlay-Inspired SPA"]
        UIMap["Google Maps canvas"]
        UIPanels["Trip, road trip, battery panels"]
        UIFatigue["Webcam fatigue overlay"]
        UIModals["Alert and choice modals"]
    end

    subgraph API["FastAPI Backend"]
        MapsAPI["/api/maps/*<br/>Routes, Places, settings"]
        TripAPI["/api/trip-planner/*<br/>Trip planning"]
        RoadTripAPI["/api/road-trip-planner<br/>Road trip discovery"]
        AgentAPI["/api/central-agent/*<br/>Agent recommendations"]
        BatteryAPI["/api/battery/*<br/>Battery predictions"]
        FatigueWS["/ws/fatigue/detect<br/>Fatigue WebSocket"]
    end

    subgraph Agent["Central AI Agent - LangGraph"]
        LoadMemory["Load preference memory"]
        LoadRoute["Load active route"]
        Evaluate["Evaluate risk and trip context"]
        Search["Search route-aware stops"]
        Notify["Return driver notification"]
        LoadMemory --> LoadRoute --> Evaluate --> Search --> Notify
    end

    subgraph TripPlanner["Trip Planner - LangGraph"]
        Parse["DeepSeek intent parsing"]
        Resolve["Google Places resolution"]
        Rank["Candidate ranking"]
        Compute["Google Routes computation"]
        Parse --> Resolve --> Rank --> Compute
    end

    subgraph RoadTripPlanner["Road Trip Planner"]
        Discover["Find route and destination stops"]
        Explain["Generate recommendation context"]
        Discover --> Explain
    end

    subgraph Services["ML and External Services"]
        CV["MediaPipe FaceMesh<br/>Fatigue detection"]
        ML["XGBoost + joblib<br/>Battery prediction"]
        Google["Google Maps Platform<br/>Routes, Places, Matrix"]
        LLM["DeepSeek LLM<br/>Trip parsing and recommendations"]
        Store["SQLite + JSON<br/>Checkpoints and preferences"]
    end

    UIMap --> MapsAPI
    UIMap --> TripAPI
    UIMap --> RoadTripAPI
    UIMap --> AgentAPI
    UIPanels --> BatteryAPI
    UIFatigue --> FatigueWS
    UIModals --> AgentAPI

    TripAPI --> TripPlanner
    RoadTripAPI --> LLM
    RoadTripAPI --> Google
    AgentAPI --> Agent
    BatteryAPI --> ML
    FatigueWS --> CV

    Parse --> LLM
    Resolve --> Google
    Rank --> Google
    Compute --> Google
    RoadTripAPI --> RoadTripPlanner
    Discover --> Google
    Explain --> LLM
    Search --> Google
    LoadMemory --> Store
```

### Central Agent Workflow

```mermaid
flowchart TD
    Start["Driver state changes<br/>fatigue score, battery check, route update"] --> Request["Frontend calls central-agent endpoint"]
    Request --> ActiveRoute{"Active route available?"}
    ActiveRoute -- No --> NeedRoute["Return instruction to plan or register route"]
    ActiveRoute -- Yes --> Context["Build decision context"]
    Context --> Memory["Load preference memory"]
    Memory --> Risk["Evaluate risk severity"]
    Risk --> Branch{"Recommendation type"}
    Branch -- Fatigue --> RestSearch["Search rest stops ahead on route"]
    Branch -- Charging --> ChargeSearch["Search chargers near trigger point"]
    RestSearch --> Rank["Rank candidates by drive time, rating, severity, preferences"]
    ChargeSearch --> Rank
    Rank --> Notify["Return recommendation to frontend"]
    Notify --> Driver{"Driver accepts?"}
    Driver -- Yes --> Recompute["Recompute route with accepted stop"]
    Driver -- No --> Feedback["Record dismissal feedback"]
    Recompute --> Learn["Update preference memory"]
    Feedback --> Learn
```

### Trip Planning Sequence

```mermaid
sequenceDiagram
    participant Driver
    participant Frontend
    participant API as FastAPI
    participant Planner as Trip Planner Graph
    participant DeepSeek
    participant Google as Google Maps Platform
    participant Agent as Central Agent

    Driver->>Frontend: Enters natural-language trip request
    Frontend->>API: POST /api/trip-planner
    API->>Planner: Start planning graph
    Planner->>DeepSeek: Parse intent, stops, constraints
    DeepSeek-->>Planner: Structured trip plan
    Planner->>Google: Resolve place candidates
    Google-->>Planner: Candidate places
    Planner->>Google: Compute multi-stop route
    Google-->>Planner: Route, duration, distance, polyline
    Planner-->>API: TripPlannerResponse
    API-->>Frontend: Route and choices
    Frontend->>API: POST /api/central-agent/active-road-trip
    API->>Agent: Store active route context
```

### Fatigue Intervention Sequence

```mermaid
sequenceDiagram
    participant Camera as Webcam
    participant Frontend
    participant WS as Fatigue WebSocket
    participant Detector as MediaPipe Detector
    participant API as FastAPI
    participant Agent as Central Agent
    participant Google as Google Maps Platform
    participant Memory as Preference Memory

    loop Every frame
        Camera->>Frontend: Captured frame
        Frontend->>WS: Send base64 frame
        WS->>Detector: Process frame
        Detector-->>Frontend: Fatigue score and symptoms
    end

    Frontend->>API: POST /api/central-agent/fatigue/recommendation
    API->>Agent: FatigueRecommendationRequest
    Agent->>Memory: Load preferences
    Agent->>Agent: Load active route and evaluate severity
    Agent->>Google: Search rest stops ahead on route
    Google-->>Agent: Candidate stops
    Agent-->>API: Best rest-stop recommendation
    API-->>Frontend: Notification modal
```

### Charging Recommendation Sequence

```mermaid
sequenceDiagram
    participant Frontend
    participant API as FastAPI
    participant Agent as Central Agent
    participant Battery as Battery Model
    participant Google as Google Maps Platform

    Frontend->>API: POST /api/central-agent/charging/recommendation
    API->>Agent: ChargingRecommendationRequest
    Agent->>Agent: Load active route and current battery level
    Agent->>Battery: Predict trip battery requirement
    Battery-->>Agent: Required battery percent
    Agent->>Agent: Decide charge timing
    Agent->>Google: Search chargers near route trigger point
    Google-->>Agent: Charger candidates
    Agent-->>API: ChargingRecommendationResponse
    API-->>Frontend: Charging plan
```

### End-to-End Data Flow

```mermaid
flowchart TB
    Input["Driver input<br/>trip request, road trip request, settings, webcam, battery level"]
    Planner["Trip Planner<br/>DeepSeek + LangGraph + Google Maps"]
    RoadTrip["Road Trip Planner<br/>Google Maps + DeepSeek recommendations"]
    Route["Route response<br/>polyline, waypoints, ETA, distance"]
    Discovery["Road trip recommendations<br/>stops, attractions, explanations"]
    Active["Active route state<br/>central-agent context"]
    Monitor["Monitoring loop<br/>fatigue score + battery prediction"]
    Agent["MEME central agent<br/>reason over route, risk, battery, memory"]
    Output["Driver action<br/>rest stop, charger, updated route, preference update"]

    Input --> Planner
    Input --> RoadTrip
    Planner --> Route
    RoadTrip --> Discovery
    Route --> Active
    Discovery --> Agent
    Active --> Monitor
    Monitor --> Agent
    Agent --> Output
    Output --> Active
```

## AI vs No-AI

| Driving moment | Without MEME | With MEME |
| --- | --- | --- |
| Low EV battery | Driver manually searches for charging stations and decides where to stop. | MEME predicts battery usage and recommends charging at the right point in the trip. |
| Personalized recommendations | Every trip starts from scratch. | MEME learns accepted and skipped stops, then uses that memory in future rankings. |
| Driver feels tired | Driver receives a fatigue alert and must search for a rest stop manually. | MEME detects fatigue, reads the active route, and recommends a useful stop ahead. |
| Multi-stop trip planning | Driver manually searches places, compares routes, and reorders stops. | MEME parses natural language, resolves places, and returns a computed route. |
| Road trip discovery | Driver manually researches attractions and stop ideas separately from the route. | MEME finds route-aware stop ideas and explains why they fit the journey. |

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI, Python 3.12, Uvicorn |
| AI orchestration | LangGraph |
| LLM | DeepSeek via OpenAI-compatible client |
| Maps | Google Maps Platform: Routes, Places, Matrix |
| ML | XGBoost, joblib |
| Computer vision | MediaPipe FaceMesh |
| Frontend | HTML, CSS, vanilla JavaScript, Google Maps JavaScript API |
| Persistence | SQLite for graph checkpoints, JSON for user memory |
| Testing | Pytest |
| Presentation site | Static HTML project presentation deployed on Vercel |

## Project Structure

```text
mercedes/
+-- README.md
+-- run.ps1
+-- backend/
|   +-- requirements.txt
|   +-- requirements-dev.txt
|   +-- app/
|   |   +-- main.py
|   |   +-- battery/
|   |   |   +-- model_service.py
|   |   +-- central_agent/
|   |   |   +-- charging_service.py
|   |   |   +-- graph.py
|   |   |   +-- registry.py
|   |   |   +-- rest_stop_service.py
|   |   |   +-- schemas.py
|   |   |   +-- state.py
|   |   +-- fatigue/
|   |   |   +-- config.py
|   |   |   +-- detector.py
|   |   |   +-- utils.py
|   |   +-- routers/
|   |   |   +-- battery.py
|   |   |   +-- central_agent.py
|   |   |   +-- fatigue.py
|   |   |   +-- maps.py
|   |   |   +-- trip_planner.py
|   |   +-- services/
|   |   |   +-- google_places.py
|   |   |   +-- google_routes.py
|   |   |   +-- location_context.py
|   |   |   +-- memory_service.py
|   |   |   +-- place_categories.py
|   |   +-- trip_planner/
|   |       +-- graph.py
|   |       +-- parser.py
|   |       +-- resolution.py
|   |       +-- road_trip_service.py
|   |       +-- routing.py
|   |       +-- service.py
|   +-- data/
|   |   +-- battery/
|   |   +-- user_memory.json
|   +-- tests/
+-- frontend/
|   +-- index.html
|   +-- style.css
|   +-- css/
|   +-- js/
+-- mercedes-slides/
    +-- index.html
    +-- mercedes-hackathon-pitch-assets/
        +-- road-trip-real.png
        +-- battery-real.png
        +-- fatigue-real.png
        +-- mercedes-demo.mp4
        +-- team-slide-9.jpg
```

## Getting Started

### Prerequisites

- Python 3.12
- Google Maps Platform API key with Routes and Places enabled
- DeepSeek API key
- Webcam access for fatigue detection

### Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_MAPS_BROWSER_KEY=your_google_maps_browser_api_key
GOOGLE_MAPS_SERVER_KEY=your_google_maps_server_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### Run on Windows

```powershell
.\run.ps1
```

The script creates or reuses `venv`, installs backend requirements when needed, and starts Uvicorn on port `8080`.

### Manual Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080 --reload
```

Open:

- App: [http://127.0.0.1:8080](http://127.0.0.1:8080)
- API docs: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

## API Reference

### Health

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Backend health check. |

### Maps and Settings

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/maps/config` | Return the Google Maps browser key for the frontend. |
| `POST` | `/api/routes` | Compute a route between origin and destination. |
| `GET` | `/api/location-tags` | Read saved location tags. |
| `POST` | `/api/location-tags` | Save a tagged location such as home or work. |
| `GET` | `/api/settings` | Read user settings and preference memory summary. |
| `POST` | `/api/settings/current-location` | Save the current location. |
| `POST` | `/api/settings/ev-battery-level` | Save current EV battery percentage. |
| `POST` | `/api/places/search-nearby` | Search nearby places using Google Places. |

### Trip Planner

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/trip-planner` | Plan a trip from a natural-language instruction. |
| `POST` | `/api/trip-planner/resume` | Resume a planner flow after clarification or place choice. |
| `POST` | `/api/trip-planner/choice-route` | Build a route from a selected place choice. |

### Road Trip Planner

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/road-trip-planner` | Discover road trip stops and destination suggestions. |

### Central Agent

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/central-agent/active-road-trip` | Register the current route for agent monitoring. |
| `POST` | `/api/central-agent/fatigue/recommendation` | Recommend a rest stop from fatigue context. |
| `POST` | `/api/central-agent/rest-stop/accept` | Accept a rest stop and recompute the route. |
| `POST` | `/api/central-agent/charging/recommendation` | Recommend a charging action or stop. |
| `POST` | `/api/central-agent/charging/accept` | Accept a charging stop and recompute the route. |
| `GET` | `/api/central-agent/preferences` | Read preference memory summary. |
| `POST` | `/api/central-agent/preferences/feedback` | Record preference feedback. |
| `DELETE` | `/api/central-agent/preferences` | Reset preference memory. |

### Battery

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/battery/health` | Check model readiness. |
| `GET` | `/api/battery/model/summary` | Return battery model metrics and statistics. |
| `POST` | `/api/battery/predict/trip` | Predict battery required for a trip distance. |
| `POST` | `/api/battery/predict/daily` | Predict expected daily distance and battery use. |

### Fatigue Detection

| Protocol | Endpoint | Purpose |
| --- | --- | --- |
| `WS` | `/ws/fatigue/detect` | Stream webcam frames and receive fatigue scores. |

## Testing

Install development requirements if needed:

```powershell
pip install -r backend\requirements-dev.txt
```

Run the test suite:

```powershell
pytest backend\tests -v
```

Useful focused test commands:

```powershell
pytest backend\tests\test_trip_planner_graph.py -v
pytest backend\tests\test_central_agent.py -v
pytest backend\tests\test_battery_router.py -v
pytest backend\tests\test_fatigue_router.py -v
```

## Design Principles

| Principle | How MEME applies it |
| --- | --- |
| Unified intelligence | Route, battery, fatigue, and preferences are evaluated together. |
| Human-in-the-loop | The assistant recommends actions, but the driver accepts or dismisses them. |
| Route-aware recommendations | Rest and charging stops are chosen in the context of the active trip. |
| Personalization | Preference memory improves future stop and route suggestions. |
| Modular growth | New vehicle signals can be added as modules that feed the central agent. |
| Graceful degradation | Core flows are separated so individual services can fail without collapsing the entire app. |

## Roadmap

Planned next steps for MEME:

- Integrate native Mercedes systems such as Attention Assist, GUARD360, and DYNAMIC SELECT.
- Add more vehicle modules without rebuilding the central agent.
- Use contextual recommendations for Mercedes digital upgrades when they are genuinely useful.
- Expand personalization from stop preferences to comfort, safety, and charging behavior.
- Continue evolving MEME into a modular AI layer that gets smarter as more vehicle features connect to it.

## License

This repository is a prototype and finalist project for the Mercedes Vibathon 2026. It is intended for demonstration, learning, and evaluation of an intelligent EV driving assistant concept.
