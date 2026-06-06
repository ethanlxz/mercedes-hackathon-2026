"""
main.py
-------
Application entry point for the Mercedes Mobility Assistant API.

Responsibilities:
  - Create the FastAPI application instance
  - Register middleware (CORS)
  - Include all routers

Run with:
    uvicorn main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import APP_TITLE, APP_VERSION, CORS_ORIGINS
from backend.routers import agent, frontend, simulation, wallet

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mercedes-assistant")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(frontend.router)          # GET /  and static asset routes
app.include_router(simulation.router)        # GET|POST /simulation/state
app.include_router(wallet.router)            # GET|POST /wallet/*
app.include_router(agent.router)             # POST /agent/analyze

# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
