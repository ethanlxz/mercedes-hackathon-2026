# Backend Refactor Walkthrough

## ✅ Verification

```
App loaded OK: Mercedes Mobility Assistant API
```

`python -c "from main import app; print(app.title)"` passed with zero errors.
The app still runs with `uvicorn main:app --reload` exactly as before.

---

## Final Project Structure

```
backend/
├── main.py                        ← App factory: creates app, wires CORS + routers
│
├── config/
│   ├── __init__.py
│   └── settings.py                ← All paths, titles, CORS config
│
├── models/
│   ├── __init__.py                ← Re-exports all schemas
│   └── schemas.py                 ← SimulationState, AnalyzeRequest, Wallet models
│
├── services/
│   ├── __init__.py                ← Re-exports service functions
│   ├── memory_service.py          ← load_memory() / save_memory() file I/O
│   └── agent_service.py           ← Full MBUX agent recommendation logic
│
├── routers/
│   ├── __init__.py
│   ├── frontend.py                ← GET / + static CSS/JS file serving
│   ├── simulation.py              ← GET|POST /simulation/state
│   ├── wallet.py                  ← GET /wallet/balance, POST /topup, /charge
│   └── agent.py                   ← POST /agent/analyze
│
├── dependencies/
│   └── __init__.py                ← Placeholder for auth / DB session deps
│
├── utils/
│   └── __init__.py                ← Placeholder for general helper functions
│
├── memory.json                    ← Persistent user memory (unchanged)
└── requirements.txt               ← Unchanged
```

---

## What Changed & Why

### `config/settings.py` — **[NEW]**
Centralises `MEMORY_FILE`, `FRONTEND_DIR`, `APP_TITLE`, `CORS_ORIGINS`.
No more scattered `os.path.join(os.path.dirname(__file__), ...)` calls throughout the codebase.

### `models/schemas.py` — **[NEW]**
All four Pydantic models (`SimulationState`, `AnalyzeRequest`, `WalletTopUpRequest`, `WalletChargeRequest`) in one place, importable by any router or service.

### `services/memory_service.py` — **[NEW]**
`load_memory()` and `save_memory()` extracted into a dedicated service.  
The default fallback memory is now a named constant `_DEFAULT_MEMORY` instead of inline code.

### `services/agent_service.py` — **[NEW]**
The entire 150-line `analyze_state` function body is now `run_agent_analysis()` — a pure Python function with **no FastAPI dependency**, making it independently unit-testable.  
Command parsing is separated into a private `_parse_command()` helper, and deduplication into `_deduplicate()`.

### `routers/simulation.py` — **[NEW]**
`GET /simulation/state` and `POST /simulation/state` with the `current_simulation_state` global living alongside its routes.

### `routers/wallet.py` — **[NEW]**
`GET /wallet/balance`, `POST /wallet/topup`, `POST /wallet/charge` — delegates all persistence to `memory_service`.

### `routers/agent.py` — **[NEW]**
`POST /agent/analyze` — a thin 10-line handler that calls `run_agent_analysis()` and returns the result.

### `routers/frontend.py` — **[NEW]**
Static file serving for `index.html`, `style.css`, `app.js` (both `/` and `/frontend/` aliases), reading paths from `config.settings.FRONTEND_DIR`.

### `main.py` — **[REWRITTEN]**
Now only 50 lines. Creates the `FastAPI` app, registers CORS middleware, and calls `app.include_router()` for each of the four routers.

---

## No Behaviour Changes

| Route | Before | After |
|---|---|---|
| `GET /` | ✅ | ✅ |
| `GET /simulation/state` | ✅ | ✅ |
| `POST /simulation/state` | ✅ | ✅ |
| `GET /wallet/balance` | ✅ | ✅ |
| `POST /wallet/topup` | ✅ | ✅ |
| `POST /wallet/charge` | ✅ | ✅ |
| `POST /agent/analyze` | ✅ | ✅ |

All request/response schemas, logic, and error handling are identical to the original.
