from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.routers.fatigue import router as fatigue_router
from backend.app.routers.maps import router as maps_router
from backend.app.routers.trip_planner import router as trip_planner_router


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="CarPlay Routes", version="1.0.0")
app.include_router(fatigue_router)
app.include_router(maps_router)
app.include_router(trip_planner_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
