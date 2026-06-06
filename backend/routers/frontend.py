"""
routers/frontend.py
-------------------
Serves the static frontend files (HTML, CSS, JS) directly from the backend.
This lets the app be accessed via a single uvicorn process during development.

Endpoints:
  GET /                      — serves index.html
  GET /frontend/index.html   — alias for index.html
  GET /style.css             — serves style.css
  GET /frontend/style.css    — alias for style.css
  GET /app.js                — serves app.js
  GET /frontend/app.js       — alias for app.js
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from backend.config.settings import FRONTEND_DIR
import os

router = APIRouter(tags=["Frontend"])


@router.get("/", response_class=HTMLResponse)
@router.get("/frontend/index.html", response_class=HTMLResponse)
def read_index() -> HTMLResponse:
    """Return the main HTML page."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/style.css")
@router.get("/frontend/style.css")
def read_style() -> FileResponse:
    """Return the stylesheet."""
    return FileResponse(
        os.path.join(FRONTEND_DIR, "style.css"),
        media_type="text/css",
    )


@router.get("/app.js")
@router.get("/frontend/app.js")
def read_js() -> FileResponse:
    """Return the frontend JavaScript bundle."""
    return FileResponse(
        os.path.join(FRONTEND_DIR, "app.js"),
        media_type="application/javascript",
    )
