# EV Battery Optimizer

AI-powered EV battery prediction web app built with FastAPI, XGBoost, and a minimal Tailwind frontend.

## Features

- Predicts required battery percentage for a trip.
- Predicts expected daily driving distance by weekday.
- Predicts expected daily battery usage by weekday.
- Uses a copied Excel dataset as the local source of truth.
- Serves a clean Light Studio Planner dashboard at `/`.

## Project Structure

```text
app/
  main.py
  ml/model_service.py
  static/
data/
models/
tests/
requirements.txt
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

The app trains and saves model artifacts automatically on startup if `models/ev_battery_models.joblib` does not exist.

## API

- `GET /api/health`
- `GET /api/model/summary`
- `POST /api/predict/trip`
- `POST /api/predict/daily`

Trip prediction request:

```json
{
  "distance_km": 80
}
```

Daily prediction request:

```json
{
  "day_of_week": "Tuesday"
}
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```
