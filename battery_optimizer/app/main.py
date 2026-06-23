from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ml.model_service import ModelService, WEEKDAYS


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
DATASET_PATH = BASE_DIR / "data" / "mercedes_ev_100day_dataset_weekend_fixed.xlsx"
MODEL_DIR = BASE_DIR / "models"

app = FastAPI(
    title="EV Battery Optimizer",
    description="FastAPI + XGBoost EV battery and driver behavior prediction app.",
    version="1.0.0",
)

model_service = ModelService(dataset_path=DATASET_PATH, model_dir=MODEL_DIR)


@asynccontextmanager
async def lifespan(_: FastAPI):
    model_service.load_or_train()
    yield


app.router.lifespan_context = lifespan
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class TripPredictionRequest(BaseModel):
    distance_km: float = Field(..., gt=0, le=1000)


class DailyPredictionRequest(BaseModel):
    day_of_week: str = Field(..., examples=["Monday"])


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "models_ready": model_service.ready,
        "dataset_found": DATASET_PATH.exists(),
    }


@app.get("/api/model/summary")
def model_summary() -> dict:
    try:
        return model_service.summary()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/predict/trip")
def predict_trip(payload: TripPredictionRequest) -> dict:
    try:
        return model_service.predict_trip(
            distance_km=payload.distance_km,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/predict/daily")
def predict_daily(payload: DailyPredictionRequest) -> dict:
    if payload.day_of_week not in WEEKDAYS:
        raise HTTPException(
            status_code=422,
            detail=f"day_of_week must be one of: {', '.join(WEEKDAYS)}",
        )

    try:
        return model_service.predict_daily(day_of_week=payload.day_of_week)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
