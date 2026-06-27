from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.battery.model_service import ModelService, WEEKDAYS


ROOT_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = ROOT_DIR / "backend" / "data" / "battery" / "500_ev.xlsx"
MODEL_DIR = ROOT_DIR / "backend" / "data" / "battery" / "models"

router = APIRouter(prefix="/api/battery", tags=["battery"])
model_service = ModelService(dataset_path=DATASET_PATH, model_dir=MODEL_DIR)


class TripPredictionRequest(BaseModel):
    distance_km: float = Field(..., gt=0, le=1000)


class DailyPredictionRequest(BaseModel):
    day_of_week: str = Field(..., examples=["Monday"])


def load_battery_model() -> None:
    model_service.safe_load_or_train()


def _model_error(exc: RuntimeError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )


@router.get("/health")
def health() -> dict[str, Any]:
    if not model_service.ready:
        model_service.safe_load_or_train()
    return {
        "status": "ok",
        "models_ready": model_service.ready,
        "dataset_found": DATASET_PATH.exists(),
        "last_error": model_service.last_error,
    }


@router.get("/model/summary")
def model_summary() -> dict[str, Any]:
    try:
        return model_service.summary()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise _model_error(exc) from exc


@router.post("/predict/trip")
def predict_trip(payload: TripPredictionRequest) -> dict[str, Any]:
    try:
        return model_service.predict_trip(distance_km=payload.distance_km)
    except RuntimeError as exc:
        raise _model_error(exc) from exc


@router.post("/predict/daily")
def predict_daily(payload: DailyPredictionRequest) -> dict[str, Any]:
    if payload.day_of_week not in WEEKDAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"day_of_week must be one of: {', '.join(WEEKDAYS)}",
        )

    try:
        return model_service.predict_daily(day_of_week=payload.day_of_week)
    except RuntimeError as exc:
        raise _model_error(exc) from exc
