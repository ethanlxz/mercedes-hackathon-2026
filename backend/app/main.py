from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.routers.battery import load_battery_model
from backend.app.routers.battery import router as battery_router
from backend.app.routers.central_agent import router as central_agent_router
from backend.app.routers.fatigue import router as fatigue_router
from backend.app.routers.maps import router as maps_router
from backend.app.routers.trip_planner import router as trip_planner_router


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_battery_model()
    yield


app = FastAPI(title="CarPlay Routes", version="1.0.0", lifespan=lifespan)
app.include_router(battery_router)
app.include_router(fatigue_router)
app.include_router(maps_router)
app.include_router(trip_planner_router)
app.include_router(central_agent_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
